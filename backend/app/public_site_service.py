"""Serviços do site público LETTER — captura de leads, simuladores e preview MMN."""

import hashlib
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.finops_engine import money, pool_public_simulation
from app.flash_capital_params import get_active_flash_simulation_params
from app.bacen_scr_service import attach_scr_to_lead, bacen_scr_client
from app.core.security import hash_password
from app.identity_service import create_session_tokens
from app.models import CommissionRule, Lead, NetworkNode, Organization, Quota, Role, User
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


def mask_person_name(name: str) -> str:
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "Indicador"
    if len(parts) == 1:
        return f"{parts[0][:1].upper()}***"
    return f"{parts[0]} {parts[-1][:1].upper()}."


def lookup_referral_code(db: Session, organization_id: str, referral_code: str | None) -> NetworkNode | None:
    if not referral_code or not referral_code.strip():
        return None
    code = referral_code.strip().upper()
    return db.scalar(
        select(NetworkNode).where(
            NetworkNode.organization_id == organization_id,
            NetworkNode.referral_code == code,
            NetworkNode.status == "ACTIVE",
        )
    )


def preview_referral_code(db: Session, referral_code: str) -> dict:
    org = headquarters_org(db)
    node = lookup_referral_code(db, org.id, referral_code)
    if not node:
        return {
            "valid": False,
            "referral_code": referral_code.strip().upper(),
            "referrer_name": None,
            "message": "Código de indicação não encontrado.",
        }
    referrer = db.get(User, node.user_id)
    return {
        "valid": True,
        "referral_code": node.referral_code,
        "referrer_name": mask_person_name(referrer.name) if referrer else None,
        "message": None,
    }


def register_public_client(
    db: Session,
    *,
    name: str,
    email: str,
    phone: str,
    password: str,
    document: str | None = None,
    referral_code: str | None = None,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict:
    org = headquarters_org(db)
    normalized_email = email.strip().lower()
    if db.scalar(select(User).where(User.email == normalized_email)):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    normalized_document = document.strip() if document else None
    if normalized_document and db.scalar(select(User).where(User.document == normalized_document)):
        raise HTTPException(status_code=409, detail="Documento já cadastrado")

    referrer_node = lookup_referral_code(db, org.id, referral_code)
    if referral_code and referral_code.strip() and not referrer_node:
        raise HTTPException(status_code=422, detail="Código de indicação inválido")

    referrer_user_id = referrer_node.user_id if referrer_node else None
    user = User(
        organization_id=org.id,
        name=name.strip(),
        email=normalized_email,
        phone=phone.strip(),
        document=normalized_document,
        password_hash=hash_password(password),
        role=Role.CLIENT,
        referred_by_user_id=referrer_user_id,
    )
    db.add(user)
    db.flush()

    lead_source = "CLIENT_SELF_REGISTER"
    if referrer_node:
        lead_source = f"CLIENT_SELF_REGISTER:REF:{referrer_node.referral_code}"
    lead = Lead(
        organization_id=org.id,
        owner_id=referrer_user_id,
        name=user.name,
        document=user.document,
        phone=user.phone or phone.strip(),
        product_interest="PLATFORM",
        status="REGISTERED",
        source=lead_source,
    )
    db.add(lead)
    db.flush()

    access, refresh, _ = create_session_tokens(db, user, user_agent, ip_address)
    referrer = db.get(User, referrer_user_id) if referrer_user_id else None
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": user,
        "referrer": {
            "valid": bool(referrer_node),
            "referral_code": referrer_node.referral_code if referrer_node else None,
            "referrer_name": mask_person_name(referrer.name) if referrer else None,
        } if referrer_node else None,
        "lead_id": lead.id,
    }


def capture_public_lead(
    db: Session,
    *,
    razao_social: str,
    whatsapp: str,
    produto: str,
    valor_base: Decimal | None = None,
    autorizacao_scr_bacen: bool = False,
    document: str | None = None,
    referral_code: str | None = None,
) -> dict:
    if not autorizacao_scr_bacen:
        raise HTTPException(422, "Autorização SCR/Registrato é obrigatória")
    org = headquarters_org(db)
    referrer_node = lookup_referral_code(db, org.id, referral_code)
    referrer_user_id = referrer_node.user_id if referrer_node else None
    if referral_code and referral_code.strip() and not referrer_node:
        raise HTTPException(status_code=422, detail="Código de indicação inválido")
    if not referrer_user_id:
        owner = db.scalar(
            select(User).where(User.organization_id == org.id, User.active.is_(True)).order_by(User.created_at)
        )
        referrer_user_id = owner.id if owner else None
    product_map = {"flash": "FLASH_CREDIT", "sdc": "SDC", "quitcon": "QUITCON"}
    lead_source = "SITE_BACEN_AUTHORIZED"
    if referrer_node:
        lead_source = f"SITE_BACEN_AUTHORIZED:REF:{referrer_node.referral_code}"
    lead = Lead(
        organization_id=org.id,
        owner_id=referrer_user_id,
        name=razao_social.strip(),
        document=document.strip() if document else None,
        phone=whatsapp.strip(),
        product_interest=product_map.get(produto.lower(), produto.upper()),
        status="NEW",
        source=lead_source,
    )
    db.add(lead)
    db.flush()

    scr = bacen_scr_client.consult(
        company_name=razao_social.strip(),
        document=document,
        authorization_accepted=autorizacao_scr_bacen,
    )
    attach_scr_to_lead(lead, scr)

    lead_hash = hashlib.md5(f"{razao_social}-{whatsapp}".encode()).hexdigest()
    return {
        "status": "LEAD_LOGGED_AND_BACEN_AUTHORIZED",
        "id": lead.id,
        "lead_hash": lead_hash,
        "produto": lead.product_interest,
        "valor_base": str(valor_base) if valor_base is not None else None,
        "scr_status": lead.scr_status,
        "scr_reference": lead.scr_reference,
        "scr_mode": scr.mode,
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
