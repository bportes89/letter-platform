"""Venda Direta Manual — admin escolhe uma cota específica e grava a venda (Paulo / LETTER)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cadastro_service import seed_marketplace_lifecycle
from app.commission_attribution import apply_proposal_attribution
from app.marketplace_service import admin_profile_blockers, pricing_for_combo, pricing_for_quota
from app.models import Administrator, Lead, Proposal, Quota, Role, User
from app.quota_inventory_service import run_nina_quota_scan
from app.quota_supplier_service import suppliers_index
from app.services import money, reserve_quota

SOURCE = "VENDA_DIRETA_MANUAL"
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


def list_cotas_options(db: Session, user: User, *, category: str) -> list[dict]:
    """Cotas AVAILABLE da categoria, com entrada efetiva (markup + comissão embutida)."""
    if category not in {"REAL_ESTATE", "VEHICLE"}:
        raise HTTPException(status_code=422, detail="Categoria deve ser REAL_ESTATE ou VEHICLE.")
    suppliers = suppliers_index(db, user.organization_id)
    quotas = list(
        db.scalars(
            select(Quota)
            .where(
                Quota.organization_id == user.organization_id,
                Quota.status == "AVAILABLE",
                Quota.category == category,
            )
            .order_by(Quota.credit_value.asc())
        )
    )
    rows: list[dict] = []
    for q in quotas:
        admin = db.get(Administrator, q.administrator_id)
        pricing = pricing_for_quota(q, suppliers=suppliers)
        label = (
            f"Valor: R$ {pricing['credit']} | Entrada: R$ {pricing['entrada_final']} | "
            f"Parc.: R$ {pricing['installment']} | "
            f"Adm.: {admin.name if admin else '—'} | "
            f"Forn.: {q.supplier_source or '—'}"
        )
        rows.append(
            {
                "quota_id": q.id,
                "group_code": q.group_code,
                "quota_code": q.quota_code,
                "category": q.category,
                "credit_value": str(pricing["credit"]),
                "premium_value": str(pricing["entrada_base"]),
                "entrada_final": str(pricing["entrada_final"]),
                "installment_value": str(pricing["installment"]),
                "remaining_installments": pricing["remaining_installments"],
                "supplier_source": q.supplier_source,
                "markup_percent": pricing["markup_percent"],
                "markup_amount": pricing["markup_amount"],
                "administrator_id": q.administrator_id,
                "administrator_name": admin.name if admin else None,
                "nina_scan_status": q.nina_scan_status,
                "installment_due_date": q.installment_due_date.isoformat() if q.installment_due_date else None,
                "label": label,
            }
        )
    return rows


def list_cadastros(db: Session, user: User, *, q: str | None = None) -> list[dict]:
    """Atalho: leads recentes da org para auto-preencher."""
    stmt = select(Lead).where(Lead.organization_id == user.organization_id)
    if user.role == Role.PARTNER:
        stmt = stmt.where(Lead.owner_id == user.id)
    stmt = stmt.order_by(Lead.created_at.desc()).limit(80)
    leads = list(db.scalars(stmt))
    needle = (q or "").strip().lower()
    rows = []
    for lead in leads:
        email = None
        person_type = "PF"
        address = {}
        try:
            detail = json.loads(lead.scr_detail_json or "{}")
            for key in ("venda_direta_manual", "venda_direta_robo"):
                snap = detail.get(key) or {}
                if snap.get("email"):
                    email = snap.get("email")
                    person_type = snap.get("person_type") or "PF"
                    address = snap.get("address") or {}
                    break
        except json.JSONDecodeError:
            pass
        label = f"(#{lead.id[:8]}) {lead.name}"
        if lead.document:
            label += f" ({lead.document})"
        if email:
            label += f" {email}"
        if needle and needle not in label.lower() and needle not in (lead.phone or "").lower():
            continue
        rows.append(
            {
                "lead_id": lead.id,
                "name": lead.name,
                "document": lead.document,
                "phone": lead.phone,
                "email": email,
                "person_type": person_type,
                "address": address,
                "label": label,
                "source": lead.source,
                "status": lead.status,
            }
        )
    return rows[:40]


def list_partners(db: Session, user: User) -> list[dict]:
    partners = list(
        db.scalars(
            select(User)
            .where(
                User.organization_id == user.organization_id,
                User.active.is_(True),
                User.role.in_([Role.PARTNER, Role.MASTER_FRANCHISEE, Role.MANAGER]),
            )
            .order_by(User.name)
        )
    )
    return [{"id": p.id, "name": p.name, "role": p.role, "email": p.email} for p in partners]


def store_manual(
    db: Session,
    user: User,
    *,
    name: str,
    email: str,
    phone: str,
    person_type: str,
    document: str | None,
    quota_id: str | None = None,
    quota_ids: list[str] | None = None,
    partner_user_id: str | None = None,
    zipcode: str | None = None,
    street: str | None = None,
    number: str | None = None,
    neighborhood: str | None = None,
    city: str | None = None,
    uf: str | None = None,
    occupation: str | None = None,
    monthly_income: Decimal | None = None,
    monthly_commitment: Decimal | None = None,
    asset_value: Decimal | None = None,
    asset_year: int | None = None,
    has_credit_restriction: bool = False,
    asset_is_zero_km: bool = False,
) -> dict:
    """Grava venda manual em uma operação: lead + proposta + trava 60 min."""
    person = (person_type or "PF").upper()
    if person not in {"PF", "PJ"}:
        raise HTTPException(status_code=422, detail="Tipo deve ser PF ou PJ.")
    doc = _validate_document(person, document)
    if not (email or "").strip() or "@" not in email:
        raise HTTPException(status_code=422, detail="E-mail inválido.")
    if len((phone or "").strip()) < 8:
        raise HTTPException(status_code=422, detail="Telefone/WhatsApp obrigatório.")
    if not (name or "").strip():
        raise HTTPException(status_code=422, detail="Nome obrigatório.")

    for field_name, value in (
        ("CEP", zipcode),
        ("endereço", street),
        ("número", number),
        ("bairro", neighborhood),
        ("cidade", city),
        ("UF", uf),
    ):
        if not (value or "").strip():
            raise HTTPException(status_code=422, detail=f"Campo obrigatório: {field_name}.")

    resolved_ids = [str(x).strip() for x in (quota_ids or []) if str(x).strip()]
    if quota_id and str(quota_id).strip():
        resolved_ids = [str(quota_id).strip(), *resolved_ids]
    resolved_ids = list(dict.fromkeys(resolved_ids))
    if not resolved_ids:
        raise HTTPException(status_code=422, detail="Informe ao menos uma cota.")

    quotas: list[Quota] = []
    for qid in resolved_ids:
        quota = db.scalar(
            select(Quota).where(Quota.id == qid, Quota.organization_id == user.organization_id)
        )
        if not quota:
            raise HTTPException(status_code=404, detail=f"Cota não encontrada: {qid}.")
        if quota.status != "AVAILABLE":
            raise HTTPException(status_code=422, detail=f"Cota indisponível: {qid}.")
        if not quota.installment_due_date:
            raise HTTPException(status_code=422, detail="Cota sem vencimento de parcela — complete no Inventário.")
        quotas.append(quota)

    admin_ids = {q.administrator_id for q in quotas}
    if len(admin_ids) > 1:
        raise HTTPException(
            status_code=422,
            detail="Junção manual só permite cotas da mesma administradora.",
        )

    income = money(Decimal(str(monthly_income or 0)))
    if income <= 0:
        raise HTTPException(status_code=422, detail="Informe a renda mensal comprovada do cliente.")
    collateral = money(Decimal(str(asset_value or 0)))
    if collateral <= 0:
        raise HTTPException(status_code=422, detail="Informe o valor de avaliação do bem.")

    category = quotas[0].category
    year = int(asset_year) if asset_year else datetime.now(UTC).year
    if category == "VEHICLE" and not asset_year:
        raise HTTPException(status_code=422, detail="Informe o ano do bem (veículo).")

    suppliers = suppliers_index(db, user.organization_id)
    combo_pricing = pricing_for_combo(quotas, suppliers=suppliers)
    total_credit = Decimal(str(combo_pricing["credit"]))
    installment_total = Decimal(str(combo_pricing["installment"]))

    admin = db.get(Administrator, quotas[0].administrator_id)
    blockers = admin_profile_blockers(
        admin,
        category=category,
        asset_year=year,
        asset_is_zero_km=asset_is_zero_km,
        has_credit_restriction=has_credit_restriction,
        credit_total=total_credit,
        installment_total=installment_total,
        monthly_income=income,
        asset_value=collateral,
        combo_size=len(quotas),
    )
    if blockers:
        raise HTTPException(status_code=422, detail="; ".join(blockers))

    partner = None
    if partner_user_id:
        partner = db.scalar(
            select(User).where(
                User.id == partner_user_id,
                User.organization_id == user.organization_id,
                User.active.is_(True),
            )
        )
        if not partner:
            raise HTTPException(status_code=404, detail="Parceiro não encontrado.")

    pricing_rows: list[dict] = []
    total_credit = Decimal("0")
    total_entrada = Decimal("0")
    quota_payloads: list[dict] = []
    for quota in quotas:
        pricing = pricing_for_quota(quota, suppliers=suppliers)
        pricing_rows.append(pricing)
        total_credit += Decimal(str(pricing["credit"]))
        total_entrada += Decimal(str(pricing["entrada_final"]))
        if quota.nina_scan_status != "CLEARED":
            result = run_nina_quota_scan(db, user, quota)
            if result.get("status") != "CLEARED":
                raise HTTPException(
                    status_code=422,
                    detail=result.get("message") or "Varredura Nina reprovou a cota.",
                )
        quota_payloads.append(
            {
                "quota_id": quota.id,
                "group_code": quota.group_code,
                "quota_code": quota.quota_code,
                "credit_value": str(quota.credit_value),
                "premium_value": str(quota.premium_value),
                "entrada_final": str(pricing["entrada_final"]),
                "installment_value": str(quota.installment_value or 0),
                "supplier_source": quota.supplier_source,
                "administrator_id": quota.administrator_id,
            }
        )
    primary = quotas[0]
    primary_pricing = pricing_rows[0]

    snapshot = {
        "email": email.strip(),
        "person_type": person,
        "occupation": occupation,
        "monthly_income": str(income),
        "monthly_commitment": str(money(Decimal(str(monthly_commitment or 0)))),
        "asset_value": str(collateral),
        "asset_year": year,
        "has_credit_restriction": has_credit_restriction,
        "asset_is_zero_km": asset_is_zero_km,
        "partner_user_id": partner.id if partner else None,
        "address": {
            "zipcode": zipcode.strip(),
            "street": street.strip(),
            "number": number.strip(),
            "neighborhood": neighborhood.strip(),
            "city": city.strip(),
            "uf": (uf or "").strip().upper(),
        },
        "pricing": {
            "credit": str(total_credit),
            "entrada_final": str(total_entrada),
            "markup_percent": primary_pricing["markup_percent"],
            "markup_amount": primary_pricing["markup_amount"],
            "quem_paga_comissao": primary_pricing.get("quem_paga_comissao", 0),
        },
        "quota_ids": resolved_ids,
    }

    lead = Lead(
        organization_id=user.organization_id,
        owner_id=partner.id if partner else user.id,
        name=name.strip(),
        document=doc,
        phone=phone.strip(),
        product_interest=PRODUCT,
        status="PROPOSAL",
        source=SOURCE,
        scr_detail_json=json.dumps({"venda_direta_manual": snapshot}, ensure_ascii=False),
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
            seed_marketplace_lifecycle(
                {
                    "channel": SOURCE,
                    "quota_ids": resolved_ids,
                    "total_credit": str(total_credit),
                    "total_entrada": str(total_entrada),
                    "client_email": email.strip(),
                    "person_type": person,
                    "partner_user_id": partner.id if partner else None,
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
        commission_originator_id=partner.id if partner else None,
    )
    db.add(proposal)
    db.flush()
    if partner:
        from app.affiliate_markup_service import resolve_affiliate_porc_a_mais
        from app.affiliate_chain_commission_service import persist_chain_commissions_on_proposal

        markup = resolve_affiliate_porc_a_mais(db, user.organization_id, partner.id, is_sdc=False)
        persist_chain_commissions_on_proposal(
            db,
            proposal,
            partner_user_id=partner.id,
            price_base=total_credit,
            porc_a_mais_franquia=markup.get("porc_a_mais", "0"),
            porc_a_mais_sellers=markup.get("porc_a_mais_sellers", "0"),
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
    if partner:
        proposal.commission_originator_id = partner.id
        proposal.served_by_user_id = user.id

    reservations = []
    for quota in quotas:
        reservations.append(reserve_quota(db, user, quota, proposal.id, RESERVE_TTL_MINUTES))
    db.flush()

    return {
        "lead_id": lead.id,
        "proposal_id": proposal.id,
        "quota_id": primary.id,
        "quota_ids": resolved_ids,
        "reservation_id": reservations[0].id,
        "reservation_ids": [r.id for r in reservations],
        "requested_amount": str(money(total_credit)),
        "entrada_final": str(money(total_entrada)),
        "message": (
            f"Venda manual gravada ({len(resolved_ids)} cota(s)). Trava de {RESERVE_TTL_MINUTES} min. "
            "Finalize o cálculo e o contrato em Propostas."
        ),
    }
