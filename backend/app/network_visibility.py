"""Visibilidade de leads e propostas por árvore comercial (master → gerente → parceiro)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Lead, NetworkNode, Proposal, Role, User

OVERSIGHT_ROLES = frozenset({Role.MASTER_FRANCHISEE, Role.MANAGER})
PARTNER_ORIGIN_ROLES = frozenset({Role.PARTNER, Role.QUOTA_SELLER})
ORG_WIDE_ROLES = frozenset({Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF})

INVITEABLE_ROLES: dict[Role, frozenset[Role]] = {
    Role.MASTER_FRANCHISEE: frozenset({Role.MANAGER, Role.PARTNER, Role.QUOTA_SELLER}),
    Role.MANAGER: frozenset({Role.PARTNER, Role.QUOTA_SELLER}),
    Role.PARTNER: frozenset({Role.PARTNER, Role.QUOTA_SELLER}),
    Role.QUOTA_SELLER: frozenset({Role.QUOTA_SELLER}),
}

CONTRACT_REQUIRED_INVITE_ROLES = frozenset({Role.PARTNER, Role.QUOTA_SELLER})


def assert_invitable_role(inviter: User, role: Role) -> None:
    allowed = INVITEABLE_ROLES.get(inviter.role, frozenset())
    if role not in allowed:
        raise HTTPException(
            status_code=422,
            detail="Perfil sem permissão para convidar este papel na sua rede.",
        )


def ensure_network_node(db: Session, user: User, tree_type: str = "SALES") -> NetworkNode | None:
    if user.role not in OVERSIGHT_ROLES and user.role not in PARTNER_ORIGIN_ROLES:
        return None
    existing = db.scalar(
        select(NetworkNode).where(
            NetworkNode.organization_id == user.organization_id,
            NetworkNode.user_id == user.id,
            NetworkNode.tree_type == tree_type,
        )
    )
    if existing:
        return existing
    if user.role not in OVERSIGHT_ROLES and user.role not in PARTNER_ORIGIN_ROLES:
        return None
    code = f"LTR-{tree_type[:3]}-{user.id.replace('-', '')[:10].upper()}"
    node = NetworkNode(
        organization_id=user.organization_id,
        user_id=user.id,
        sponsor_user_id=None,
        tree_type=tree_type,
        referral_code=code,
    )
    db.add(node)
    db.flush()
    return node


def downline_user_ids(
    db: Session,
    user: User,
    *,
    tree_type: str = "SALES",
    max_depth: int = 5,
    include_self: bool = False,
) -> set[str]:
    ensure_network_node(db, user, tree_type)
    frontier = [user.id]
    descendants: set[str] = set()
    for _ in range(max_depth):
        if not frontier:
            break
        children = list(
            db.scalars(
                select(NetworkNode.user_id).where(
                    NetworkNode.organization_id == user.organization_id,
                    NetworkNode.tree_type == tree_type,
                    NetworkNode.sponsor_user_id.in_(frontier),
                )
            )
        )
        new_children = [child for child in children if child not in descendants]
        descendants.update(new_children)
        frontier = new_children
    if include_self:
        descendants.add(user.id)
    return descendants


def visible_owner_ids(db: Session, user: User) -> set[str] | None:
    if user.role in ORG_WIDE_ROLES:
        return None
    if user.role == Role.CLIENT:
        return {user.id}
    if user.role in OVERSIGHT_ROLES:
        ids = downline_user_ids(db, user, include_self=True)
        return ids
    if user.role in PARTNER_ORIGIN_ROLES:
        return {user.id}
    return set()


def list_visible_leads(db: Session, user: User) -> list[Lead]:
    query = select(Lead).where(Lead.organization_id == user.organization_id)
    if user.role == Role.CLIENT:
        query = query.where(
            (Lead.client_user_id == user.id) | (Lead.owner_id == user.id)
        )
    else:
        owner_ids = visible_owner_ids(db, user)
        if owner_ids is not None:
            query = query.where(Lead.owner_id.in_(owner_ids))
    return list(db.scalars(query.order_by(Lead.created_at.desc())))


def list_visible_proposals(db: Session, user: User) -> list[Proposal]:
    if user.role == Role.CLIENT:
        query = (
            select(Proposal)
            .join(Lead, Proposal.lead_id == Lead.id)
            .where(
                Proposal.organization_id == user.organization_id,
                (Proposal.client_user_id == user.id) | (Lead.client_user_id == user.id),
            )
        )
        return list(db.scalars(query.order_by(Proposal.created_at.desc())))
    owner_ids = visible_owner_ids(db, user)
    query = (
        select(Proposal)
        .join(Lead, Proposal.lead_id == Lead.id)
        .where(Proposal.organization_id == user.organization_id)
    )
    if owner_ids is not None:
        query = query.where(Lead.owner_id.in_(owner_ids))
    return list(db.scalars(query.order_by(Proposal.created_at.desc())))


def get_lead_for_user(db: Session, user: User, lead_id: str) -> Lead:
    lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.organization_id == user.organization_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if user.role == Role.CLIENT:
        if lead.client_user_id != user.id and lead.owner_id != user.id:
            raise HTTPException(status_code=404, detail="Lead não encontrado")
        return lead
    owner_ids = visible_owner_ids(db, user)
    if owner_ids is not None and lead.owner_id not in owner_ids:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    return lead


def get_proposal_for_user(db: Session, user: User, proposal_id: str) -> Proposal:
    proposal = db.scalar(
        select(Proposal).where(Proposal.id == proposal_id, Proposal.organization_id == user.organization_id)
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    lead = db.get(Lead, proposal.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    if user.role == Role.CLIENT:
        if proposal.client_user_id != user.id and lead.client_user_id != user.id:
            raise HTTPException(status_code=404, detail="Proposta não encontrada")
        return proposal
    owner_ids = visible_owner_ids(db, user)
    if owner_ids is not None and lead.owner_id not in owner_ids:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    return proposal


def owner_map(db: Session, owner_ids: set[str]) -> dict[str, User]:
    if not owner_ids:
        return {}
    users = list(db.scalars(select(User).where(User.id.in_(owner_ids))))
    return {item.id: item for item in users}


def enrich_lead_view(lead: Lead, owners: dict[str, User]) -> dict:
    owner = owners.get(lead.owner_id or "")
    payload = {
        "id": lead.id,
        "name": lead.name,
        "phone": lead.phone,
        "product_interest": lead.product_interest,
        "status": lead.status,
        "source": lead.source,
        "scr_status": lead.scr_status,
        "scr_reference": lead.scr_reference,
        "scr_consulted_at": lead.scr_consulted_at,
        "created_at": lead.created_at,
        "owner_id": lead.owner_id,
        "owner_name": owner.name if owner else None,
        "owner_role": owner.role.value if owner and hasattr(owner.role, "value") else (str(owner.role) if owner else None),
    }
    return payload


def enrich_proposal_view(proposal: Proposal, lead: Lead | None, owners: dict[str, User], db: Session | None = None) -> dict:
    owner = owners.get((lead.owner_id if lead else "") or "")
    payload = {
        "id": proposal.id,
        "lead_id": proposal.lead_id,
        "product": proposal.product,
        "requested_amount": proposal.requested_amount,
        "status": proposal.status,
        "calculation_version": proposal.calculation_version,
        "created_at": proposal.created_at,
        "owner_id": lead.owner_id if lead else None,
        "owner_name": owner.name if owner else None,
        "owner_role": owner.role.value if owner and hasattr(owner.role, "value") else (str(owner.role) if owner else None),
        "lead_name": lead.name if lead else None,
    }
    if db is not None:
        from app.commission_attribution import attribution_view

        payload.update(attribution_view(proposal, db))
    return payload


def list_downline_members(db: Session, user: User, tree_type: str = "SALES") -> list[dict]:
    ensure_network_node(db, user, tree_type)
    members: list[dict] = []
    frontier = [(user.id, 0)]
    visited: set[str] = {user.id}
    users_by_id = owner_map(db, {user.id})

    while frontier:
        sponsor_id, level = frontier.pop(0)
        if level >= 5:
            continue
        children = list(
            db.scalars(
                select(NetworkNode).where(
                    NetworkNode.organization_id == user.organization_id,
                    NetworkNode.tree_type == tree_type,
                    NetworkNode.sponsor_user_id == sponsor_id,
                ).order_by(NetworkNode.created_at)
            )
        )
        child_user_ids = {node.user_id for node in children}
        users_by_id.update(owner_map(db, child_user_ids))
        sponsor = users_by_id.get(sponsor_id)
        for node in children:
            if node.user_id in visited:
                continue
            visited.add(node.user_id)
            member = users_by_id.get(node.user_id)
            if not member:
                continue
            members.append(
                {
                    "user_id": member.id,
                    "name": member.name,
                    "email": member.email,
                    "role": member.role.value if hasattr(member.role, "value") else str(member.role),
                    "referral_code": node.referral_code,
                    "level": level + 1,
                    "sponsor_user_id": sponsor_id,
                    "sponsor_name": sponsor.name if sponsor else None,
                    "status": node.status,
                }
            )
            frontier.append((node.user_id, level + 1))
    return members


def pending_counts_for_network(db: Session, user: User) -> dict:
    proposals = list_visible_proposals(db, user)
    pending_statuses = {"DRAFT", "PENDING", "IN_REVIEW", "SUBMITTED", "DOCUMENTS_PENDING", "PENDING_DOCUMENTS"}
    active = [p for p in proposals if p.status not in {"CANCELLED", "EXPIRED"}]
    pending = [p for p in active if p.status in pending_statuses or p.status not in {"APPROVED", "CONTRACTED", "CLOSED"}]
    leads = list_visible_leads(db, user)
    open_leads = [lead for lead in leads if lead.status not in {"REGISTERED", "CLOSED", "LOST"}]
    return {
        "visible_proposals": len(active),
        "pending_proposals": len(pending),
        "visible_leads": len(leads),
        "open_leads": len(open_leads),
        "downline_size": len(downline_user_ids(db, user)),
    }
