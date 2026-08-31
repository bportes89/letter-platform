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


LEVEL_SHARES = [Decimal("50"), Decimal("20"), Decimal("15"), Decimal("10"), Decimal("5")]


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


PARTNER_NETWORK_ROLES = frozenset({
    Role.MASTER_FRANCHISEE,
    Role.MANAGER,
    Role.PARTNER,
    Role.QUOTA_SELLER,
})


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
    rule = db.scalar(select(CommissionRule).where(
        CommissionRule.organization_id == user.organization_id, CommissionRule.product == product,
        CommissionRule.commission_type == commission_type, CommissionRule.active.is_(True),
    ))
    if not rule:
        raise HTTPException(status_code=422, detail="Regra de comissão ativa não encontrada")
    node = db.scalar(select(NetworkNode).where(
        NetworkNode.organization_id == user.organization_id, NetworkNode.user_id == originator_id,
        NetworkNode.tree_type == commission_type,
    ))
    if not node:
        raise HTTPException(status_code=422, detail="Originador não pertence à árvore de comissão")
    pool = money(calculation_base * Decimal(str(rule.pool_rate_percent)) / Decimal("100"))
    shares = [Decimal(x) for x in json.loads(rule.levels_json)]
    entries: list[CommissionEntry] = []
    beneficiary_id: str | None = originator_id
    for level, share in enumerate(shares, start=1):
        if not beneficiary_id:
            break
        amount = money(pool * share / Decimal("100"))
        entry = CommissionEntry(
            organization_id=user.organization_id, beneficiary_id=beneficiary_id,
            originator_id=originator_id, proposal_id=proposal_id, reference=reference,
            product=product, commission_type=commission_type, level=level,
            calculation_base=calculation_base, pool_rate_percent=rule.pool_rate_percent,
            level_share_percent=share, amount=amount, status="PENDING_FISCAL",
        )
        db.add(entry); entries.append(entry)
        current = db.scalar(select(NetworkNode).where(
            NetworkNode.organization_id == user.organization_id, NetworkNode.user_id == beneficiary_id,
            NetworkNode.tree_type == commission_type,
        ))
        beneficiary_id = current.sponsor_user_id if current else None
    try:
        db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="Comissões desta referência já foram provisionadas")
    return entries


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
    if user.role not in {Role.RETAIL_INVESTOR, Role.INSTITUTIONAL_FUND}:
        raise HTTPException(status_code=403, detail="Perfil não habilitado para investimento")
    if opportunity.status != "OPEN":
        raise HTTPException(status_code=409, detail="Oportunidade não está aberta")
    value = money(amount)
    if value < Decimal(str(opportunity.min_investment)):
        raise HTTPException(status_code=422, detail="Valor abaixo do investimento mínimo")
    reserved = db.scalar(select(func.coalesce(func.sum(InvestmentReservation.amount), 0)).where(
        InvestmentReservation.opportunity_id == opportunity.id,
        InvestmentReservation.status.in_(["RESERVED", "CONFIRMED"]),
    ))
    if Decimal(str(reserved)) + value > Decimal(str(opportunity.target_amount)):
        raise HTTPException(status_code=409, detail="Reserva excede o saldo disponível da oportunidade")
    item = InvestmentReservation(
        organization_id=user.organization_id, opportunity_id=opportunity.id,
        investor_id=user.id, amount=value,
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="Já existe reserva ativa para este investidor")
    return item


def confirm_investment(db: Session, reservation: InvestmentReservation) -> InvestmentPosition:
    if reservation.status != "RESERVED":
        raise HTTPException(status_code=409, detail="Reserva não está pendente")
    opportunity = db.get(FundingOpportunity, reservation.opportunity_id)
    reservation.status = "CONFIRMED"; reservation.confirmed_at = datetime.now(UTC)
    opportunity.funded_amount = money(Decimal(str(opportunity.funded_amount)) + Decimal(str(reservation.amount)))
    if Decimal(str(opportunity.funded_amount)) >= Decimal(str(opportunity.target_amount)):
        opportunity.status = "FUNDED"
    position = InvestmentPosition(
        organization_id=reservation.organization_id, opportunity_id=opportunity.id,
        investor_id=reservation.investor_id, principal=reservation.amount,
    )
    db.add(position); db.flush(); return position
