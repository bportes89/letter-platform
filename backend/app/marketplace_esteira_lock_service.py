"""Trava 60 min + proposta MARKETPLACE após Esteira 1/2 (parceiro)."""

from __future__ import annotations

import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cadastro_service import SIT_INCOMPLETO, seed_marketplace_lifecycle
from app.commission_attribution import apply_proposal_attribution
from app.marketplace_service import esteira1_partner_select, esteira1_partner_select_combo, pricing_for_combo, pricing_for_quota
from app.models import Lead, Proposal, Quota, User
from app.quota_supplier_service import suppliers_index
from app.services import money, reserve_quota

SOURCE_ESTEIRA_1 = "MARKETPLACE_ESTEIRA_1"
SOURCE_ESTEIRA_2 = "MARKETPLACE_ESTEIRA_2"
PRODUCT = "MARKETPLACE"
RESERVE_TTL_MINUTES = 60


def _terms_after_esteira_lock(payload: dict) -> dict:
    terms = seed_marketplace_lifecycle(payload)
    life = terms.get("lifecycle") if isinstance(terms.get("lifecycle"), dict) else {}
    life["situation"] = SIT_INCOMPLETO
    terms["lifecycle"] = life
    return terms


def _assert_eligible_esteira1(
    db: Session,
    user: User,
    quota_ids: list[str],
    *,
    monthly_income: Decimal,
    monthly_commitment: Decimal,
    asset_value: Decimal,
    asset_year: int,
    has_credit_restriction: bool,
    asset_is_zero_km: bool,
) -> dict:
    common = {
        "monthly_income": monthly_income,
        "monthly_commitment": monthly_commitment,
        "asset_value": asset_value,
        "asset_year": asset_year,
        "has_credit_restriction": has_credit_restriction,
        "asset_is_zero_km": asset_is_zero_km,
    }
    if len(quota_ids) == 1:
        result = esteira1_partner_select(db, user, quota_id=quota_ids[0], **common)
    else:
        result = esteira1_partner_select_combo(db, user, quota_ids=quota_ids, **common)
    if not result.get("eligible"):
        blockers = result.get("blockers") or ["Cliente ou cota não elegível."]
        raise HTTPException(status_code=422, detail="; ".join(blockers))
    return result


def lock_quotas_with_proposal(
    db: Session,
    user: User,
    *,
    quota_ids: list[str],
    channel: str,
    profile: dict,
    match_lane: str | None = None,
    revalidate_esteira1: bool = False,
) -> dict:
    ids = list(dict.fromkeys([str(x).strip() for x in quota_ids if str(x).strip()]))
    if not ids:
        raise HTTPException(status_code=422, detail="Informe ao menos uma cota.")

    if revalidate_esteira1:
        _assert_eligible_esteira1(
            db,
            user,
            ids,
            monthly_income=Decimal(str(profile["monthly_income"])),
            monthly_commitment=Decimal(str(profile.get("monthly_commitment") or 0)),
            asset_value=Decimal(str(profile["asset_value"])),
            asset_year=int(profile.get("asset_year") or 0),
            has_credit_restriction=bool(profile.get("has_credit_restriction")),
            asset_is_zero_km=bool(profile.get("asset_is_zero_km")),
        )

    quotas = list(
        db.scalars(select(Quota).where(Quota.id.in_(ids), Quota.organization_id == user.organization_id))
    )
    if len(quotas) != len(ids):
        raise HTTPException(status_code=404, detail="Uma ou mais cotas não foram encontradas.")
    for q in quotas:
        if q.status != "AVAILABLE":
            raise HTTPException(status_code=409, detail=f"Cota indisponível ou já reservada ({q.quota_code}).")

    admin_ids = {q.administrator_id for q in quotas}
    if len(admin_ids) > 1:
        raise HTTPException(status_code=422, detail="Junção manual só permite cotas da mesma administradora.")

    suppliers = suppliers_index(db, user.organization_id)
    combo_pricing = pricing_for_combo(quotas, suppliers=suppliers)
    total_credit = Decimal(str(combo_pricing["credit"]))
    total_entrada = Decimal(str(combo_pricing["entrada_final"]))

    quota_payloads = []
    for q in quotas:
        row = pricing_for_quota(q, suppliers=suppliers)
        quota_payloads.append(
            {
                "quota_id": q.id,
                "group_code": q.group_code,
                "quota_code": q.quota_code,
                "credit_value": str(row["credit"]),
                "premium_value": str(q.premium_value),
                "entrada_final": str(row["entrada_final"]),
                "installment_value": str(q.installment_value or 0),
                "supplier_source": q.supplier_source,
                "administrator_id": q.administrator_id,
            }
        )

    snapshot = {
        **profile,
        "quota_ids": ids,
        "channel": channel,
        "match_lane": match_lane,
    }
    lead = Lead(
        organization_id=user.organization_id,
        owner_id=user.id,
        name="Cliente — completar cadastro",
        document=None,
        phone="11999999999",
        product_interest=PRODUCT,
        status="PROPOSAL",
        source=channel,
        scr_detail_json=json.dumps({channel.lower(): snapshot}, ensure_ascii=False),
    )
    db.add(lead)
    db.flush()

    proposal = Proposal(
        organization_id=user.organization_id,
        lead_id=lead.id,
        product=PRODUCT,
        requested_amount=total_credit,
        status="SUBMITTED",
        terms_json=json.dumps(
            _terms_after_esteira_lock(
                {
                    "channel": channel,
                    "match_lane": match_lane,
                    "quota_ids": ids,
                    "total_credit": str(total_credit),
                    "total_entrada": str(total_entrada),
                    "partner_user_id": user.id,
                    "porc_a_mais": "0",
                    "porc_a_mais_sellers": "0",
                    "filters": snapshot,
                    "quotas": quota_payloads,
                }
            ),
            ensure_ascii=False,
        ),
        sale_channel="PARTNER_OFFICE",
        served_by_user_id=user.id,
        created_by_user_id=user.id,
        commission_originator_id=user.id,
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

    reservations = [reserve_quota(db, user, q, proposal.id, RESERVE_TTL_MINUTES) for q in quotas]
    db.flush()

    return {
        "lead_id": lead.id,
        "proposal_id": proposal.id,
        "quota_ids": ids,
        "reservation_ids": [r.id for r in reservations],
        "requested_amount": str(money(total_credit)),
        "entrada_final": str(money(total_entrada)),
        "message": (
            f"Cota(s) travada(s) por {RESERVE_TTL_MINUTES} min. Complete o cadastro do cliente para contrato e boleto."
        ),
    }
