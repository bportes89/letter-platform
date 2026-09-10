"""Marketplace cartas contempladas — Esteira 1 (escolha do parceiro) e Esteira 2 (curadoria Nina).

A análise usa as regras cadastradas em Administrator.rules_json (painel interno).
Bacen não é chamado no matching — só atualiza rules_json via sync manual/cron.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.administrator_service import APPROVED_STATUSES, parse_rules
from app.models import Administrator, Quota, User
from app.nina_bi_service import rank_quota_combinations
from app.quota_inventory_service import run_nina_quota_scan
from app.services import money

DEFAULT_INCOME_RATIO = Decimal("3")


def _quota_summary(quota: Quota, admin: Administrator | None) -> dict:
    return {
        "quota_id": quota.id,
        "group_code": quota.group_code,
        "quota_code": quota.quota_code,
        "category": quota.category,
        "credit_value": str(money(Decimal(str(quota.credit_value)))),
        "premium_value": str(money(Decimal(str(quota.premium_value)))),
        "installment_value": str(money(Decimal(str(quota.installment_value or 0)))),
        "installment_due_date": quota.installment_due_date.isoformat() if quota.installment_due_date else None,
        "administrator_name": admin.name if admin else None,
        "status": quota.status,
        "nina_scan_status": quota.nina_scan_status,
    }


def _installment_total(quotas: list[Quota]) -> Decimal:
    return money(sum((Decimal(str(q.installment_value or 0)) for q in quotas), Decimal("0")))


def admin_profile_blockers(
    admin: Administrator | None,
    *,
    category: str,
    asset_year: int,
    asset_is_zero_km: bool,
    has_credit_restriction: bool,
    credit_total: Decimal,
    installment_total: Decimal,
    monthly_income: Decimal,
    asset_value: Decimal,
    target_amount: Decimal | None = None,
    combo_size: int = 1,
) -> list[str]:
    """Bloqueios a partir das regras internas da administradora + perfil do cliente."""
    blockers: list[str] = []
    check_amount = target_amount or credit_total

    if asset_value <= 0:
        blockers.append("Informe o valor de avaliação do bem.")
    elif check_amount > asset_value:
        blockers.append(
            f"Crédito alvo (R$ {money(check_amount)}) excede o valor do bem (R$ {money(asset_value)})."
        )

    if monthly_income <= 0:
        blockers.append("Informe a renda mensal comprovada do cliente.")

    if not admin:
        blockers.append("Administradora da cota não encontrada.")
        return blockers

    if admin.authorization_status not in APPROVED_STATUSES:
        blockers.append(f"Administradora {admin.name} com status {admin.authorization_status}.")

    rules = parse_rules(admin.rules_json)
    products = rules.get("products_enabled") or []
    if products and "MARKETPLACE" not in products:
        blockers.append(f"Administradora {admin.name} sem produto MARKETPLACE habilitado nas regras internas.")

    allowed_categories = rules.get("allowed_categories") or []
    if allowed_categories and category not in allowed_categories:
        blockers.append(
            f"Categoria {category} não permitida pelas regras internas de {admin.name}."
        )

    max_age = int(rules.get("max_asset_age_years") or 15)
    if asset_is_zero_km:
        if not bool(rules.get("accepts_zero_km", True)):
            blockers.append(f"Administradora {admin.name} não aceita bem zero km.")
    elif category == "VEHICLE":
        age = datetime.now(UTC).year - int(asset_year)
        if age > max_age:
            blockers.append(
                f"Bem com {age} anos — acima do limite de {max_age} anos nas regras de {admin.name}."
            )

    if has_credit_restriction and not bool(rules.get("accepts_dirty_name", False)):
        blockers.append(
            f"Administradora {admin.name} não aceita cliente com restrição SPC/Serasa (regras internas)."
        )

    ratio = Decimal(str(rules.get("min_income_to_installment_ratio") or DEFAULT_INCOME_RATIO))
    if installment_total > 0 and monthly_income > 0:
        max_installment = money(monthly_income / ratio)
        if installment_total > max_installment:
            blockers.append(
                f"Renda comprovada (R$ {money(monthly_income)}) precisa cobrir no mínimo "
                f"{ratio:g}× a parcela (R$ {installment_total}); teto da parcela: R$ {max_installment}."
            )

    credit_rules = rules.get("credit_utilization_rules") if isinstance(rules.get("credit_utilization_rules"), dict) else {}
    max_credit = credit_rules.get("max_credit_per_operation_brl")
    if max_credit and credit_total > Decimal(str(max_credit)):
        blockers.append(
            f"Crédito (R$ {money(credit_total)}) excede o teto interno de {admin.name} (R$ {money(Decimal(str(max_credit)))})."
        )
    max_combined = credit_rules.get("max_combined_quotas")
    if max_combined and combo_size > int(max_combined):
        blockers.append(
            f"Combinação de {combo_size} cotas excede o máximo de {max_combined} nas regras de {admin.name}."
        )

    return blockers


def _rank_alternatives(
    db: Session,
    user: User,
    *,
    target_amount: Decimal,
    category: str,
    asset_value: Decimal,
    asset_year: int,
    monthly_income: Decimal,
    has_credit_restriction: bool,
    asset_is_zero_km: bool,
    exclude_quota_id: str | None = None,
    limit: int = 5,
) -> list[dict]:
    ranked = rank_quota_combinations(db, user, target_amount, category, limit=limit * 4)
    alternatives: list[dict] = []
    for item in ranked:
        if exclude_quota_id and exclude_quota_id in item["quota_ids"]:
            continue
        quotas = list(db.scalars(select(Quota).where(Quota.id.in_(item["quota_ids"]))))
        if not quotas:
            continue
        total_credit = Decimal(str(item["total_credit"]))
        admin = db.get(Administrator, item["administrator_id"])
        blockers = admin_profile_blockers(
            admin,
            category=category,
            asset_year=asset_year,
            asset_is_zero_km=asset_is_zero_km,
            has_credit_restriction=has_credit_restriction,
            credit_total=total_credit,
            installment_total=_installment_total(quotas),
            monthly_income=monthly_income,
            asset_value=asset_value,
            target_amount=target_amount,
            combo_size=len(quotas),
        )
        if blockers:
            continue
        alternatives.append(
            {
                **item,
                "administrator_name": admin.name if admin else None,
                "quotas": [_quota_summary(q, db.get(Administrator, q.administrator_id)) for q in quotas],
                "message": "Combinação compatível com o perfil e as regras internas da administradora.",
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
    has_credit_restriction: bool = False,
    asset_is_zero_km: bool = False,
) -> dict:
    """Esteira 1: parceiro escolhe a carta → Nina varre → sugere alternativas se perfil não couber."""
    del monthly_commitment  # mantido no payload por compatibilidade; filtro operacional é renda × parcela
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
                    has_credit_restriction=has_credit_restriction,
                    asset_is_zero_km=asset_is_zero_km,
                    exclude_quota_id=quota.id,
                ),
                "message": "Varredura cadastral Nina reprovou a cota escolhida.",
            }

    credit = Decimal(str(quota.credit_value))
    blockers = admin_profile_blockers(
        admin,
        category=quota.category,
        asset_year=asset_year,
        asset_is_zero_km=asset_is_zero_km,
        has_credit_restriction=has_credit_restriction,
        credit_total=credit,
        installment_total=_installment_total([quota]),
        monthly_income=monthly_income,
        asset_value=asset_value,
        combo_size=1,
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
            has_credit_restriction=has_credit_restriction,
            asset_is_zero_km=asset_is_zero_km,
            exclude_quota_id=quota.id,
        )

    return {
        "esteira": "SELF_SELECT",
        "eligible": eligible,
        "quota": _quota_summary(quota, admin),
        "blockers": blockers,
        "alternatives": alternatives,
        "message": (
            "Cliente apto para a carta escolhida pelas regras internas da administradora. Prossiga com trava de 60 min e proposta."
            if eligible
            else "Cliente sem perfil para esta carta. Nina indicou alternativas compatíveis com as regras internas."
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
    has_credit_restriction: bool = False,
    asset_is_zero_km: bool = False,
    limit: int = 8,
) -> dict:
    """Esteira 2: cliente/parceiro informa valor e ano do bem → Nina entrega opções."""
    del monthly_commitment
    if category not in {"REAL_ESTATE", "VEHICLE"}:
        raise HTTPException(status_code=422, detail="Categoria deve ser REAL_ESTATE ou VEHICLE.")

    if monthly_income <= 0:
        return {
            "esteira": "NINA_CURATED",
            "eligible": False,
            "blockers": ["Informe a renda mensal comprovada do cliente."],
            "matches": [],
            "message": "Perfil incompleto para matching.",
        }
    if asset_value <= 0:
        return {
            "esteira": "NINA_CURATED",
            "eligible": False,
            "blockers": ["Informe o valor de avaliação do bem."],
            "matches": [],
            "message": "Perfil incompleto para matching.",
        }
    if target_amount > asset_value:
        return {
            "esteira": "NINA_CURATED",
            "eligible": False,
            "blockers": [
                f"Crédito alvo (R$ {money(target_amount)}) excede o valor do bem (R$ {money(asset_value)})."
            ],
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
        has_credit_restriction=has_credit_restriction,
        asset_is_zero_km=asset_is_zero_km,
        limit=limit,
    )

    return {
        "esteira": "NINA_CURATED",
        "eligible": bool(matches),
        "blockers": [] if matches else ["Nenhuma combinação disponível no inventário para o perfil e as regras internas."],
        "matches": matches,
        "message": (
            f"Nina encontrou {len(matches)} opção(ões) para crédito alvo de R$ {money(target_amount)} "
            f"(filtro: regras da administradora + renda ≥ 3× parcela)."
            if matches
            else "Sem opções no inventário — cadastre novas cotas, ajuste a parcela/renda ou as regras da administradora."
        ),
    }
