"""Venda Direta Robô — wizard admin sobre o motor Esteira 2 (Paulo / LETTER)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commission_attribution import apply_proposal_attribution
from app.marketplace_service import esteira2_nina_curated_match, pricing_for_combo, pricing_for_quota
from app.cadastro_service import SIT_AGUARDANDO, seed_marketplace_lifecycle, _write_lifecycle
from app.models import Administrator, Lead, Proposal, Quota, Role, User
from app.quota_supplier_service import suppliers_index
from app.services import money, reserve_quota

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


def _resolve_partner(db: Session, user: User, partner_user_id: str | None) -> User | None:
    if not partner_user_id:
        return None
    partner = db.scalar(
        select(User).where(
            User.id == partner_user_id,
            User.organization_id == user.organization_id,
            User.active.is_(True),
            User.role.in_([Role.PARTNER, Role.MASTER_FRANCHISEE, Role.MANAGER]),
        )
    )
    if not partner:
        raise HTTPException(status_code=404, detail="Parceiro não encontrado.")
    return partner


def _affiliate_markup(db: Session, organization_id: str, partner: User | None) -> dict[str, str] | None:
    if not partner:
        return None
    from app.affiliate_markup_service import resolve_affiliate_porc_a_mais

    return resolve_affiliate_porc_a_mais(db, organization_id, partner.id, is_sdc=False)


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
    quota_category_id: str | None = None,
    client_bank_administrator_ids: list[str] | None = None,
    client_problem_bank_administrator_ids: list[str] | None = None,
    partner_user_id: str | None = None,
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

    partner = _resolve_partner(db, user, partner_user_id)
    affiliate_markup = _affiliate_markup(db, user.organization_id, partner)

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
        quota_category_id=quota_category_id,
        client_bank_administrator_ids=client_bank_administrator_ids,
        client_problem_bank_administrator_ids=client_problem_bank_administrator_ids,
        affiliate_markup=affiliate_markup,
    )

    has_options = bool(
        match.get("credit_matches") or match.get("entrada_matches") or match.get("matches")
    )
    if not match.get("eligible") or not has_options:
        blockers = list(match.get("blockers") or [])
        if not blockers:
            blockers = [
                match.get("message")
                or "Não encontramos cota nas réguas legado (10% crédito / 20% entrada / 5% combo) para esses filtros.",
            ]
        return {
            "lead_id": "",
            "client_name": name.strip(),
            "esteira": match.get("esteira") or "NINA_CURATED",
            "eligible": False,
            "blockers": blockers,
            "matches": [],
            "credit_matches": [],
            "entrada_matches": [],
            "band_percent": match.get("band_percent") or "10",
            "message": blockers[0],
        }

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
        "partner_user_id": partner.id if partner else None,
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
        owner_id=partner.id if partner else user.id,
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
        "band_percent": match.get("band_percent") or "10",
        "credit_band_percent": match.get("credit_band_percent") or "10",
        "entrada_band_percent": match.get("entrada_band_percent") or "20",
        "combo_band_percent": match.get("combo_band_percent") or "5",
        "message": "",
    }


def _parse_terms(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _contract_snap_from_purchase(
    db: Session,
    lead: Lead,
    proposal: Proposal,
    snapshot: dict,
    quotas: list[Quota],
    *,
    affiliate_markup: dict[str, str] | None,
) -> dict:
    from app.marketplace_service import pricing_for_quota

    suppliers = suppliers_index(db, lead.organization_id)
    terms = _parse_terms(proposal.terms_json)
    total_credit = Decimal(str(terms.get("total_credit") or proposal.requested_amount or 0))
    total_entrada = Decimal(str(terms.get("total_entrada") or 0))
    handoff_quotas: list[dict] = []
    for q in quotas:
        admin = db.get(Administrator, q.administrator_id)
        row = pricing_for_quota(q, suppliers=suppliers, affiliate_markup=affiliate_markup)
        handoff_quotas.append(
            {
                "id": q.id,
                "administradora": admin.name if admin else "—",
                "tipo_credito": "Imóvel" if q.category == "REAL_ESTATE" else "Veículo",
                "price": str(row["credit"]),
                "price_entrada": str(row["entrada_final"]),
                "parcelas": q.remaining_installments,
                "price_parcela": str(q.installment_value or 0),
            }
        )
    snap = dict(snapshot)
    snap["email"] = snap.get("email") or lead.email
    snap["proposal_id"] = proposal.id
    snap["handoff_credit"] = str(total_credit)
    snap["handoff_entrada"] = str(total_entrada)
    snap["handoff_quotas"] = handoff_quotas
    snap["declared_income"] = snap.get("monthly_income")
    return snap


def _emit_contract_and_boleto(
    db: Session,
    user: User,
    lead: Lead,
    proposal: Proposal,
    contract_snap: dict,
) -> dict:
    from app.marketplace_contract_template_service import render_marketplace_contract_html
    from app.product_contract_flow_service import mark_marketplace_contract_at_purchase

    html = render_marketplace_contract_html(db, user.organization_id, lead, contract_snap)
    accepted_at = datetime.now(UTC).isoformat()
    terms = seed_marketplace_lifecycle(_parse_terms(proposal.terms_json))
    terms["contract_html"] = html
    terms["contract_ack"] = {
        "accepted_at": accepted_at,
        "channel": SOURCE,
        "provider": "OFFICE_ROBO_ACK",
    }
    mark_marketplace_contract_at_purchase(terms)
    proposal.terms_json = json.dumps(terms, ensure_ascii=False)

    detail = _parse_terms(lead.scr_detail_json)
    block = detail.get("venda_direta_robo") if isinstance(detail.get("venda_direta_robo"), dict) else {}
    block = {**block, **contract_snap, "contract_html": html, "contract_accepted_at": accepted_at}
    detail["venda_direta_robo"] = block
    lead.scr_detail_json = json.dumps(detail, ensure_ascii=False)
    db.flush()

    boleto_view = None
    boleto_created = False
    try:
        from app.inter_boleto_service import issue_marketplace_boleto

        issued = issue_marketplace_boleto(db, user, lead.id)
        boleto_view = issued.get("boleto")
        boleto_created = bool(issued.get("created"))
    except HTTPException:
        boleto_view = None
    except Exception:
        boleto_view = None

    from app.inter_boleto_service import boleto_public_token

    token = boleto_public_token(lead.id) if boleto_view else None
    return {
        "boleto": boleto_view,
        "boleto_created": boleto_created,
        "contract_available": bool(html),
        "cadastro_path": f"/modules/cadastros?open={lead.id}",
        "boleto_download_path": f"/marketplace/cadastros/{lead.id}/boleto/{token}" if token else None,
        "contract_pdf_path": f"/marketplace/cadastros/{lead.id}/contrato.pdf",
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

    partner_id = snapshot.get("partner_user_id")
    partner = _resolve_partner(db, user, str(partner_id) if partner_id else None)
    affiliate_markup = _affiliate_markup(db, user.organization_id, partner)
    suppliers = suppliers_index(db, user.organization_id)
    combo_pricing = pricing_for_combo(quotas, suppliers=suppliers, affiliate_markup=affiliate_markup)
    total_credit = Decimal(str(combo_pricing["credit"]))
    total_entrada = Decimal(str(combo_pricing["entrada_final"]))
    porcs = affiliate_markup or {"porc_a_mais": "0", "porc_a_mais_sellers": "0"}

    quota_payloads = []
    for q in quotas:
        row = pricing_for_quota(q, suppliers=suppliers, affiliate_markup=affiliate_markup)
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

    proposal = Proposal(
        organization_id=user.organization_id,
        lead_id=lead.id,
        product=PRODUCT,
        requested_amount=total_credit,
        status="SUBMITTED",
        terms_json=json.dumps(
            seed_marketplace_lifecycle(
                {
                    "channel": SOURCE,
                    "match_lane": match_lane,
                    "quota_ids": ids,
                    "total_credit": str(total_credit),
                    "total_entrada": str(total_entrada),
                    "client_email": snapshot.get("email"),
                    "person_type": snapshot.get("person_type"),
                    "partner_user_id": partner.id if partner else None,
                    "porc_a_mais": porcs.get("porc_a_mais", "0"),
                    "porc_a_mais_sellers": porcs.get("porc_a_mais_sellers", "0"),
                    "filters": snapshot,
                    "quotas": quota_payloads,
                }
            ),
            ensure_ascii=False,
        ),
        sale_channel="PARTNER_OFFICE",
        served_by_user_id=user.id,
        created_by_user_id=user.id,
        commission_originator_id=partner.id if partner else None,
    )
    db.add(proposal)
    db.flush()
    if partner:
        from app.affiliate_chain_commission_service import persist_chain_commissions_on_proposal

        persist_chain_commissions_on_proposal(
            db,
            proposal,
            partner_user_id=partner.id,
            price_base=total_credit,
            porc_a_mais_franquia=porcs.get("porc_a_mais", "0"),
            porc_a_mais_sellers=porcs.get("porc_a_mais_sellers", "0"),
            is_sdc=False,
        )
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

    from app.quota_inventory_service import run_nina_quota_scan

    for quota in quotas:
        if quota.nina_scan_status != "CLEARED":
            run_nina_quota_scan(db, user, quota)

    lead.status = "PROPOSAL"
    _write_lifecycle(proposal, situation=SIT_AGUARDANDO)
    contract_snap = _contract_snap_from_purchase(
        db, lead, proposal, snapshot, quotas, affiliate_markup=affiliate_markup
    )
    detail = _parse_terms(lead.scr_detail_json)
    block = detail.get("venda_direta_robo") if isinstance(detail.get("venda_direta_robo"), dict) else {}
    detail["venda_direta_robo"] = {**block, **contract_snap}
    lead.scr_detail_json = json.dumps(detail, ensure_ascii=False)
    from app.marketplace_contract_docs_service import ensure_marketplace_office_contract_draft

    ensure_marketplace_office_contract_draft(db, lead, proposal)
    db.flush()

    msg_parts = [
        f"Venda gravada. Cotas travadas por {RESERVE_TTL_MINUTES} min.",
        "Abra Cadastros para visualizar o contrato (PDF) e emitir o boleto da entrada.",
        "Assinatura digital (ZapSign) após pagamento da entrada.",
    ]

    return {
        "lead_id": lead.id,
        "proposal_id": proposal.id,
        "quota_ids": ids,
        "reservation_ids": [r.id for r in reservations],
        "requested_amount": str(money(total_credit)),
        "entrada_final": str(money(total_entrada)),
        "message": " ".join(msg_parts),
        "boleto": None,
        "boleto_created": False,
        "contract_available": True,
        "cadastro_path": f"/modules/cadastros?open={lead.id}",
        "boleto_download_path": None,
        "contract_pdf_path": f"/marketplace/cadastros/{lead.id}/contrato.pdf",
    }
