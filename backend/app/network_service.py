import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    CommissionEntry, CommissionRule, FiscalEvidence, FundingOpportunity,
    InvestmentPosition, InvestmentReservation, NetworkNode, Role, User,
)


LEVEL_SHARES = [Decimal("50"), Decimal("35"), Decimal("7"), Decimal("5"), Decimal("3")]


def money(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


PARTNER_NETWORK_ROLES = frozenset({
    Role.MASTER_FRANCHISEE,
    Role.MANAGER,
    Role.PARTNER,
    Role.QUOTA_SELLER,
})


def provision_master_network_on_signup(db: Session, user: User) -> NetworkNode | None:
    """Cria a rede comercial do master no cadastro (raiz com código de indicação)."""
    if user.role != Role.MASTER_FRANCHISEE:
        return None
    from app.master_tree_service import sync_user_master_tree
    from app.network_visibility import ensure_network_node

    if user.master_tree_key:
        return sync_user_master_tree(db, user)
    return ensure_network_node(db, user)


def attach_partner_under_sponsor(
    db: Session,
    organization_id: str,
    new_user: User,
    sponsor: User,
    tree_type: str = "SALES",
) -> NetworkNode | None:
    if new_user.role not in PARTNER_NETWORK_ROLES:
        return None
    existing = db.scalar(select(NetworkNode).where(
        NetworkNode.organization_id == organization_id,
        NetworkNode.user_id == new_user.id,
        NetworkNode.tree_type == tree_type,
    ))
    if existing:
        return existing
    sponsor_node = db.scalar(select(NetworkNode).where(
        NetworkNode.organization_id == organization_id,
        NetworkNode.user_id == sponsor.id,
        NetworkNode.tree_type == tree_type,
    ))
    if not sponsor_node:
        return None
    code = f"LTR-{tree_type[:3]}-{new_user.id.replace('-', '')[:10].upper()}"
    node = NetworkNode(
        organization_id=organization_id,
        user_id=new_user.id,
        sponsor_user_id=sponsor.id,
        master_tree_key=sponsor_node.master_tree_key,
        tree_type=tree_type,
        referral_code=code,
    )
    db.add(node)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return None
    return node


def create_network_node(db: Session, user: User, target: User, tree_type: str, sponsor_user_id: str | None) -> NetworkNode:
    if target.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if tree_type not in {"SALES", "CAPITAL"}:
        raise HTTPException(status_code=422, detail="Árvore deve ser SALES ou CAPITAL")
    if sponsor_user_id:
        sponsor = db.scalar(select(NetworkNode).where(
            NetworkNode.organization_id == user.organization_id,
            NetworkNode.user_id == sponsor_user_id, NetworkNode.tree_type == tree_type,
        ))
        if not sponsor:
            raise HTTPException(status_code=422, detail="Patrocinador não pertence à árvore informada")
    code = f"LTR-{tree_type[:3]}-{target.id.replace('-', '')[:10].upper()}"
    node = NetworkNode(
        organization_id=user.organization_id, user_id=target.id, sponsor_user_id=sponsor_user_id,
        tree_type=tree_type, referral_code=code,
    )
    db.add(node)
    try:
        db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="Usuário já está cadastrado nesta árvore")
    return node


def downline_summary(db: Session, user: User, tree_type: str) -> dict:
    levels: list[int] = []
    frontier = [user.id]
    for _ in range(5):
        children = list(db.scalars(select(NetworkNode.user_id).where(
            NetworkNode.organization_id == user.organization_id,
            NetworkNode.tree_type == tree_type, NetworkNode.sponsor_user_id.in_(frontier),
        ))) if frontier else []
        levels.append(len(children)); frontier = children
    return {"tree_type": tree_type, "total_downline": sum(levels), "levels": {str(i + 1): count for i, count in enumerate(levels)}, "privacy_mode": "AGGREGATED"}


def create_rule(db: Session, user: User, product: str, commission_type: str, pool_rate_percent: Decimal, base_type: str) -> CommissionRule:
    if commission_type not in {"SALES", "CAPITAL"}:
        raise HTTPException(status_code=422, detail="Tipo de comissão inválido")
    current = db.scalar(select(func.max(CommissionRule.version)).where(
        CommissionRule.organization_id == user.organization_id,
        CommissionRule.product == product, CommissionRule.commission_type == commission_type,
    )) or 0
    for item in db.scalars(select(CommissionRule).where(
        CommissionRule.organization_id == user.organization_id,
        CommissionRule.product == product, CommissionRule.commission_type == commission_type,
        CommissionRule.active.is_(True),
    )):
        item.active = False
    rule = CommissionRule(
        organization_id=user.organization_id, product=product, commission_type=commission_type,
        version=current + 1, base_type=base_type, pool_rate_percent=pool_rate_percent,
        levels_json=json.dumps([str(x) for x in LEVEL_SHARES]), active=True,
    )
    db.add(rule); return rule


def allocate_commissions(db: Session, user: User, originator_id: str, proposal_id: str | None, reference: str, product: str, commission_type: str, calculation_base: Decimal) -> list[CommissionEntry]:
    from app.universal_mmn_service import allocate_universal_mmn

    rule = db.scalar(select(CommissionRule).where(
        CommissionRule.organization_id == user.organization_id, CommissionRule.product == product,
        CommissionRule.commission_type == commission_type, CommissionRule.active.is_(True),
    ))
    if not rule:
        raise HTTPException(status_code=422, detail="Regra de comissão ativa não encontrada")
    pool = money(calculation_base * Decimal(str(rule.pool_rate_percent)) / Decimal("100"))
    try:
        return allocate_universal_mmn(
            db,
            user,
            originator_id=originator_id,
            proposal_id=proposal_id,
            reference=reference,
            product=product,
            commission_type=commission_type,
            pool_amount=pool,
            pool_rate_percent=Decimal(str(rule.pool_rate_percent)),
            calculation_base=calculation_base,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Comissões desta referência já foram provisionadas")


def release_fiscal_hold(db: Session, user: User, reference_month: str, document_content: str) -> FiscalEvidence:
    digest = hashlib.sha256(document_content.encode()).hexdigest()
    evidence = FiscalEvidence(
        organization_id=user.organization_id, user_id=user.id, reference_month=reference_month,
        document_hash=digest, status="VALID", validated_at=datetime.now(UTC),
    )
    db.add(evidence); db.flush()
    for entry in db.scalars(select(CommissionEntry).where(
        CommissionEntry.organization_id == user.organization_id,
        CommissionEntry.beneficiary_id == user.id, CommissionEntry.status == "PENDING_FISCAL",
    )):
        entry.status = "AVAILABLE"; entry.released_at = datetime.now(UTC)
    return evidence


def reserve_investment(db: Session, user: User, opportunity: FundingOpportunity, amount: Decimal) -> InvestmentReservation:
    from app.flash_invest_service import reserve_investment as _reserve

    return _reserve(db, user, opportunity, amount)


def confirm_investment(db: Session, reservation: InvestmentReservation) -> InvestmentPosition:
    from app.flash_invest_service import confirm_investment as _confirm

    return _confirm(db, reservation)
