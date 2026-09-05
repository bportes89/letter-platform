"""Atribuição de comissão MMN: autoconsumo do cliente vs atendimento no escritório do parceiro."""

from __future__ import annotations

import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CalculationMemory, CommissionEntry, CommissionRule, Lead, NetworkNode, Proposal, Role, User
from app.network_service import allocate_commissions, money
from app.public_site_service import MMN_BASE_KEYS

SALE_CHANNEL_SELF = "SELF_SERVICE"
SALE_CHANNEL_PARTNER = "PARTNER_OFFICE"

COMMERCIAL_SELLER_ROLES = frozenset({
    Role.MASTER_FRANCHISEE,
    Role.MANAGER,
    Role.PARTNER,
    Role.QUOTA_SELLER,
})


def is_commercial_seller(role: Role) -> bool:
    return role in COMMERCIAL_SELLER_ROLES


def originator_in_sales_tree(db: Session, organization_id: str, user_id: str) -> bool:
    return db.scalar(
        select(NetworkNode.id).where(
            NetworkNode.organization_id == organization_id,
            NetworkNode.user_id == user_id,
            NetworkNode.tree_type == "SALES",
        )
    ) is not None


def resolve_commission_originator_id(
    db: Session,
    organization_id: str,
    *,
    sale_channel: str,
    client_user: User | None,
    served_by_user: User | None,
) -> str | None:
    if sale_channel == SALE_CHANNEL_PARTNER:
        if served_by_user and is_commercial_seller(served_by_user.role):
            candidate = served_by_user.id
        else:
            return None
    elif sale_channel == SALE_CHANNEL_SELF:
        if not client_user or not client_user.referred_by_user_id:
            return None
        referrer = db.get(User, client_user.referred_by_user_id)
        if not referrer or not referrer.active or referrer.organization_id != organization_id:
            return None
        candidate = referrer.id
    else:
        return None

    if not originator_in_sales_tree(db, organization_id, candidate):
        return None
    return candidate


def resolve_sale_channel_and_parties(
    db: Session,
    actor: User,
    *,
    client_user_id: str | None,
    sale_channel: str | None,
    served_by_user_id: str | None,
    lead: Lead,
) -> tuple[str, User | None, User | None]:
    if actor.role == Role.CLIENT:
        if client_user_id and client_user_id != actor.id:
            raise HTTPException(status_code=403, detail="Cliente só pode consumir no próprio escritório")
        return SALE_CHANNEL_SELF, actor, None

    if not is_commercial_seller(actor.role):
        raise HTTPException(status_code=403, detail="Perfil sem permissão para registrar venda comercial")

    channel = (sale_channel or SALE_CHANNEL_PARTNER).upper()
    if channel not in {SALE_CHANNEL_SELF, SALE_CHANNEL_PARTNER}:
        raise HTTPException(status_code=422, detail="Canal de venda inválido")

    if channel == SALE_CHANNEL_SELF:
        if not client_user_id:
            raise HTTPException(status_code=422, detail="Informe o cliente para autoconsumo assistido")
        client = db.get(User, client_user_id)
        if not client or client.organization_id != actor.organization_id or client.role != Role.CLIENT:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        return SALE_CHANNEL_SELF, client, None

    client: User | None = None
    if client_user_id:
        client = db.get(User, client_user_id)
        if not client or client.organization_id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
    elif lead.client_user_id:
        client = db.get(User, lead.client_user_id)

    served_by = actor
    if served_by_user_id and served_by_user_id != actor.id:
        served = db.get(User, served_by_user_id)
        if not served or served.organization_id != actor.organization_id or not is_commercial_seller(served.role):
            raise HTTPException(status_code=404, detail="Atendente comercial não encontrado")
        served_by = served

    return SALE_CHANNEL_PARTNER, client, served_by


def apply_proposal_attribution(
    db: Session,
    actor: User,
    proposal: Proposal,
    *,
    client_user_id: str | None,
    sale_channel: str | None,
    served_by_user_id: str | None,
    lead: Lead,
) -> None:
    channel, client_user, served_by = resolve_sale_channel_and_parties(
        db,
        actor,
        client_user_id=client_user_id,
        sale_channel=sale_channel,
        served_by_user_id=served_by_user_id,
        lead=lead,
    )
    originator_id = resolve_commission_originator_id(
        db,
        actor.organization_id,
        sale_channel=channel,
        client_user=client_user,
        served_by_user=served_by if channel == SALE_CHANNEL_PARTNER else None,
    )

    proposal.sale_channel = channel
    proposal.client_user_id = client_user.id if client_user else lead.client_user_id
    proposal.served_by_user_id = served_by.id if channel == SALE_CHANNEL_PARTNER and served_by else None
    proposal.commission_originator_id = originator_id
    proposal.created_by_user_id = actor.id

    terms = json.loads(proposal.terms_json or "{}")
    terms.update({
        "sale_channel": channel,
        "commission_originator_id": originator_id,
        "client_user_id": proposal.client_user_id,
        "served_by_user_id": proposal.served_by_user_id,
    })
    proposal.terms_json = json.dumps(terms, ensure_ascii=False)


def assert_lead_access_for_sale(db: Session, actor: User, lead: Lead, client_user_id: str | None) -> None:
    if actor.role == Role.CLIENT:
        if lead.client_user_id and lead.client_user_id != actor.id:
            raise HTTPException(status_code=404, detail="Lead não encontrado")
        if not lead.client_user_id and lead.document and actor.document and lead.document != actor.document:
            raise HTTPException(status_code=404, detail="Lead não encontrado")
        return

    from app.network_visibility import get_lead_for_user

    get_lead_for_user(db, actor, lead.id)


def get_or_create_client_lead(db: Session, client: User, *, owner_id: str | None = None) -> Lead:
    existing = db.scalar(
        select(Lead).where(
            Lead.organization_id == client.organization_id,
            Lead.client_user_id == client.id,
        ).order_by(Lead.created_at.desc())
    )
    if existing:
        return existing
    lead = Lead(
        organization_id=client.organization_id,
        owner_id=owner_id or client.referred_by_user_id,
        client_user_id=client.id,
        name=client.name,
        document=client.document,
        phone=client.phone or "",
        product_interest="PLATFORM",
        status="REGISTERED",
        source="CLIENT_OFFICE",
    )
    db.add(lead)
    db.flush()
    return lead


def commission_base_from_calculation(rule: CommissionRule, calculation: CalculationMemory, proposal: Proposal) -> Decimal:
    output = json.loads(calculation.output_json or "{}")
    base_key = MMN_BASE_KEYS.get(rule.base_type.upper(), rule.base_type.lower())
    raw = output.get(base_key)
    if raw is None:
        for fallback in ("net_payout", "platform_fee", "intermediation_fee", "principal", "partner_commission_base"):
            if fallback in output:
                raw = output[fallback]
                break
    if raw is None:
        raw = proposal.requested_amount
    return money(Decimal(str(raw)))


def auto_allocate_sale_commission(
    db: Session,
    actor: User,
    proposal: Proposal,
    calculation: CalculationMemory,
    *,
    reference: str,
) -> list[CommissionEntry]:
    if not proposal.commission_originator_id:
        return []

    existing = db.scalar(
        select(CommissionEntry.id).where(
            CommissionEntry.organization_id == proposal.organization_id,
            CommissionEntry.reference == reference,
        )
    )
    if existing:
        return list(
            db.scalars(
                select(CommissionEntry).where(
                    CommissionEntry.organization_id == proposal.organization_id,
                    CommissionEntry.reference == reference,
                )
            )
        )

    rule = db.scalar(
        select(CommissionRule).where(
            CommissionRule.organization_id == proposal.organization_id,
            CommissionRule.product == proposal.product,
            CommissionRule.commission_type == "SALES",
            CommissionRule.active.is_(True),
        )
    )
    if not rule:
        return []

    base = commission_base_from_calculation(rule, calculation, proposal)
    if base <= 0:
        return []

    return allocate_commissions(
        db,
        actor,
        proposal.commission_originator_id,
        proposal.id,
        reference,
        proposal.product,
        "SALES",
        base,
    )


def attribution_view(proposal: Proposal, db: Session) -> dict:
    client = db.get(User, proposal.client_user_id) if proposal.client_user_id else None
    served = db.get(User, proposal.served_by_user_id) if proposal.served_by_user_id else None
    originator = db.get(User, proposal.commission_originator_id) if proposal.commission_originator_id else None
    return {
        "sale_channel": proposal.sale_channel,
        "client_user_id": proposal.client_user_id,
        "client_name": client.name if client else None,
        "served_by_user_id": proposal.served_by_user_id,
        "served_by_name": served.name if served else None,
        "commission_originator_id": proposal.commission_originator_id,
        "commission_originator_name": originator.name if originator else None,
    }
