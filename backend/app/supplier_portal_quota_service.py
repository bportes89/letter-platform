"""Cotas do fornecedor no portal — cadastro em análise e aprovação admin."""

from __future__ import annotations

import json
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.administrator_service import APPROVED_STATUSES, homologated_administrators
from app.models import Administrator, Proposal, Quota, QuotaSupplier, User
from app.quota_supplier_service import normalize_supplier_key

QUOTA_PENDING_REVIEW = "PENDING_REVIEW"
PROTECTED_STATUSES = {"RESERVED", "SOLD"}


def _parse_detail(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _write_detail(quota: Quota, **fields) -> dict:
    detail = _parse_detail(quota.nina_scan_detail_json)
    detail.update(fields)
    quota.nina_scan_detail_json = json.dumps(detail, ensure_ascii=False)
    return detail


def _quota_owned_by_supplier(quota: Quota, supplier: QuotaSupplier) -> bool:
    return normalize_supplier_key(quota.supplier_source or "") == normalize_supplier_key(supplier.source_key)


def _parse_terms(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _quota_in_sale(db: Session, quota_id: str) -> bool:
    proposals = db.scalars(select(Proposal).where(Proposal.product == "MARKETPLACE")).all()
    for proposal in proposals:
        terms = _parse_terms(proposal.terms_json)
        quota_ids = {str(x) for x in (terms.get("quota_ids") or []) if x}
        if str(terms.get("quota_id") or "") == quota_id:
            return True
        if quota_id in quota_ids:
            return True
    return False


def quota_portal_view(quota: Quota, administrator: Administrator | None = None) -> dict:
    detail = _parse_detail(quota.nina_scan_detail_json)
    admin_name = administrator.name if administrator else detail.get("administrator_name")
    return {
        "id": quota.id,
        "group_code": quota.group_code,
        "quota_code": quota.quota_code,
        "category": quota.category,
        "credit_value": str(quota.credit_value),
        "premium_value": str(quota.premium_value),
        "installment_value": str(quota.installment_value or 0),
        "installment_due_date": quota.installment_due_date.isoformat() if quota.installment_due_date else None,
        "remaining_installments": quota.remaining_installments,
        "status": quota.status,
        "administrator_id": quota.administrator_id,
        "administrator_name": admin_name,
        "change_reason": detail.get("supplier_change_reason"),
        "created_at": quota.created_at.isoformat() if quota.created_at else None,
    }


def list_supplier_quotas(db: Session, supplier: QuotaSupplier) -> list[dict]:
    rows = db.scalars(
        select(Quota)
        .where(
            Quota.organization_id == supplier.organization_id,
            Quota.supplier_source == supplier.source_key,
        )
        .order_by(Quota.created_at.desc())
    ).all()
    admins = {a.id: a for a in db.scalars(select(Administrator)).all()}
    return [quota_portal_view(q, admins.get(q.administrator_id)) for q in rows]


def list_portal_administrators(db: Session) -> list[dict]:
    return [{"id": admin.id, "name": admin.name, "code": admin.code} for admin in homologated_administrators(db)]


def create_supplier_quota(
    db: Session,
    supplier: QuotaSupplier,
    *,
    administrator_id: str,
    group_code: str,
    quota_code: str,
    category: str,
    credit_value: float,
    premium_value: float,
    installment_value: float,
    installment_due_date: date,
    remaining_installments: int | None,
) -> dict:
    if category not in {"VEHICLE", "REAL_ESTATE"}:
        raise HTTPException(status_code=422, detail="Categoria deve ser VEHICLE ou REAL_ESTATE.")
    admin = db.get(Administrator, administrator_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Administradora não encontrada.")
    if admin.authorization_status not in APPROVED_STATUSES:
        raise HTTPException(status_code=422, detail="Administradora ainda não homologada.")

    group = group_code.strip()
    code = quota_code.strip()
    if not group or not code:
        raise HTTPException(status_code=422, detail="Grupo e cota são obrigatórios.")

    conflict = db.scalar(
        select(Quota.id).where(
            Quota.administrator_id == administrator_id,
            Quota.group_code == group,
            Quota.quota_code == code,
        )
    )
    if conflict:
        raise HTTPException(status_code=409, detail="Já existe uma cota com este grupo/cota nesta administradora.")

    quota = Quota(
        organization_id=supplier.organization_id,
        administrator_id=administrator_id,
        group_code=group,
        quota_code=code,
        category=category,
        credit_value=credit_value,
        premium_value=premium_value,
        installment_value=installment_value,
        installment_due_date=installment_due_date,
        remaining_installments=remaining_installments,
        supplier_source=supplier.source_key,
        sync_origin="SUPPLIER_PORTAL",
        status=QUOTA_PENDING_REVIEW,
    )
    db.add(quota)
    db.flush()
    _write_detail(quota, supplier_change_reason=None, administrator_name=admin.name)
    return quota_portal_view(quota, admin)


def update_supplier_quota(
    db: Session,
    supplier: QuotaSupplier,
    quota_id: str,
    *,
    change_reason: str,
    administrator_id: str | None = None,
    group_code: str | None = None,
    quota_code: str | None = None,
    category: str | None = None,
    credit_value: float | None = None,
    premium_value: float | None = None,
    installment_value: float | None = None,
    installment_due_date: date | None = None,
    remaining_installments: int | None = None,
) -> dict:
    reason = (change_reason or "").strip()
    if not reason:
        raise HTTPException(status_code=422, detail="Informe o motivo da alteração.")

    quota = db.get(Quota, quota_id)
    if not quota or quota.organization_id != supplier.organization_id or not _quota_owned_by_supplier(quota, supplier):
        raise HTTPException(status_code=404, detail="Cota não encontrada.")
    if quota.status in PROTECTED_STATUSES:
        raise HTTPException(status_code=409, detail="Cota em venda ou vendida não pode ser editada.")

    if administrator_id:
        admin = db.get(Administrator, administrator_id)
        if not admin:
            raise HTTPException(status_code=404, detail="Administradora não encontrada.")
        quota.administrator_id = administrator_id
    if group_code is not None:
        quota.group_code = group_code.strip()
    if quota_code is not None:
        quota.quota_code = quota_code.strip()
    if category is not None:
        if category not in {"VEHICLE", "REAL_ESTATE"}:
            raise HTTPException(status_code=422, detail="Categoria inválida.")
        quota.category = category
    if credit_value is not None:
        quota.credit_value = credit_value
    if premium_value is not None:
        quota.premium_value = premium_value
    if installment_value is not None:
        quota.installment_value = installment_value
    if installment_due_date is not None:
        quota.installment_due_date = installment_due_date
    if remaining_installments is not None:
        quota.remaining_installments = remaining_installments

    quota.status = QUOTA_PENDING_REVIEW
    admin = db.get(Administrator, quota.administrator_id)
    _write_detail(quota, supplier_change_reason=reason, administrator_name=admin.name if admin else None)
    db.flush()
    return quota_portal_view(quota, admin)


def delete_supplier_quota(db: Session, supplier: QuotaSupplier, quota_id: str) -> None:
    quota = db.get(Quota, quota_id)
    if not quota or quota.organization_id != supplier.organization_id or not _quota_owned_by_supplier(quota, supplier):
        raise HTTPException(status_code=404, detail="Cota não encontrada.")
    if quota.status in PROTECTED_STATUSES:
        raise HTTPException(status_code=409, detail="Cota em venda ou vendida não pode ser excluída.")
    if _quota_in_sale(db, quota.id):
        raise HTTPException(status_code=409, detail="Cota já referenciada em venda — desative em vez de excluir.")
    db.delete(quota)


def approve_supplier_quota(db: Session, user: User, quota_id: str) -> Quota:
    quota = db.scalar(select(Quota).where(Quota.id == quota_id, Quota.organization_id == user.organization_id))
    if not quota:
        raise HTTPException(status_code=404, detail="Cota não encontrada.")
    if quota.status != QUOTA_PENDING_REVIEW:
        raise HTTPException(status_code=409, detail="Somente cotas em análise podem ser aprovadas.")
    quota.status = "AVAILABLE"
    db.flush()
    return quota
