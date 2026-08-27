"""Serviços do site público LETTER — captura de leads, simuladores e preview MMN."""

import hashlib
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.finops_engine import money, pool_public_simulation
from app.flash_capital_params import get_active_flash_simulation_params
from app.models import CommissionRule, Lead, Organization, Quota, User
from app.product_service import build_sdc_simulation_output

HUNDRED = Decimal("100")

MMN_BASE_KEYS = {
    "NET_PAYOUT": "net_payout",
    "PLATFORM_FEE": "platform_fee",
    "INTERMEDIATION_FEE": "intermediation_fee",
    "PRINCIPAL": "principal",
    "CAPITAL_COMMISSION": "capital_commission",
    "LETTER_FEE": "platform_fee",
}


def headquarters_org(db: Session) -> Organization:
    org = db.scalar(
        select(Organization).where(Organization.kind == "HEADQUARTERS").order_by(Organization.created_at)
    )
    if not org:
        org = db.scalar(select(Organization).order_by(Organization.created_at))
    if not org:
        raise HTTPException(503, "Organização matriz não configurada")
    return org


def preview_mmn(db: Session, organization_id: str, product: str, bases: dict[str, Decimal]) -> dict:
    rule = db.scalar(
        select(CommissionRule).where(
            CommissionRule.organization_id == organization_id,
            CommissionRule.product == product,
            CommissionRule.commission_type == "SALES",
            CommissionRule.active.is_(True),
        ).order_by(CommissionRule.version.desc())
    )
    if not rule:
        return {
            "configured": False,
            "product": product,
            "message": "Regra MMN ativa não configurada para este produto.",
        }
    base_key = MMN_BASE_KEYS.get(rule.base_type.upper(), rule.base_type.lower())
    raw = bases.get(base_key)
    if raw is None:
        for fallback in ("net_payout", "intermediation_fee", "platform_fee", "principal"):
            if fallback in bases:
                raw = bases[fallback]
                base_key = fallback
                break
    if raw is None or raw <= 0:
        return {
            "configured": True,
            "product": product,
            "base_type": rule.base_type,
            "pool_rate_percent": str(rule.pool_rate_percent),
            "message": "Base de comissão indisponível para esta simulação.",
        }
    pool_rate = Decimal(str(rule.pool_rate_percent))
    commission_pool = money(raw * pool_rate / HUNDRED)
    platform_fee = bases.get("platform_fee")
    holding_retained = None
    if platform_fee is not None:
        holding_retained = str(money(max(Decimal("0"), platform_fee - commission_pool)))
    return {
        "configured": True,
        "product": product,
        "rule_id": rule.id,
        "base_type": rule.base_type,
        "calculation_base_key": base_key,
        "calculation_base": str(money(raw)),
        "pool_rate_percent": str(pool_rate),
        "commission_pool": str(commission_pool),
        "holding_retained_from_fee": holding_retained,
        "levels_json": rule.levels_json,
        "note": "Preview com base na regra MMN ativa da plataforma (tipo SALES).",
    }


def capture_public_lead(
    db: Session,
    *,
    razao_social: str,
    whatsapp: str,
    produto: str,
    valor_base: Decimal | None = None,
    autorizacao_scr_bacen: bool = False,
) -> dict:
    if not autorizacao_scr_bacen:
        raise HTTPException(422, "Autorização SCR/Registrato é obrigatória")
    org = headquarters_org(db)
    owner = db.scalar(
        select(User).where(User.organization_id == org.id, User.active.is_(True)).order_by(User.created_at)
    )
    product_map = {"flash": "FLASH_CREDIT", "sdc": "SDC", "quitcon": "QUITCON"}
    lead = Lead(
        organization_id=org.id,
        owner_id=owner.id if owner else None,
        name=razao_social.strip(),
        phone=whatsapp.strip(),
        product_interest=product_map.get(produto.lower(), produto.upper()),
        status="NEW",
        source="SITE_BACEN_AUTHORIZED",
    )
    db.add(lead)
    db.flush()
    lead_hash = hashlib.md5(f"{razao_social}-{whatsapp}".encode()).hexdigest()
    return {
        "status": "LEAD_LOGGED_AND_BACEN_AUTHORIZED",
        "id": lead.id,
        "lead_hash": lead_hash,
        "produto": lead.product_interest,
        "valor_base": str(valor_base) if valor_base is not None else None,
    }


def list_public_quotas(db: Session) -> list[dict]:
    org = headquarters_org(db)
    rows = db.scalars(
        select(Quota).where(
            Quota.organization_id == org.id,
            Quota.status == "AVAILABLE",
        ).order_by(Quota.category, Quota.credit_value.desc())
    )
    return [
        {
            "id": q.id,
            "group_code": q.group_code,
            "quota_code": q.quota_code,
            "category": q.category,
            "credit_value": str(money(Decimal(str(q.credit_value)))),
            "status": q.status,
        }
        for q in rows
    ]


def simulate_flash_pool_public(
    db: Session,
    asset_value: Decimal,
    requested_amount: Decimal | None,
) -> dict:
    org = headquarters_org(db)
    params = get_active_flash_simulation_params(db, org.id)
    retail = Decimal(params["retail_rate_monthly"])
    result = pool_public_simulation(asset_value, requested_amount, retail_monthly=retail)
    bases = {
        "net_payout": Decimal(result["net_payout"]),
        "platform_fee": Decimal(result["platform_fee"]),
        "principal": Decimal(result["principal"]),
    }
    result["mmn"] = preview_mmn(db, org.id, "FLASH_CREDIT", bases)
    result["retail_rate_monthly"] = params["retail_rate_monthly"]
    return result


def simulate_sdc_public(
    db: Session,
    quota_ids: list[str],
    requested_amount: Decimal,
    duration_months: int,
    capital_source: str = "POOL",
) -> dict:
    org = headquarters_org(db)
    quotas = list(
        db.scalars(
            select(Quota).where(
                Quota.organization_id == org.id,
                Quota.id.in_(quota_ids),
                Quota.status == "AVAILABLE",
            )
        )
    )
    if len(quotas) != len(quota_ids):
        raise HTTPException(422, "Uma ou mais cotas não estão disponíveis")
    formula_version, input_data, output_data = build_sdc_simulation_output(
        quotas, float(requested_amount), duration_months, capital_source,
    )
    bases = {
        "principal": Decimal(output_data["principal"]),
        "intermediation_fee": Decimal(output_data["intermediation_fee"]),
        "capital_commission": Decimal(output_data["capital_commission"]),
    }
    return {
        "formula_version": formula_version,
        "input": input_data,
        "output": output_data,
        "mmn": preview_mmn(db, org.id, "SDC", bases),
        "execution": "SIMULATION_ONLY",
    }
