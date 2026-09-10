"""Venda Direta Manual — admin escolhe uma cota específica e grava a venda (Paulo / LETTER)."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commission_attribution import apply_proposal_attribution
from app.marketplace_service import pricing_for_quota
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
    stmt = (
        select(Lead)
        .where(Lead.organization_id == user.organization_id)
        .order_by(Lead.created_at.desc())
        .limit(80)
    )
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
    quota_id: str,
    partner_user_id: str | None = None,
    zipcode: str | None = None,
    street: str | None = None,
    number: str | None = None,
    neighborhood: str | None = None,
    city: str | None = None,
    uf: str | None = None,
    occupation: str | None = None,
    monthly_income: Decimal | None = None,
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

    quota = db.scalar(
        select(Quota).where(Quota.id == quota_id, Quota.organization_id == user.organization_id)
    )
    if not quota:
        raise HTTPException(status_code=404, detail="Cota não encontrada.")
    if quota.status != "AVAILABLE":
        raise HTTPException(status_code=422, detail="Cota indisponível para venda.")
    if not quota.installment_due_date:
        raise HTTPException(status_code=422, detail="Cota sem vencimento de parcela — complete no Inventário.")

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

    suppliers = suppliers_index(db, user.organization_id)
    pricing = pricing_for_quota(quota, suppliers=suppliers)

    # Nina scan antes da trava (igual Inventário / Robô)
    if quota.nina_scan_status != "CLEARED":
        result = run_nina_quota_scan(db, user, quota)
        if result.get("status") != "CLEARED":
            raise HTTPException(
                status_code=422,
                detail=result.get("message") or "Varredura Nina reprovou a cota.",
            )

    snapshot = {
        "email": email.strip(),
        "person_type": person,
        "occupation": occupation,
        "monthly_income": str(monthly_income) if monthly_income is not None else None,
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
            "credit": str(pricing["credit"]),
            "entrada_final": str(pricing["entrada_final"]),
            "markup_percent": pricing["markup_percent"],
            "markup_amount": pricing["markup_amount"],
            "quem_paga_comissao": pricing.get("quem_paga_comissao", 0),
        },
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
        requested_amount=pricing["credit"],
        status="SUBMITTED",
        terms_json=json.dumps(
            {
                "channel": SOURCE,
                "quota_ids": [quota.id],
                "total_credit": str(pricing["credit"]),
                "total_entrada": str(pricing["entrada_final"]),
                "client_email": email.strip(),
                "person_type": person,
                "partner_user_id": partner.id if partner else None,
                "porc_a_mais": "0",
                "porc_a_mais_sellers": "0",
                "filters": snapshot,
                "quotas": [
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
                ],
            },
            ensure_ascii=False,
        ),
        sale_channel="PARTNER_OFFICE",
        served_by_user_id=user.id,
        created_by_user_id=user.id,
        commission_originator_id=partner.id if partner else None,
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
    if partner:
        proposal.commission_originator_id = partner.id
        proposal.served_by_user_id = user.id

    reservation = reserve_quota(db, user, quota, proposal.id, RESERVE_TTL_MINUTES)
    db.flush()

    return {
        "lead_id": lead.id,
        "proposal_id": proposal.id,
        "quota_id": quota.id,
        "reservation_id": reservation.id,
        "requested_amount": str(money(pricing["credit"])),
        "entrada_final": str(pricing["entrada_final"]),
        "message": (
            f"Venda manual gravada. Cota travada por {RESERVE_TTL_MINUTES} min. "
            "Finalize o cálculo e o contrato em Propostas."
        ),
    }
