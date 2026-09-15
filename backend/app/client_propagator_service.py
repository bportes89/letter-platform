"""Cliente como propagador — código de indicação e âncora comercial na rede."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commission_attribution import is_commercial_seller, originator_in_sales_tree
from app.models import NetworkNode, Role, User

CLIENT_TREE_TYPE = "CLIENT"


def resolve_commercial_anchor(db: Session, user: User | None) -> User | None:
    if not user:
        return None
    current: User | None = user
    visited: set[str] = set()
    while current and current.id not in visited:
        visited.add(current.id)
        if is_commercial_seller(current.role) and originator_in_sales_tree(
            db,
            current.organization_id,
            current.id,
        ):
            return current
        if not current.referred_by_user_id:
            break
        current = db.get(User, current.referred_by_user_id)
    return None


def ensure_client_propagator_node(db: Session, user: User) -> NetworkNode | None:
    if user.role != Role.CLIENT:
        return None
    existing = db.scalar(
        select(NetworkNode).where(
            NetworkNode.organization_id == user.organization_id,
            NetworkNode.user_id == user.id,
            NetworkNode.tree_type == CLIENT_TREE_TYPE,
        )
    )
    if existing:
        return existing
    anchor = resolve_commercial_anchor(db, user)
    code = f"LTR-CLI-{user.id.replace('-', '')[:10].upper()}"
    node = NetworkNode(
        organization_id=user.organization_id,
        user_id=user.id,
        sponsor_user_id=anchor.id if anchor else user.referred_by_user_id,
        tree_type=CLIENT_TREE_TYPE,
        referral_code=code,
    )
    db.add(node)
    db.flush()
    return node


def provision_client_propagator_on_signup(db: Session, user: User) -> NetworkNode | None:
    if user.role != Role.CLIENT:
        return None
    return ensure_client_propagator_node(db, user)


def lead_owner_for_referrer(
    db: Session,
    organization_id: str,
    referrer_node: NetworkNode | None,
    *,
    fallback_user_id: str | None = None,
) -> str | None:
    if not referrer_node:
        return fallback_user_id
    if referrer_node.tree_type == CLIENT_TREE_TYPE:
        referrer = db.get(User, referrer_node.user_id)
        anchor = resolve_commercial_anchor(db, referrer)
        return anchor.id if anchor else referrer_node.user_id
    return referrer_node.user_id
