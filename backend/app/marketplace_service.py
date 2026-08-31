"""Marketplace cartas contempladas — Esteira 1 (escolha do parceiro) e Esteira 2 (curadoria Nina)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Administrator, Quota, User
from app.nina_bi_service import rank_quota_combinations
from app.quota_inventory_service import run_nina_quota_scan
from app.services import money, utcnow

MAX_VEHICLE_AGE_YEARS = 10
MAX_COMMITMENT_PERCENT = Decimal("30")


def _profile_blockers(
    *,
    category: str,
    credit_value: Decimal,
    asset_value: Decimal,
    asset_year: int,
    monthly_income: Decimal,
    monthly_commitment: Decimal,
    target_amount: Decimal | None = None,
) -> list[str]:
    blockers: list[str] = []
    check_amount = target_amount or credit_value

    if asset_value <= 0:
        blockers.append("Informe o valor de avaliação do bem.")
    elif check_amount > asset_value:
        blockers.append(
            f"Crédito alvo (R$ {money(check_amount)}) excede o valor do bem (R$ {money(asset_value)})."
        )

    if monthly_income <= 0:
        blockers.append("Informe a renda mensal do cliente.")
    else:
        commitment_pct = (monthly_commitment / monthly_income) * Decimal("100")
        if commitment_pct > MAX_COMMITMENT_PERCENT:
            blockers.append(
                f"Comprometimento de renda ({commitment_pct:.1f}%) acima do limite de 30%."
            )

    if category == "VEHICLE":
        age = datetime.now(UTC).year - int(asset_year)
        if age > MAX_VEHICLE_AGE_YEARS:
            blockers.append(
                f"Bem com {age} anos — acima do limite de {MAX_VEHICLE_AGE_YEARS} anos para cartas de veículo."
            )

    return blockers


def _quota_summary(quota: Quota, admin: Administrator | None) -> dict:
    return {
        "quota_id": quota.id,
        "group_code": quota.group_code,
        "quota_code": quota.quota_code,
        "category": quota.category,
        "credit_value": str(money(Decimal(str(quota.credit_value)))),
        "premium_value": str(money(Decimal(str(quota.premium_value)))),
        "installment_due_date": quota.installment_due_date.isoformat() if quota.installment_due_date else None,
        "administrator_name": admin.name if admin else None,
        "status": quota.status,
        "nina_scan_status": quota.nina_scan_status,
    }


def _rank_alternatives(
    db: Session,
    user: User,
    *,
    target_amount: Decimal,
    category: str,
    asset_value: Decimal,
    asset_year: int,
    monthly_income: Decimal,
    monthly_commitment: Decimal,
    exclude_quota_id: str | None = None,
    limit: int = 5,
) -> list[dict]:
    ranked = rank_quota_combinations(db, user, target_amount, category, limit=limit * 3)
    alternatives: list[dict] = []
    for item in ranked:
        if exclude_quota_id and exclude_quota_id in item["quota_ids"]:
            continue
        quotas = list(db.scalars(select(Quota).where(Quota.id.in_(item["quota_ids"]))))
        if not quotas:
            continue
        total_credit = Decimal(str(item["total_credit"]))
        blockers = _profile_blockers(
            category=category,
            credit_value=total_credit,
            asset_value=asset_value,
            asset_year=asset_year,
            monthly_income=monthly_income,
            monthly_commitment=monthly_commitment,
            target_amount=target_amount,
        )
        if blockers:
            continue
        admin = db.get(Administrator, item["administrator_id"])
        alternatives.append(
            {
                **item,
                "administrator_name": admin.name if admin else None,
                "quotas": [_quota_summary(q, db.get(Administrator, q.administrator_id)) for q in quotas],
                "message": "Combinação compatível com o perfil do cliente.",
            }
        )
        if len(alternatives) >= limit:
            break
    return alternatives


def esteira1_partner_select(
    db: Session,
    user: User,
    *,
    quota_id: str,
    monthly_income: Decimal,
    monthly_commitment: Decimal,
    asset_value: Decimal,
    asset_year: int,
) -> dict:
    """Esteira 1: parceiro escolhe a carta → Nina varre → sugere alternativas se perfil não couber."""
    quota = db.scalar(select(Quota).where(Quota.id == quota_id, Quota.organization_id == user.organization_id))
    if not quota:
        raise HTTPException(status_code=404, detail="Cota não encontrada.")
    if quota.status not in {"AVAILABLE", "RESERVED"}:
        raise HTTPException(status_code=409, detail="Cota indisponível para análise.")

    admin = db.get(Administrator, quota.administrator_id)
    if quota.nina_scan_status != "CLEARED":
        try:
            run_nina_quota_scan(db, user, quota)
        except HTTPException as exc:
            return {
                "esteira": "SELF_SELECT",
                "eligible": False,
                "quota": _quota_summary(quota, admin),
                "blockers": [str(exc.detail)],
                "alternatives": _rank_alternatives(
                    db,
                    user,
                    target_amount=Decimal(str(quota.credit_value)),
                    category=quota.category,
                    asset_value=asset_value,
                    asset_year=asset_year,
                    monthly_income=monthly_income,
                    monthly_commitment=monthly_commitment,
                    exclude_quota_id=quota.id,
                ),
                "message": "Varredura cadastral Nina reprovou a cota escolhida.",
            }

    credit = Decimal(str(quota.credit_value))
    blockers = _profile_blockers(
        category=quota.category,
        credit_value=credit,
        asset_value=asset_value,
        asset_year=asset_year,
        monthly_income=monthly_income,
        monthly_commitment=monthly_commitment,
    )

    eligible = len(blockers) == 0
    alternatives = []
    if not eligible:
        alternatives = _rank_alternatives(
            db,
            user,
            target_amount=credit,
            category=quota.category,
            asset_value=asset_value,
            asset_year=asset_year,
            monthly_income=monthly_income,
            monthly_commitment=monthly_commitment,
            exclude_quota_id=quota.id,
        )

    return {
        "esteira": "SELF_SELECT",
        "eligible": eligible,
        "quota": _quota_summary(quota, admin),
        "blockers": blockers,
        "alternatives": alternatives,
        "message": (
            "Cliente apto para a carta escolhida. Prossiga com trava de 60 min e proposta."
            if eligible
            else "Cliente sem perfil para esta carta. Nina indicou alternativas compatíveis."
        ),
    }


def esteira2_nina_curated_match(
    db: Session,
    user: User,
    *,
    target_amount: Decimal,
    category: str,
    asset_year: int,
    monthly_income: Decimal,
    monthly_commitment: Decimal,
    asset_value: Decimal,
    limit: int = 8,
) -> dict:
    """Esteira 2: cliente/parceiro informa valor e ano do bem → Nina entrega opções."""
    if category not in {"REAL_ESTATE", "VEHICLE"}:
        raise HTTPException(status_code=422, detail="Categoria deve ser REAL_ESTATE ou VEHICLE.")

    profile_blockers = _profile_blockers(
        category=category,
        credit_value=target_amount,
        asset_value=asset_value,
        asset_year=asset_year,
        monthly_income=monthly_income,
        monthly_commitment=monthly_commitment,
        target_amount=target_amount,
    )
    if profile_blockers:
        return {
            "esteira": "NINA_CURATED",
            "eligible": False,
            "blockers": profile_blockers,
            "matches": [],
            "message": "Perfil do cliente não permite matching automático. Ajuste renda, bem ou valor alvo.",
        }

    matches = _rank_alternatives(
        db,
        user,
        target_amount=target_amount,
        category=category,
        asset_value=asset_value,
        asset_year=asset_year,
        monthly_income=monthly_income,
        monthly_commitment=monthly_commitment,
        limit=limit,
    )

    return {
        "esteira": "NINA_CURATED",
        "eligible": bool(matches),
        "blockers": [] if matches else ["Nenhuma combinação disponível no inventário para o perfil informado."],
        "matches": matches,
        "message": (
            f"Nina encontrou {len(matches)} opção(ões) para crédito alvo de R$ {money(target_amount)}."
            if matches
            else "Sem opções no inventário — cadastre novas cotas ou ajuste o valor alvo."
        ),
    }
