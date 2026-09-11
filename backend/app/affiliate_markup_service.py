"""Markup afiliado (% a mais na entrada) — regras Paulo / legado CHAT_FLOW_ROBOT__affiliate_porc_a_mais."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NetworkNode, Role, User

PORC_A_MAIS_MAX = Decimal("5")


def _pct(value: float | Decimal | None) -> Decimal:
    try:
        pct = Decimal(str(value or 0))
    except Exception:
        return Decimal("0")
    if pct <= 0:
        return Decimal("0")
    return min(pct, PORC_A_MAIS_MAX)


def _sales_node(db: Session, organization_id: str, user_id: str) -> NetworkNode | None:
    return db.scalar(
        select(NetworkNode).where(
            NetworkNode.organization_id == organization_id,
            NetworkNode.user_id == user_id,
            NetworkNode.tree_type == "SALES",
            NetworkNode.status == "ACTIVE",
        )
    )


def find_franchise_user(db: Session, organization_id: str, user_id: str) -> User | None:
    """Sobe a árvore SALES até a franquia raiz (MASTER_FRANCHISEE ou PARTNER sem patrocinador)."""
    visited: set[str] = set()
    user = db.get(User, user_id)
    while user and user.id not in visited:
        visited.add(user.id)
        if not user.active:
            return None
        if user.role == Role.MASTER_FRANCHISEE:
            return user
        node = _sales_node(db, organization_id, user.id)
        if not node or not node.sponsor_user_id:
            return user if user.role == Role.PARTNER else None
        user = db.get(User, node.sponsor_user_id)
    return None


def resolve_affiliate_porc_a_mais(
    db: Session,
    organization_id: str,
    partner_user_id: str | None,
    *,
    is_sdc: bool = False,
) -> dict[str, str]:
    """Retorna porc_a_mais (franquia) e porc_a_mais_sellers (vendedor) em % do crédito."""
    zero = {"porc_a_mais": "0", "porc_a_mais_sellers": "0"}
    if is_sdc or not partner_user_id:
        return zero

    partner = db.get(User, partner_user_id)
    if not partner or not partner.active or partner.organization_id != organization_id:
        return zero

    porc_franquia = Decimal("0")
    porc_sellers = Decimal("0")
    franchise = find_franchise_user(db, organization_id, partner_user_id)

    if partner.role in {Role.MASTER_FRANCHISEE, Role.PARTNER}:
        porc_franquia += _pct(partner.porc_a_mais)
    elif partner.role == Role.MANAGER:
        if franchise and franchise.active:
            porc_franquia += _pct(franchise.porc_a_mais)
    elif partner.role == Role.QUOTA_SELLER:
        if franchise and franchise.active:
            porc_franquia += _pct(franchise.porc_a_mais)
        if partner.adicionar_comissao:
            porc_sellers += _pct(partner.porc_a_mais)

    return {
        "porc_a_mais": str(porc_franquia),
        "porc_a_mais_sellers": str(porc_sellers),
    }


def affiliate_markup_amount(credit: Decimal, porcs: dict[str, str] | None) -> Decimal:
    if not porcs:
        return Decimal("0")
    total_pct = Decimal(str(porcs.get("porc_a_mais") or 0)) + Decimal(str(porcs.get("porc_a_mais_sellers") or 0))
    if total_pct <= 0:
        return Decimal("0")
    from app.services import money

    return money(credit * total_pct / Decimal("100"))
