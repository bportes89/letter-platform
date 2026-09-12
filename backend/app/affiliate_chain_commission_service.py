"""Pré-cálculo de comissão afiliada — modelo bolo rachado (Paulo / SalesFinalizeService)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.affiliate_markup_service import _sales_node
from app.models import CommissionEntry, Proposal, Role, User
from app.services import money

CHAIN_KEYS = ("franquia", "regional", "manager", "supervisor", "vendedor")
PRICE_KEYS = (
    "price_partners",
    "price_regionais",
    "price_managers",
    "price_supervisors",
    "price_sellers",
)

BOLO_RELEASE_LEVELS: tuple[tuple[int, str, str], ...] = (
    (1, "franquia", "price_partners"),
    (2, "regional", "price_regionais"),
    (3, "manager", "price_managers"),
    (4, "supervisor", "price_supervisors"),
    (5, "vendedor", "price_sellers"),
)

CHAIN_LEVEL_LABELS = {
    "franquia": "Franquia",
    "regional": "Regional",
    "manager": "Gestor",
    "supervisor": "Supervisor",
    "vendedor": "Vendedor",
}

def _pct(value: float | Decimal | None) -> Decimal:
    try:
        return max(Decimal("0"), Decimal(str(value or 0)))
    except Exception:
        return Decimal("0")


def _walk_sales_chain(db: Session, organization_id: str, originator_id: str) -> list[User]:
    chain: list[User] = []
    visited: set[str] = set()
    user = db.get(User, originator_id)
    while user and user.id not in visited:
        if user.organization_id != organization_id or not user.active:
            break
        visited.add(user.id)
        chain.append(user)
        node = _sales_node(db, organization_id, user.id)
        if not node or not node.sponsor_user_id:
            break
        user = db.get(User, node.sponsor_user_id)
    return chain


def resolve_chain_user_ids(db: Session, organization_id: str, originator_id: str | None) -> dict[str, str | None]:
    """Resolve IDs da cadeia linear a partir do parceiro captador."""
    empty = {key: None for key in CHAIN_KEYS}
    if not originator_id:
        return empty

    chain = _walk_sales_chain(db, organization_id, originator_id)
    if not chain:
        return empty

    origin = chain[0]
    if origin.role in {Role.MASTER_FRANCHISEE, Role.PARTNER}:
        empty["franquia"] = origin.id
        return empty

    if origin.role == Role.QUOTA_SELLER:
        empty["vendedor"] = origin.id

    # Franquia operacional = PARTNER mais alto na cadeia (bolo/porc); master raiz só se não houver PARTNER.
    franquia_user: User | None = None
    for user in reversed(chain):
        if user.role == Role.PARTNER:
            franquia_user = user
            empty["franquia"] = user.id
            break
    if franquia_user is None:
        for user in reversed(chain):
            if user.role == Role.MASTER_FRANCHISEE:
                franquia_user = user
                empty["franquia"] = user.id
                break

    for user in chain:
        if user.id == origin.id:
            continue
        if franquia_user and user.id == franquia_user.id:
            continue
        if user.role == Role.MANAGER and not empty["manager"]:
            empty["manager"] = user.id
        elif user.role == Role.PARTNER:
            if not empty["supervisor"]:
                empty["supervisor"] = user.id
            elif not empty["regional"]:
                empty["regional"] = user.id

    return empty


def _resolve_porc_member(user: User | None, *, is_sdc: bool) -> Decimal:
    if not user or not user.active:
        return Decimal("0")
    if is_sdc:
        cg = _pct(user.porc_capital_giro)
        return cg if cg > 0 else _pct(user.porc)
    return _pct(user.porc)


def compute_chain_commissions(
    db: Session,
    organization_id: str,
    *,
    partner_user_id: str | None,
    price_base: Decimal,
    porc_a_mais_franquia: Decimal | str | float = 0,
    porc_a_mais_sellers: Decimal | str | float = 0,
    is_sdc: bool = False,
) -> dict:
    """Calcula fatias bloqueadas por nível (sem gravar saldo)."""
    base = money(Decimal(str(price_base)))
    zero_amounts = {key: "0.00" for key in PRICE_KEYS}
    if base <= 0 or not partner_user_id:
        return {
            **zero_amounts,
            "price_base": str(base),
            "chain_user_ids": {key: None for key in CHAIN_KEYS},
            "bolo_total_pct": "0",
            "porc_franquia_residual_pct": "0",
        }

    ids = resolve_chain_user_ids(db, organization_id, partner_user_id)
    users = {key: db.get(User, uid) if uid else None for key, uid in ids.items()}

    porc_regional = _resolve_porc_member(users["regional"], is_sdc=is_sdc)
    porc_manager = _resolve_porc_member(users["manager"], is_sdc=is_sdc)
    porc_supervisor = _resolve_porc_member(users["supervisor"], is_sdc=is_sdc)
    porc_vendedor = _resolve_porc_member(users["vendedor"], is_sdc=is_sdc)
    porc_franquia = _resolve_porc_member(users["franquia"], is_sdc=is_sdc)

    markup_franquia = _pct(porc_a_mais_franquia) if not is_sdc else Decimal("0")
    markup_sellers = _pct(porc_a_mais_sellers) if not is_sdc else Decimal("0")

    bolo_total = porc_franquia + markup_franquia
    soma_subordinados = porc_regional + porc_manager + porc_supervisor + porc_vendedor
    porc_franquia_residual = max(Decimal("0"), bolo_total - soma_subordinados)
    porc_total_vendedor = porc_vendedor + markup_sellers

    amounts = {
        "price_partners": money(base * porc_franquia_residual / Decimal("100")) if ids["franquia"] else Decimal("0"),
        "price_regionais": money(base * porc_regional / Decimal("100")) if ids["regional"] else Decimal("0"),
        "price_managers": money(base * porc_manager / Decimal("100")) if ids["manager"] else Decimal("0"),
        "price_supervisors": money(base * porc_supervisor / Decimal("100")) if ids["supervisor"] else Decimal("0"),
        "price_sellers": money(base * porc_total_vendedor / Decimal("100")) if ids["vendedor"] else Decimal("0"),
    }

    return {
        **{key: str(val) for key, val in amounts.items()},
        "price_base": str(base),
        "chain_user_ids": ids,
        "bolo_total_pct": str(bolo_total),
        "porc_franquia_residual_pct": str(porc_franquia_residual),
        "porc_a_mais_franquia": str(markup_franquia),
        "porc_a_mais_sellers": str(markup_sellers),
    }


def merge_chain_commissions_into_terms(terms: dict, commissions: dict) -> dict:
    """Grava pré-cálculo no terms_json (campos planos + bloco chain_commissions)."""
    terms = dict(terms)
    terms["chain_commissions"] = commissions
    for key in PRICE_KEYS:
        terms[key] = commissions.get(key, "0.00")
    return terms


def partner_chain_commission_slice(
    terms: dict,
    user_id: str,
    *,
    situation: str | None = None,
    commission_release_status: str | None = None,
) -> dict | None:
    """Fatia do afiliado logado (Paulo __estimated_commission_for_chain)."""
    block = chain_commissions_block(terms)
    if not block:
        return None

    chain_ids = block.get("chain_user_ids") or {}
    uid = str(user_id)
    level_key = next((key for key, value in chain_ids.items() if value and str(value) == uid), None)
    if not level_key:
        return None

    price_key = next(price for _, chain_key, price in BOLO_RELEASE_LEVELS if chain_key == level_key)
    amount = money(Decimal(str(block.get(price_key) or terms.get(price_key) or 0)))
    if amount <= 0:
        return None

    released = str(commission_release_status or "").upper() in {"RELEASED", "RELEASED_STUB"} or str(
        situation or ""
    ).upper() in {"CONCLUIDO", "CONCLUIDA"}
    return {
        "level": level_key,
        "level_label": CHAIN_LEVEL_LABELS.get(level_key, level_key),
        "amount": str(amount),
        "status": "RELEASED" if released else "BLOCKED",
    }


def sanitize_marketplace_terms_for_user(terms: dict, user: User) -> dict:
    """Oculta valores dos outros níveis da cadeia para parceiros."""
    from app.models import Role

    if user.role in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF, Role.MASTER_FRANCHISEE}:
        return terms
    safe = dict(terms)
    safe.pop("chain_commissions", None)
    for key in PRICE_KEYS:
        safe.pop(key, None)
    return safe


def chain_commissions_block(terms: dict) -> dict | None:
    """Retorna bloco chain_commissions se existir pré-cálculo bolo."""
    block = terms.get("chain_commissions")
    if not isinstance(block, dict):
        return None
    ids = block.get("chain_user_ids")
    if not isinstance(ids, dict):
        return None
    return block


def marketplace_blocked_commission_summary(db: Session, user: User) -> dict:
    """Saldo bloqueado: vendas pagas, não concluídas, com fatia do usuário."""
    from app.cadastro_service import SIT_CONCLUIDO, SIT_PAGO, list_cadastros

    blocked_total = Decimal("0")
    blocked_count = 0
    pipeline_total = Decimal("0")
    pipeline_count = 0

    for row in list_cadastros(db, user):
        slice_ = row.get("my_chain_commission")
        if not isinstance(slice_, dict) or slice_.get("status") != "BLOCKED":
            continue
        amount = money(Decimal(str(slice_.get("amount") or 0)))
        if amount <= 0:
            continue
        situation = str(row.get("situation") or "").upper()
        if situation in {SIT_CONCLUIDO, "CONCLUIDA"}:
            continue
        pipeline_total += amount
        pipeline_count += 1
        if situation == SIT_PAGO:
            blocked_total += amount
            blocked_count += 1

    return {
        "blocked_for_withdrawal": str(money(blocked_total)),
        "blocked_sale_count": blocked_count,
        "estimated_pipeline_total": str(money(pipeline_total)),
        "estimated_pipeline_count": pipeline_count,
    }


def bolo_chain_affiliate_total(terms: dict) -> Decimal:
    block = chain_commissions_block(terms)
    if not block:
        return Decimal("0")
    return money(
        sum(
            (Decimal(str(block.get(key) or terms.get(key) or 0)) for key in PRICE_KEYS),
            Decimal("0"),
        )
    )


def allocate_bolo_chain_commissions(
    db: Session,
    actor: User,
    *,
    originator_id: str,
    proposal: Proposal,
    reference: str,
    terms: dict,
) -> list[CommissionEntry]:
    """Libera CommissionEntry com valores pré-calculados (SalesFinalizeService / Paulo)."""
    block = chain_commissions_block(terms)
    if not block:
        return []

    chain_ids = block.get("chain_user_ids") or {}
    base = money(
        Decimal(
            str(
                block.get("price_base")
                or terms.get("total_credit")
                or proposal.requested_amount
                or 0
            )
        )
    )
    if base <= 0:
        return []

    pool_pct = Decimal(str(block.get("bolo_total_pct") or "0"))
    now = datetime.now(UTC)
    entries: list[CommissionEntry] = []

    for level, chain_key, price_key in BOLO_RELEASE_LEVELS:
        beneficiary_id = chain_ids.get(chain_key)
        if not beneficiary_id:
            continue
        amount = money(Decimal(str(block.get(price_key) or terms.get(price_key) or 0)))
        if amount <= 0:
            continue
        beneficiary = db.get(User, str(beneficiary_id))
        if (
            not beneficiary
            or not beneficiary.active
            or beneficiary.organization_id != actor.organization_id
        ):
            continue
        share_pct = money(amount / base * Decimal("100")) if base > 0 else Decimal("0")
        entries.append(
            CommissionEntry(
                organization_id=actor.organization_id,
                beneficiary_id=beneficiary.id,
                originator_id=originator_id,
                proposal_id=proposal.id,
                reference=reference,
                product="MARKETPLACE",
                commission_type="SALES",
                level=level,
                calculation_base=base,
                pool_rate_percent=pool_pct,
                level_share_percent=share_pct,
                amount=amount,
                status="AVAILABLE",
                released_at=now,
            )
        )

    if not entries:
        return []

    for entry in entries:
        db.add(entry)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Comissões desta referência já foram provisionadas")
    return entries


def persist_chain_commissions_on_proposal(
    db: Session,
    proposal: Proposal,
    *,
    partner_user_id: str | None,
    price_base: Decimal,
    porc_a_mais_franquia: Decimal | str | float = 0,
    porc_a_mais_sellers: Decimal | str | float = 0,
    is_sdc: bool = False,
) -> dict:
    commissions = compute_chain_commissions(
        db,
        proposal.organization_id,
        partner_user_id=partner_user_id,
        price_base=price_base,
        porc_a_mais_franquia=porc_a_mais_franquia,
        porc_a_mais_sellers=porc_a_mais_sellers,
        is_sdc=is_sdc,
    )
    try:
        terms = json.loads(proposal.terms_json or "{}")
    except json.JSONDecodeError:
        terms = {}
    if not isinstance(terms, dict):
        terms = {}
    terms = merge_chain_commissions_into_terms(terms, commissions)
    proposal.terms_json = json.dumps(terms, ensure_ascii=False)
    db.flush()
    return commissions
