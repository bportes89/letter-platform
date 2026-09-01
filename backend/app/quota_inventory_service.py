"""Inventário de cartas contempladas — varredura Nina, trava e venda."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.administrator_service import parse_rules
from app.bacen_administrator_rules_sync import rules_sync_due, sync_administrator_rules
from app.models import Administrator, CalculationMemory, Quota, QuotaReservation, User
from app.services import utcnow

QUOTA_LOCK_TTL_MINUTES = 60
NINA_SCAN_MAX_AGE_MINUTES = 30


def run_nina_quota_scan(db: Session, user: User, quota: Quota) -> dict:
    """Varredura Nina: valida dados cadastrais antes de permitir trava."""
    if quota.status not in {"AVAILABLE", "RESERVED"}:
        raise HTTPException(status_code=409, detail="Cota não elegível para varredura Nina.")

    admin = db.get(Administrator, quota.administrator_id)
    if not admin:
        raise HTTPException(status_code=422, detail="Administradora não encontrada para a cota.")

    if rules_sync_due(admin):
        sync_administrator_rules(db, admin)

    rules = parse_rules(admin.rules_json)
    credit_rules = rules.get("credit_utilization_rules") if isinstance(rules.get("credit_utilization_rules"), dict) else {}

    blockers: list[str] = []
    if not quota.installment_due_date:
        blockers.append("Informe o vencimento da parcela no cadastro da cota.")
    if float(quota.credit_value or 0) <= 0:
        blockers.append("Crédito da cota inválido.")
    if admin.authorization_status not in {"AUTHORIZED", "APPROVED", "ACTIVE", "APPROVED_MANUALLY"}:
        blockers.append(f"Administradora com status {admin.authorization_status}.")
    allowed_categories = rules.get("allowed_categories") or []
    if allowed_categories and quota.category not in allowed_categories:
        blockers.append(f"Categoria {quota.category} não permitida pelo regulamento Bacen de {admin.name}.")
    max_credit = credit_rules.get("max_credit_per_operation_brl")
    if max_credit and float(quota.credit_value or 0) > float(max_credit):
        blockers.append(
            f"Crédito da cota excede o teto de utilização ({max_credit}) da administradora {admin.name}."
        )

    if blockers:
        quota.nina_scan_status = "REJECTED"
        quota.nina_scanned_at = utcnow()
        quota.nina_scan_detail_json = json.dumps({"blockers": blockers}, ensure_ascii=False)
        raise HTTPException(status_code=422, detail="Varredura Nina reprovou: " + " ".join(blockers))

    now = utcnow()
    quota.nina_scan_status = "CLEARED"
    quota.nina_scanned_at = now
    quota.nina_scan_detail_json = json.dumps(
        {
            "administrator": admin.name,
            "rules_version": admin.bacen_rules_version,
            "bacen_rules_synced_at": admin.bacen_rules_synced_at.isoformat() if admin.bacen_rules_synced_at else None,
            "category": quota.category,
            "credit_value": str(quota.credit_value),
            "installment_due_date": quota.installment_due_date.isoformat() if quota.installment_due_date else None,
            "scanned_by": user.id,
        },
        ensure_ascii=False,
    )
    return {
        "quota_id": quota.id,
        "status": "CLEARED",
        "scanned_at": now.isoformat(),
        "message": "Varredura Nina concluída. Cota liberada para trava de 60 minutos.",
    }


def _nina_scan_fresh(quota: Quota) -> bool:
    if quota.nina_scan_status != "CLEARED" or not quota.nina_scanned_at:
        return False
    scanned = quota.nina_scanned_at
    if scanned.tzinfo is None:
        scanned = scanned.replace(tzinfo=UTC)
    return scanned >= utcnow() - timedelta(minutes=NINA_SCAN_MAX_AGE_MINUTES)


def ensure_nina_scan_before_lock(quota: Quota) -> None:
    if not _nina_scan_fresh(quota):
        raise HTTPException(
            status_code=422,
            detail="Execute a varredura Nina antes de travar a cota (válida por 30 minutos).",
        )


def active_reservation_for_user(db: Session, quota_id: str, user_id: str) -> QuotaReservation | None:
    return db.scalar(
        select(QuotaReservation).where(
            QuotaReservation.quota_id == quota_id,
            QuotaReservation.reserved_by_id == user_id,
            QuotaReservation.status == "ACTIVE",
            QuotaReservation.expires_at > utcnow(),
        )
    )


def quota_available_for_user(db: Session, quota: Quota, user_id: str) -> bool:
    if quota.status == "AVAILABLE":
        return True
    if quota.status == "RESERVED":
        return active_reservation_for_user(db, quota.id, user_id) is not None
    return False


def mark_quotas_sold_from_calculation(db: Session, calculation: CalculationMemory) -> list[str]:
    try:
        input_data = json.loads(calculation.input_json or "{}")
    except json.JSONDecodeError:
        return []
    quota_ids = input_data.get("quota_ids") or []
    if not isinstance(quota_ids, list):
        return []

    sold: list[str] = []
    now = utcnow()
    for quota_id in quota_ids:
        quota = db.get(Quota, quota_id)
        if not quota:
            continue
        quota.status = "SOLD"
        reservation = db.scalar(
            select(QuotaReservation).where(
                QuotaReservation.quota_id == quota.id,
                QuotaReservation.status == "ACTIVE",
            )
        )
        if reservation:
            reservation.status = "CONVERTED"
            reservation.released_at = now
            reservation.release_reason = "SALE_REGISTERED"
        sold.append(quota.id)
    return sold
