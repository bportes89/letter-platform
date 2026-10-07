"""Qualificação de parceiros — faixas, apuração de volume multi-produto e bônus SDC (legado affiliates_qualification)."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.affiliate_chain_commission_service import resolve_chain_user_ids
# Mesmo valor de cadastro_service.SIT_CONCLUIDO (evita import pesado no boot).
_MARKETPLACE_SITUATION_CONCLUDED = frozenset({"CONCLUIDO", "CONCLUIDA"})
from app.legacy_export_service import DEFAULT_SQL
from app.legacy_sql_parser import load_table
from app.models import (
    FlashSolicitation,
    PartnerQualificationAppraisalRun,
    PartnerQualificationTier,
    Proposal,
    QuitConSolicitation,
    Role,
    SdcSolicitation,
    User,
)
from app.flash_desk_service import STATUS_APPROVED as FLASH_STATUS_APPROVED
from app.quitcon_desk_service import STATUS_APPROVED as QUITCON_STATUS_APPROVED
from app.sdc_desk_service import STATUS_APPROVED as SDC_STATUS_APPROVED
from app.services import money

DEFAULT_LEGACY_SQL = DEFAULT_SQL
FRANCHISE_ROLES = frozenset({Role.PARTNER, Role.MASTER_FRANCHISEE})


def tier_view(row: PartnerQualificationTier) -> dict[str, Any]:
    return {
        "id": row.id,
        "legacy_id": row.legacy_id,
        "active": row.active,
        "name": row.name,
        "price_init": str(money(Decimal(str(row.price_init)))),
        "price_final": str(money(Decimal(str(row.price_final)))),
        "price_bonus": str(Decimal(str(row.price_bonus))),
        "sort_order": row.sort_order,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_tiers(db: Session, user: User) -> list[PartnerQualificationTier]:
    return list(
        db.scalars(
            select(PartnerQualificationTier)
            .where(PartnerQualificationTier.organization_id == user.organization_id)
            .order_by(
                PartnerQualificationTier.price_init.asc(),
                PartnerQualificationTier.sort_order.asc(),
                PartnerQualificationTier.name.asc(),
            )
        )
    )


def get_tier(db: Session, user: User, tier_id: str) -> PartnerQualificationTier:
    row = db.scalar(
        select(PartnerQualificationTier).where(
            PartnerQualificationTier.id == tier_id,
            PartnerQualificationTier.organization_id == user.organization_id,
        )
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faixa não encontrada")
    return row


def create_tier(db: Session, user: User, payload: dict[str, Any]) -> PartnerQualificationTier:
    row = PartnerQualificationTier(
        organization_id=user.organization_id,
        legacy_id=payload.get("legacy_id"),
        active=bool(payload.get("active", True)),
        name=str(payload["name"]).strip(),
        price_init=float(payload.get("price_init") or 0),
        price_final=float(payload.get("price_final") or 0),
        price_bonus=float(payload.get("price_bonus") or 0),
        sort_order=int(payload.get("sort_order") or 999),
    )
    db.add(row)
    db.flush()
    return row


def update_tier(db: Session, user: User, tier_id: str, payload: dict[str, Any]) -> PartnerQualificationTier:
    row = get_tier(db, user, tier_id)
    for field in ("active", "name", "price_init", "price_final", "price_bonus", "sort_order"):
        if field in payload and payload[field] is not None:
            setattr(row, field, payload[field])
    db.flush()
    return row


def resolve_tier_for_amount(db: Session, organization_id: str, amount: Decimal) -> PartnerQualificationTier | None:
    tiers = db.scalars(
        select(PartnerQualificationTier)
        .where(
            PartnerQualificationTier.organization_id == organization_id,
            PartnerQualificationTier.active.is_(True),
        )
        .order_by(PartnerQualificationTier.price_init.asc(), PartnerQualificationTier.sort_order.asc())
    ).all()
    value = money(amount)
    for tier in tiers:
        lo = money(Decimal(str(tier.price_init)))
        hi = money(Decimal(str(tier.price_final)))
        if lo <= value <= hi:
            return tier
    return None


def qualification_bonus_pct(db: Session, organization_id: str, franchise_user: User | None) -> Decimal:
    if not franchise_user or not franchise_user.partner_qualification_tier_id:
        return Decimal("0")
    tier = db.get(PartnerQualificationTier, franchise_user.partner_qualification_tier_id)
    if not tier or not tier.active or tier.organization_id != organization_id:
        return Decimal("0")
    return Decimal(str(tier.price_bonus or 0))


def _franchise_users(db: Session, organization_id: str) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(
                User.organization_id == organization_id,
                User.active.is_(True),
                User.role.in_(tuple(FRANCHISE_ROLES)),
            )
            .order_by(User.name.asc())
        )
    )


def _period_bounds(date_init: date, date_final: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_init, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_final, time.max.replace(microsecond=0), tzinfo=timezone.utc)
    return start, end


def _rollup_partner_amounts_to_franchise(
    db: Session,
    organization_id: str,
    partner_amounts: dict[str, Decimal],
) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for partner_user_id, amount in partner_amounts.items():
        if amount <= 0:
            continue
        chain = resolve_chain_user_ids(db, organization_id, partner_user_id)
        franchise_id = chain.get("franquia")
        if not franchise_id:
            continue
        totals[franchise_id] = totals.get(franchise_id, Decimal("0")) + money(amount)
    return totals


def _desk_partner_totals(
    db: Session,
    organization_id: str,
    start: datetime,
    end: datetime,
    model: type,
    status_approved: str,
    amount_column,
) -> dict[str, Decimal]:
    rows = db.execute(
        select(model.partner_user_id, func.coalesce(func.sum(amount_column), 0))
        .where(
            model.organization_id == organization_id,
            model.status == status_approved,
            model.created_at >= start,
            model.created_at <= end,
            model.partner_user_id.isnot(None),
        )
        .group_by(model.partner_user_id)
    ).all()
    totals: dict[str, Decimal] = {}
    for partner_user_id, total in rows:
        if not partner_user_id:
            continue
        value = money(Decimal(str(total or 0)))
        if value <= 0:
            continue
        totals[str(partner_user_id)] = totals.get(str(partner_user_id), Decimal("0")) + value
    return totals


def _marketplace_concluded_partner_totals(
    db: Session,
    organization_id: str,
    start: datetime,
    end: datetime,
) -> dict[str, Decimal]:
    """Cartas contempladas concluídas no período (lifecycle CONCLUIDO)."""
    rows = db.execute(
        select(
            Proposal.commission_originator_id,
            Proposal.requested_amount,
            Proposal.terms_json,
        ).where(
            Proposal.organization_id == organization_id,
            Proposal.product == "MARKETPLACE",
            Proposal.created_at >= start,
            Proposal.created_at <= end,
            Proposal.commission_originator_id.isnot(None),
        )
    ).all()
    totals: dict[str, Decimal] = {}
    for originator_id, requested_amount, terms_raw in rows:
        if not originator_id:
            continue
        try:
            terms = json.loads(terms_raw or "{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(terms, dict):
            continue
        life = terms.get("lifecycle")
        if not isinstance(life, dict):
            continue
        situation = str(life.get("situation") or "").upper()
        if situation not in _MARKETPLACE_SITUATION_CONCLUDED:
            continue
        value = money(Decimal(str(requested_amount or 0)))
        if value <= 0:
            continue
        key = str(originator_id)
        totals[key] = totals.get(key, Decimal("0")) + value
    return totals


def _sales_volume_by_franchise(
    db: Session,
    organization_id: str,
    date_init: date,
    date_final: date,
) -> dict[str, Decimal]:
    """Volume de vendas concluídas: SDC, Marketplace, Flash Capital e QuitCon."""
    start, end = _period_bounds(date_init, date_final)
    partner_amounts: dict[str, Decimal] = {}

    for chunk in (
        _desk_partner_totals(
            db, organization_id, start, end, SdcSolicitation, SDC_STATUS_APPROVED, SdcSolicitation.credit_estimated
        ),
        _desk_partner_totals(
            db, organization_id, start, end, FlashSolicitation, FLASH_STATUS_APPROVED, FlashSolicitation.principal
        ),
        _desk_partner_totals(
            db,
            organization_id,
            start,
            end,
            QuitConSolicitation,
            QUITCON_STATUS_APPROVED,
            QuitConSolicitation.quitacao_vp_amount,
        ),
        _marketplace_concluded_partner_totals(db, organization_id, start, end),
    ):
        for partner_id, amount in chunk.items():
            partner_amounts[partner_id] = partner_amounts.get(partner_id, Decimal("0")) + amount

    return _rollup_partner_amounts_to_franchise(db, organization_id, partner_amounts)


def clear_appraisal_preview(db: Session, organization_id: str) -> None:
    for user in _franchise_users(db, organization_id):
        user.partner_qualification_appraisal_amount = 0
        user.partner_qualification_appraisal_tier_id = None
        user.partner_qualification_appraisal_tier_name = "— — — —"
    db.flush()


def run_appraisal_preview(db: Session, organization_id: str, date_init: date, date_final: date) -> list[dict[str, Any]]:
    if date_final < date_init:
        raise HTTPException(status_code=422, detail="Data final deve ser igual ou posterior à inicial")
    totals = _sales_volume_by_franchise(db, organization_id, date_init, date_final)
    result: list[dict[str, Any]] = []
    for franchise in _franchise_users(db, organization_id):
        amount = totals.get(franchise.id, Decimal("0"))
        tier = resolve_tier_for_amount(db, organization_id, amount)
        franchise.partner_qualification_appraisal_amount = float(amount)
        franchise.partner_qualification_appraisal_tier_id = tier.id if tier else None
        franchise.partner_qualification_appraisal_tier_name = tier.name if tier else None
        result.append(franchise_appraisal_view(franchise))
    result.sort(key=lambda x: Decimal(x["appraisal_amount"]), reverse=True)
    db.flush()
    return result


def franchise_appraisal_view(user: User) -> dict[str, Any]:
    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "document": user.document,
        "phone": user.phone,
        "current_tier_id": user.partner_qualification_tier_id,
        "appraisal_amount": str(money(Decimal(str(user.partner_qualification_appraisal_amount or 0)))),
        "appraisal_tier_id": user.partner_qualification_appraisal_tier_id,
        "appraisal_tier_name": user.partner_qualification_appraisal_tier_name,
    }


def list_franchise_appraisal_rows(db: Session, user: User) -> list[dict[str, Any]]:
    return [franchise_appraisal_view(u) for u in _franchise_users(db, user.organization_id)]


def apply_appraisal(
    db: Session,
    actor: User,
    date_init: date,
    date_final: date,
) -> dict[str, Any]:
    if date_final < date_init:
        raise HTTPException(status_code=422, detail="Data final deve ser igual ou posterior à inicial")
    run_appraisal_preview(db, actor.organization_id, date_init, date_final)
    promoted = 0
    for franchise in _franchise_users(db, actor.organization_id):
        franchise.partner_qualification_tier_id = franchise.partner_qualification_appraisal_tier_id
        promoted += 1
    run = PartnerQualificationAppraisalRun(
        organization_id=actor.organization_id,
        date_init=date_init,
        date_final=date_final,
        applied_by_id=actor.id,
    )
    db.add(run)
    db.flush()
    return {
        "run_id": run.id,
        "date_init": date_init.isoformat(),
        "date_final": date_final.isoformat(),
        "franchises_updated": promoted,
    }


def list_appraisal_history(db: Session, user: User, limit: int = 30) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(PartnerQualificationAppraisalRun)
        .where(PartnerQualificationAppraisalRun.organization_id == user.organization_id)
        .order_by(PartnerQualificationAppraisalRun.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "date_init": row.date_init.isoformat(),
            "date_final": row.date_final.isoformat(),
            "applied_by_id": row.applied_by_id,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def latest_appraisal_history(db: Session, organization_id: str) -> dict[str, Any] | None:
    row = db.scalar(
        select(PartnerQualificationAppraisalRun)
        .where(PartnerQualificationAppraisalRun.organization_id == organization_id)
        .order_by(PartnerQualificationAppraisalRun.created_at.desc())
        .limit(1)
    )
    if not row:
        return None
    return {
        "date_init": row.date_init.isoformat(),
        "date_final": row.date_final.isoformat(),
        "created_at": row.created_at,
    }


def import_legacy_tiers(
    db: Session,
    organization_id: str,
    *,
    sql_path: Path | None = None,
) -> dict[str, int]:
    path = sql_path or DEFAULT_LEGACY_SQL
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"SQL legado não encontrado: {path}")
    rows = load_table(path, "affiliates_qualification")
    created = updated = 0
    for row in rows:
        try:
            legacy_id = int(row.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if legacy_id <= 0:
            continue
        existing = db.scalar(
            select(PartnerQualificationTier).where(
                PartnerQualificationTier.organization_id == organization_id,
                PartnerQualificationTier.legacy_id == legacy_id,
            )
        )
        payload = {
            "name": str(row.get("name") or f"Faixa {legacy_id}"),
            "price_init": float(row.get("price_init") or 0),
            "price_final": float(row.get("price_final") or 0),
            "price_bonus": float(row.get("price_bonus") or 0),
            "sort_order": int(row.get("order") or 999),
            "active": bool(int(row.get("active") or 0)),
        }
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(
                PartnerQualificationTier(
                    organization_id=organization_id,
                    legacy_id=legacy_id,
                    **payload,
                )
            )
            created += 1
    db.flush()
    return {"created": created, "updated": updated, "total_legacy": len(rows)}
