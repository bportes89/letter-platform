"""Grade Universal MMN — Capítulo 2 (Letter Ecossystem 2026).

Camadas fixas sobre a verba de comissão (pool):
  1. Master franqueado — 50% (vitalício na rede; independente de quem vendeu)
  2. Vendedor direto — 35%
  3. Upline nível 1 — 7%
  4. Upline nível 2 — 5%
  5. Upline nível 3 — 3%
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.master_tree_service import get_master_root_user
from app.models import CommissionEntry, NetworkNode, Role, User
from app.network_service import money

UNIVERSAL_MMN_LAYERS: tuple[tuple[str, Decimal], ...] = (
    ("MASTER", Decimal("50")),
    ("DIRECT_SELLER", Decimal("35")),
    ("UPLINE_1", Decimal("7")),
    ("UPLINE_2", Decimal("5")),
    ("UPLINE_3", Decimal("3")),
)

PAYOUT_ON_COMPLETION = "ON_COMPLETION"
PAYOUT_MONTHLY_D10 = "MONTHLY_D10"

STATUS_PENDING_FISCAL = "PENDING_FISCAL"
STATUS_PENDING_RECEIPT = "PENDING_RECEIPT"


def default_levels_json() -> str:
    import json

    return json.dumps([str(share) for _, share in UNIVERSAL_MMN_LAYERS])


def _sales_node(db: Session, organization_id: str, user_id: str) -> NetworkNode | None:
    return db.scalar(
        select(NetworkNode).where(
            NetworkNode.organization_id == organization_id,
            NetworkNode.user_id == user_id,
            NetworkNode.tree_type == "SALES",
        )
    )


def find_network_master(db: Session, organization_id: str, originator_id: str) -> User | None:
    """Master vitalício da rede: sobe patrocinadores até MASTER_FRANCHISEE ou raiz macro."""
    current_id: str | None = originator_id
    visited: set[str] = set()
    fallback_root: User | None = None

    while current_id and current_id not in visited:
        visited.add(current_id)
        user = db.get(User, current_id)
        if not user or user.organization_id != organization_id:
            break
        if user.role == Role.MASTER_FRANCHISEE:
            return user
        node = _sales_node(db, organization_id, current_id)
        if node and not node.sponsor_user_id:
            fallback_root = user
        if not node or not node.sponsor_user_id:
            break
        current_id = node.sponsor_user_id

    origin_node = _sales_node(db, organization_id, originator_id)
    if origin_node and origin_node.master_tree_key:
        macro = get_master_root_user(db, organization_id, origin_node.master_tree_key)
        if macro:
            return macro
    return fallback_root


def _upline_chain(db: Session, organization_id: str, originator_id: str, depth: int = 3) -> list[str]:
    chain: list[str] = []
    node = _sales_node(db, organization_id, originator_id)
    while node and node.sponsor_user_id and len(chain) < depth:
        chain.append(node.sponsor_user_id)
        node = _sales_node(db, organization_id, node.sponsor_user_id)
    return chain


def _is_pj(user: User) -> bool:
    doc = (user.company_cnpj or user.document or "").strip()
    return len("".join(c for c in doc if c.isdigit())) == 14


def initial_payout_status(user: User, payout_schedule: str) -> str:
    if payout_schedule == PAYOUT_MONTHLY_D10:
        return STATUS_PENDING_FISCAL if _is_pj(user) else STATUS_PENDING_RECEIPT
    return STATUS_PENDING_FISCAL


def allocate_universal_mmn(
    db: Session,
    actor: User,
    *,
    originator_id: str,
    proposal_id: str | None,
    reference: str,
    product: str,
    commission_type: str,
    pool_amount: Decimal,
    pool_rate_percent: Decimal,
    calculation_base: Decimal,
    payout_schedule: str = PAYOUT_ON_COMPLETION,
) -> list[CommissionEntry]:
    if commission_type != "SALES":
        raise HTTPException(status_code=422, detail="Grade universal MMN aplica-se a comissões SALES")

    originator = db.get(User, originator_id)
    if not originator or originator.organization_id != actor.organization_id:
        raise HTTPException(status_code=422, detail="Originador inválido")

    if not _sales_node(db, actor.organization_id, originator_id):
        raise HTTPException(status_code=422, detail="Originador não pertence à árvore de comissão")

    master = find_network_master(db, actor.organization_id, originator_id)
    if not master:
        raise HTTPException(status_code=422, detail="Master da rede não encontrado para rateio")

    uplines = _upline_chain(db, actor.organization_id, originator_id, depth=3)

    layer_beneficiaries: list[tuple[str, str | None]] = [
        ("MASTER", master.id),
        ("DIRECT_SELLER", originator_id),
        ("UPLINE_1", uplines[0] if len(uplines) > 0 else None),
        ("UPLINE_2", uplines[1] if len(uplines) > 1 else None),
        ("UPLINE_3", uplines[2] if len(uplines) > 2 else None),
    ]

    entries: list[CommissionEntry] = []
    residual_master = master.id

    for level, (layer_name, share_percent) in enumerate(UNIVERSAL_MMN_LAYERS, start=1):
        beneficiary_id = layer_beneficiaries[level - 1][1]
        if not beneficiary_id:
            beneficiary_id = residual_master
        amount = money(pool_amount * share_percent / Decimal("100"))
        if amount <= 0:
            continue
        beneficiary = db.get(User, beneficiary_id)
        if not beneficiary:
            continue
        entries.append(
            CommissionEntry(
                organization_id=actor.organization_id,
                beneficiary_id=beneficiary_id,
                originator_id=originator_id,
                proposal_id=proposal_id,
                reference=reference,
                product=product,
                commission_type=commission_type,
                level=level,
                calculation_base=calculation_base,
                pool_rate_percent=pool_rate_percent,
                level_share_percent=share_percent,
                amount=amount,
                status=initial_payout_status(beneficiary, payout_schedule),
            )
        )

    if not entries:
        raise HTTPException(status_code=422, detail="Pool de comissão zerado")

    for entry in entries:
        db.add(entry)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Comissões desta referência já foram provisionadas")
    return entries
