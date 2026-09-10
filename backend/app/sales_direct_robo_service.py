"""Venda Direta Robô — wizard admin sobre o motor Esteira 2 (Paulo / LETTER)."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commission_attribution import apply_proposal_attribution
from app.marketplace_service import esteira2_nina_curated_match
from app.models import Lead, Proposal, Quota, User
from app.services import reserve_quota

SOURCE = "VENDA_DIRETA_ROBO"
PRODUCT = "MARKETPLACE"
RESERVE_TTL_MINUTES = 60


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _validate_document(person_type: str, document: str | None) -> str:
    digits = _digits(document)
    if person_type == "PJ":
        if len(digits) != 14:
            raise HTTPException(status_code=422, detail="CNPJ inválido (informe 14 dígitos).")
    else:
        if len(digits) != 11:
            raise HTTPException(status_code=422, detail="CPF inválido (informe 11 dígitos).")
    return digits


def search_cotas(
    db: Session,
    user: User,
    *,
    name: str,
    email: str,
    phone: str,
    person_type: str,
    document: str | None,
    target_amount: Decimal,
    target_entrada: Decimal,
    category: str,
    monthly_income: Decimal,
    monthly_commitment: Decimal,
    asset_value: Decimal,
    asset_year: int,
    has_credit_restriction: bool,
    asset_is_zero_km: bool,
    zipcode: str | None = None,
    street: str | None = None,
    number: str | None = None,
    neighborhood: str | None = None,
    city: str | None = None,
    uf: str | None = None,
) -> dict:
    """Passo 1: cria pré-cadastro (Lead) e roda o robô Esteira 2. Sem match → apaga o lead."""
    person = (person_type or "PF").upper()
    if person not in {"PF", "PJ"}:
        raise HTTPException(status_code=422, detail="Tipo deve ser PF ou PJ.")
    doc = _validate_document(person, document)
    if not (email or "").strip() or "@" not in email:
        raise HTTPException(status_code=422, detail="E-mail inválido.")
    if len((phone or "").strip()) < 8:
        raise HTTPException(status_code=422, detail="Telefone/WhatsApp obrigatório.")

    match = esteira2_nina_curated_match(
        db,
        user,
        target_amount=target_amount,
        category=category,
        asset_year=asset_year,
        monthly_income=monthly_income,
        monthly_commitment=monthly_commitment,
        asset_value=asset_value,
        has_credit_restriction=has_credit_restriction,
        asset_is_zero_km=asset_is_zero_km,
        target_entrada=target_entrada,
    )

    if not match.get("eligible") or not (
        match.get("credit_matches") or match.get("entrada_matches") or match.get("matches")
    ):
        raise HTTPException(
            status_code=404,
            detail=match.get("message")
            or "Desculpe, não encontramos nenhuma cota com esses filtros. Ajuste crédito/entrada e tente de novo.",
        )

    profile_snapshot = {
        "email": email.strip(),
        "person_type": person,
        "target_amount": str(target_amount),
        "target_entrada": str(target_entrada),
        "category": category,
        "monthly_income": str(monthly_income),
        "monthly_commitment": str(monthly_commitment),
        "asset_value": str(asset_value),
        "asset_year": asset_year,
        "has_credit_restriction": has_credit_restriction,
        "asset_is_zero_km": asset_is_zero_km,
        "address": {
            "zipcode": zipcode,
            "street": street,
            "number": number,
            "neighborhood": neighborhood,
            "city": city,
            "uf": uf,
        },
    }

    lead = Lead(
        organization_id=user.organization_id,
        owner_id=user.id,
        name=name.strip(),
        document=doc,
        phone=phone.strip(),
        product_interest=PRODUCT,
        status="QUALIFIED",
        source=SOURCE,
        scr_detail_json=json.dumps({"venda_direta_robo": profile_snapshot}, ensure_ascii=False),
    )
    db.add(lead)
    db.flush()

    return {
        "lead_id": lead.id,
        "client_name": lead.name,
        "esteira": match["esteira"],
        "eligible": True,
        "blockers": match.get("blockers") or [],
        "matches": match.get("matches") or [],
        "credit_matches": match.get("credit_matches") or [],
        "entrada_matches": match.get("entrada_matches") or [],
        "band_percent": match.get("band_percent") or "5",
        "message": match.get("message") or "Opções encontradas pelo robô. Escolha uma cota para confirmar.",
    }


def confirm_cota(
    db: Session,
    user: User,
    *,
    lead_id: str,
    quota_ids: list[str],
    match_lane: str | None = None,
) -> dict:
    """Passo 2: confirma sugestão do robô → proposta MARKETPLACE + trava 60 min nas cotas."""
    if not quota_ids:
        raise HTTPException(status_code=422, detail="Informe as cotas escolhidas (quota_ids).")
    ids = list(dict.fromkeys(quota_ids))

    lead = db.scalar(
        select(Lead).where(Lead.id == lead_id, Lead.organization_id == user.organization_id)
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Pré-cadastro não encontrado.")
    if lead.source != SOURCE:
        raise HTTPException(status_code=422, detail="Lead não originado pela Venda Direta Robô.")

    existing = db.scalar(
        select(Proposal).where(
            Proposal.lead_id == lead.id,
            Proposal.organization_id == user.organization_id,
            Proposal.product == PRODUCT,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Este pré-cadastro já possui proposta Marketplace.")

    quotas = list(
        db.scalars(
            select(Quota).where(Quota.id.in_(ids), Quota.organization_id == user.organization_id)
        )
    )
    if len(quotas) != len(ids):
        raise HTTPException(status_code=404, detail="Uma ou mais cotas não foram encontradas.")

    admin_ids = {q.administrator_id for q in quotas}
    if len(admin_ids) > 1:
        raise HTTPException(status_code=422, detail="Combinação só é permitida na mesma administradora.")

    snapshot = {}
    try:
        detail = json.loads(lead.scr_detail_json or "{}")
        snapshot = detail.get("venda_direta_robo") or {}
    except json.JSONDecodeError:
        snapshot = {}

    total_credit = sum((Decimal(str(q.credit_value or 0)) for q in quotas), Decimal("0"))
    total_entrada = sum((Decimal(str(q.premium_value or 0)) for q in quotas), Decimal("0"))

    proposal = Proposal(
        organization_id=user.organization_id,
        lead_id=lead.id,
        product=PRODUCT,
        requested_amount=total_credit,
        status="SUBMITTED",
        terms_json=json.dumps(
            {
                "channel": SOURCE,
                "match_lane": match_lane,
                "quota_ids": ids,
                "total_credit": str(total_credit),
                "total_entrada_base": str(total_entrada),
                "client_email": snapshot.get("email"),
                "person_type": snapshot.get("person_type"),
                "filters": snapshot,
                "quotas": [
                    {
                        "quota_id": q.id,
                        "group_code": q.group_code,
                        "quota_code": q.quota_code,
                        "credit_value": str(q.credit_value),
                        "premium_value": str(q.premium_value),
                        "installment_value": str(q.installment_value or 0),
                        "supplier_source": q.supplier_source,
                        "administrator_id": q.administrator_id,
                    }
                    for q in quotas
                ],
            },
            ensure_ascii=False,
        ),
        sale_channel="PARTNER_OFFICE",
        served_by_user_id=user.id,
        created_by_user_id=user.id,
    )
    db.add(proposal)
    db.flush()
    apply_proposal_attribution(
        db,
        user,
        proposal,
        client_user_id=None,
        sale_channel="PARTNER_OFFICE",
        served_by_user_id=user.id,
        lead=lead,
    )

    reservations = []
    for quota in quotas:
        reservation = reserve_quota(db, user, quota, proposal.id, RESERVE_TTL_MINUTES)
        reservations.append(reservation)
    db.flush()

    lead.status = "PROPOSAL"
    db.flush()

    return {
        "lead_id": lead.id,
        "proposal_id": proposal.id,
        "quota_ids": ids,
        "reservation_ids": [r.id for r in reservations],
        "requested_amount": str(total_credit),
        "message": (
            f"Venda gravada. Cotas travadas por {RESERVE_TTL_MINUTES} min. "
            "Finalize o cálculo e o contrato em Propostas."
        ),
    }
