"""Portal do fornecedor — listar transferências pendentes e confirmar."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cadastro_service import (
    SIT_AGUARDANDO,
    SIT_CANCELADO,
    SIT_CANCELADO_FALTA,
    SIT_CONCLUIDO,
    SIT_PAGO,
    seed_marketplace_lifecycle,
)
from app.models import Lead, Proposal, Quota, QuotaSupplier
from app.quota_supplier_service import normalize_supplier_key
from app.services import money


def _parse_json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _lifecycle(terms: dict) -> dict:
    life = terms.get("lifecycle")
    return life if isinstance(life, dict) else {}


def _write_lifecycle(proposal: Proposal, **fields) -> dict:
    terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json))
    life = terms["lifecycle"]
    for key, value in fields.items():
        life[key] = value
    terms["lifecycle"] = life
    proposal.terms_json = json.dumps(terms, ensure_ascii=False)
    return life


def supplier_sources_for_proposal(db: Session, proposal: Proposal, terms: dict) -> list[str]:
    sources: list[str] = []
    for row in terms.get("quotas") or []:
        if isinstance(row, dict) and row.get("supplier_source"):
            sources.append(str(row["supplier_source"]))
    quota_ids = [str(x) for x in (terms.get("quota_ids") or []) if x]
    if not quota_ids and terms.get("quota_id"):
        quota_ids = [str(terms["quota_id"])]
    if quota_ids:
        for quota in db.scalars(select(Quota).where(Quota.id.in_(quota_ids))):
            if quota.supplier_source:
                sources.append(str(quota.supplier_source))
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for src in sources:
        key = normalize_supplier_key(src)
        if key and key not in seen:
            seen.add(key)
            out.append(src)
    return out


def supplier_participates(db: Session, proposal: Proposal, supplier: QuotaSupplier) -> bool:
    terms = _parse_json(proposal.terms_json)
    sources = {normalize_supplier_key(s) for s in supplier_sources_for_proposal(db, proposal, terms)}
    return normalize_supplier_key(supplier.source_key) in sources


def portal_me(supplier: QuotaSupplier) -> dict:
    return {
        "id": supplier.id,
        "name": supplier.name,
        "trade_name": supplier.trade_name,
        "source_key": supplier.source_key,
        "email": supplier.email,
        "document": supplier.document,
    }


def _transfer_row(db: Session, lead: Lead, proposal: Proposal, terms: dict, life: dict) -> dict:
    sources = supplier_sources_for_proposal(db, proposal, terms)
    credit = terms.get("total_credit") or proposal.requested_amount
    entrada = terms.get("total_entrada") or terms.get("total_entrada_base")
    quota_ids = [str(x) for x in (terms.get("quota_ids") or []) if x]
    if not quota_ids and terms.get("quota_id"):
        quota_ids = [str(terms["quota_id"])]
    quotas = list(db.scalars(select(Quota).where(Quota.id.in_(quota_ids)))) if quota_ids else []
    situation = str(life.get("situation") or SIT_AGUARDANDO).upper()
    # privacidade Paulo: antes do pagamento mascara nome
    name = lead.name
    if situation == SIT_AGUARDANDO:
        parts = (lead.name or "").split()
        name = (parts[0] + " ***") if parts else "***"
    return {
        "lead_id": lead.id,
        "proposal_id": proposal.id,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "name": name,
        "situation": situation,
        "credit_value": str(money(Decimal(str(credit)))) if credit not in (None, "") else None,
        "entrada_value": str(money(Decimal(str(entrada)))) if entrada not in (None, "") else None,
        "quota_codes": [f"{q.group_code}/{q.quota_code}" for q in quotas],
        "supplier_sources": sources,
        "supplier_transfer_confirmed": bool(life.get("supplier_transfer_confirmed")),
        "supplier_transfer_confirmed_at": life.get("supplier_transfer_confirmed_at"),
        "paid_at": life.get("paid_at"),
        "confirmed_by_source_key": life.get("confirmed_by_source_key"),
    }


def list_transfers(
    db: Session,
    supplier: QuotaSupplier,
    *,
    status_filter: str = "pending",
) -> list[dict]:
    status_filter = (status_filter or "pending").strip().lower()
    proposals = list(
        db.scalars(
            select(Proposal)
            .where(
                Proposal.organization_id == supplier.organization_id,
                Proposal.product == "MARKETPLACE",
            )
            .order_by(Proposal.created_at.desc())
            .limit(400)
        )
    )
    rows: list[dict] = []
    for proposal in proposals:
        if not supplier_participates(db, proposal, supplier):
            continue
        terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json))
        life = _lifecycle(terms)
        situation = str(life.get("situation") or SIT_AGUARDANDO).upper()
        if situation in {SIT_CANCELADO, SIT_CANCELADO_FALTA, "CANCELADA"}:
            continue
        confirmed = bool(life.get("supplier_transfer_confirmed"))
        if status_filter == "pending":
            if situation != SIT_PAGO or confirmed:
                continue
        elif status_filter == "confirmed":
            if not confirmed:
                continue
        elif status_filter == "all":
            pass
        else:
            raise HTTPException(status_code=422, detail="status deve ser pending|confirmed|all")

        lead = db.get(Lead, proposal.lead_id) if proposal.lead_id else None
        if not lead:
            continue
        rows.append(_transfer_row(db, lead, proposal, terms, life))
    return rows


def get_transfer(db: Session, supplier: QuotaSupplier, lead_id: str) -> dict:
    lead = db.get(Lead, lead_id)
    if not lead or lead.organization_id != supplier.organization_id:
        raise HTTPException(status_code=404, detail="Transferência não encontrada")
    proposal = db.scalar(
        select(Proposal)
        .where(
            Proposal.lead_id == lead.id,
            Proposal.organization_id == supplier.organization_id,
            Proposal.product == "MARKETPLACE",
        )
        .order_by(Proposal.created_at.desc())
    )
    if not proposal or not supplier_participates(db, proposal, supplier):
        raise HTTPException(status_code=404, detail="Transferência não encontrada")
    terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json))
    return _transfer_row(db, lead, proposal, terms, _lifecycle(terms))


def confirm_supplier_transfer(db: Session, supplier: QuotaSupplier, lead_id: str) -> dict:
    lead = db.get(Lead, lead_id)
    if not lead or lead.organization_id != supplier.organization_id:
        raise HTTPException(status_code=404, detail="Transferência não encontrada")
    proposal = db.scalar(
        select(Proposal)
        .where(
            Proposal.lead_id == lead.id,
            Proposal.organization_id == supplier.organization_id,
            Proposal.product == "MARKETPLACE",
        )
        .order_by(Proposal.created_at.desc())
    )
    if not proposal or not supplier_participates(db, proposal, supplier):
        raise HTTPException(status_code=404, detail="Transferência não encontrada")

    terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json))
    life = _lifecycle(terms)
    situation = str(life.get("situation") or SIT_AGUARDANDO).upper()
    if situation != SIT_PAGO:
        raise HTTPException(
            status_code=409,
            detail=f"Só é possível confirmar após Pagou (situação atual: {situation}).",
        )
    if situation == SIT_CONCLUIDO:
        raise HTTPException(status_code=409, detail="Venda já concluída.")

    now = datetime.now(UTC).isoformat()
    if life.get("supplier_transfer_confirmed"):
        # idempotente
        return get_transfer(db, supplier, lead_id)

    _write_lifecycle(
        proposal,
        supplier_transfer_confirmed=True,
        supplier_transfer_confirmed_at=now,
        confirmed_by_supplier_id=supplier.id,
        confirmed_by_source_key=supplier.source_key,
    )
    db.flush()
    return get_transfer(db, supplier, lead_id)
