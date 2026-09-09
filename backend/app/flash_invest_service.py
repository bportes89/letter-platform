"""Flash Invest — tokens (a partir de R$ 100) e mútuo (>= R$ 10.000), com lançamentos manuais."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import FundingOpportunity, InvestmentPosition, InvestmentReservation, RentabilityCredit, Role, User
from app.services import money

TOKEN_MIN = Decimal("100")
MUTUO_MIN = Decimal("10000")
DEFAULT_TOKEN_UNIT = Decimal("100")
DEFAULT_MONTHLY_RATE = Decimal("0.016")


def validate_instrument_amount(*, instrument_type: str, amount: Decimal, token_unit: Decimal = DEFAULT_TOKEN_UNIT) -> None:
    value = money(amount)
    instrument = (instrument_type or "TOKEN").upper()
    if instrument == "TOKEN":
        if value < TOKEN_MIN:
            raise HTTPException(status_code=422, detail="Investimento via token exige mínimo de R$ 100,00.")
        unit = money(token_unit) if token_unit > 0 else DEFAULT_TOKEN_UNIT
        if value % unit != 0:
            raise HTTPException(
                status_code=422,
                detail=f"Valor via token deve ser múltiplo de R$ {unit} (face do token).",
            )
        return
    if instrument == "MUTUO":
        if value < MUTUO_MIN:
            raise HTTPException(
                status_code=422,
                detail="Mútuo financeiro exige aporte mínimo de R$ 10.000,00. Abaixo disso use tokens.",
            )
        return
    raise HTTPException(status_code=422, detail="Instrumento inválido. Use TOKEN ou MUTUO.")


def instrument_hint(amount: Decimal) -> dict:
    value = money(amount)
    if value < TOKEN_MIN:
        return {
            "amount": str(value),
            "allowed": [],
            "message": "Aporte mínimo via token é R$ 100,00.",
        }
    if value < MUTUO_MIN:
        return {
            "amount": str(value),
            "allowed": ["TOKEN"],
            "message": "Abaixo de R$ 10.000 o investimento é exclusivamente via tokens.",
        }
    return {
        "amount": str(value),
        "allowed": ["TOKEN", "MUTUO"],
        "message": "A partir de R$ 10.000 pode ser via token ou mútuo financeiro.",
    }


def _tokens_for(amount: Decimal, unit: Decimal) -> int:
    unit = money(unit) if unit > 0 else DEFAULT_TOKEN_UNIT
    return int(money(amount) / unit)


def create_opportunity(
    db: Session,
    user: User,
    *,
    title: str,
    product: str,
    capital_source: str,
    target_amount: Decimal,
    instrument_type: str = "TOKEN",
    min_investment: Decimal | None = None,
    token_unit_price: Decimal = DEFAULT_TOKEN_UNIT,
    monthly_return_rate: Decimal = DEFAULT_MONTHLY_RATE,
    property_ref: str | None = None,
    annual_return_reference: Decimal | None = None,
    proposal_id: str | None = None,
) -> FundingOpportunity:
    instrument = (instrument_type or "TOKEN").upper()
    if instrument not in {"TOKEN", "MUTUO"}:
        raise HTTPException(status_code=422, detail="instrument_type deve ser TOKEN ou MUTUO")
    if capital_source not in {"RETAIL", "INSTITUTIONAL"}:
        raise HTTPException(status_code=422, detail="Fonte de capital inválida")

    unit = money(token_unit_price) if token_unit_price else DEFAULT_TOKEN_UNIT
    if instrument == "TOKEN":
        floor = money(min_investment) if min_investment is not None else TOKEN_MIN
        if floor < TOKEN_MIN:
            floor = TOKEN_MIN
    else:
        floor = money(min_investment) if min_investment is not None else MUTUO_MIN
        if floor < MUTUO_MIN:
            floor = MUTUO_MIN

    item = FundingOpportunity(
        organization_id=user.organization_id,
        proposal_id=proposal_id,
        title=title.strip(),
        product=product,
        capital_source=capital_source,
        instrument_type=instrument,
        target_amount=money(target_amount),
        min_investment=floor,
        token_unit_price=unit,
        monthly_return_rate=money(monthly_return_rate),
        property_ref=(property_ref or "").strip() or None,
        annual_return_reference=money(annual_return_reference) if annual_return_reference is not None else None,
        status="OPEN",
    )
    db.add(item)
    db.flush()
    return item


def set_opportunity_property(db: Session, opportunity: FundingOpportunity, property_ref: str | None) -> FundingOpportunity:
    opportunity.property_ref = (property_ref or "").strip() or None
    db.add(opportunity)
    db.flush()
    return opportunity


def reserve_investment(db: Session, user: User, opportunity: FundingOpportunity, amount: Decimal) -> InvestmentReservation:
    if user.role not in {Role.RETAIL_INVESTOR, Role.INSTITUTIONAL_FUND}:
        raise HTTPException(status_code=403, detail="Perfil não habilitado para investimento")
    if opportunity.status != "OPEN":
        raise HTTPException(status_code=409, detail="Oportunidade não está aberta")

    value = money(amount)
    instrument = (opportunity.instrument_type or "TOKEN").upper()
    validate_instrument_amount(
        instrument_type=instrument,
        amount=value,
        token_unit=Decimal(str(opportunity.token_unit_price or 100)),
    )
    if value < Decimal(str(opportunity.min_investment)):
        raise HTTPException(status_code=422, detail="Valor abaixo do investimento mínimo da oportunidade")

    from sqlalchemy import func

    reserved = db.scalar(
        select(func.coalesce(func.sum(InvestmentReservation.amount), 0)).where(
            InvestmentReservation.opportunity_id == opportunity.id,
            InvestmentReservation.status.in_(["RESERVED", "CONFIRMED"]),
        )
    )
    if Decimal(str(reserved)) + value > Decimal(str(opportunity.target_amount)):
        raise HTTPException(status_code=409, detail="Reserva excede o saldo disponível da oportunidade")

    item = InvestmentReservation(
        organization_id=user.organization_id,
        opportunity_id=opportunity.id,
        investor_id=user.id,
        amount=value,
        instrument_type=instrument,
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe reserva ativa para este investidor") from None
    return item


def confirm_investment(db: Session, reservation: InvestmentReservation) -> InvestmentPosition:
    if reservation.status != "RESERVED":
        raise HTTPException(status_code=409, detail="Reserva não está pendente")
    opportunity = db.get(FundingOpportunity, reservation.opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada")

    reservation.status = "CONFIRMED"
    reservation.confirmed_at = datetime.now(UTC)
    amount = money(Decimal(str(reservation.amount)))
    opportunity.funded_amount = money(Decimal(str(opportunity.funded_amount)) + amount)
    if Decimal(str(opportunity.funded_amount)) >= Decimal(str(opportunity.target_amount)):
        opportunity.status = "FUNDED"

    instrument = (reservation.instrument_type or opportunity.instrument_type or "TOKEN").upper()
    unit = Decimal(str(opportunity.token_unit_price or 100))
    tokens_qty = _tokens_for(amount, unit) if instrument == "TOKEN" else None

    existing = db.scalar(
        select(InvestmentPosition).where(
            InvestmentPosition.opportunity_id == opportunity.id,
            InvestmentPosition.investor_id == reservation.investor_id,
        )
    )
    if existing:
        existing.principal = money(Decimal(str(existing.principal)) + amount)
        if tokens_qty is not None:
            existing.tokens_qty = int(existing.tokens_qty or 0) + tokens_qty
        if opportunity.property_ref and not existing.property_ref:
            existing.property_ref = opportunity.property_ref
        db.add(existing)
        db.flush()
        return existing

    position = InvestmentPosition(
        organization_id=reservation.organization_id,
        opportunity_id=opportunity.id,
        investor_id=reservation.investor_id,
        principal=amount,
        accrued_return=Decimal("0"),
        instrument_type=instrument,
        source="PLATFORM",
        tokens_qty=tokens_qty,
        property_ref=opportunity.property_ref,
        status="ACTIVE",
    )
    db.add(position)
    db.flush()
    return position


def manual_investment(
    db: Session,
    actor: User,
    *,
    opportunity_id: str,
    investor_id: str,
    amount: Decimal,
    instrument_type: str | None = None,
    property_ref: str | None = None,
    notes: str | None = None,
) -> InvestmentPosition:
    opportunity = db.scalar(
        select(FundingOpportunity).where(
            FundingOpportunity.id == opportunity_id,
            FundingOpportunity.organization_id == actor.organization_id,
        )
    )
    if not opportunity:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada")

    investor = db.scalar(
        select(User).where(User.id == investor_id, User.organization_id == actor.organization_id)
    )
    if not investor:
        raise HTTPException(status_code=404, detail="Investidor não encontrado")

    value = money(amount)
    instrument = (instrument_type or opportunity.instrument_type or "TOKEN").upper()
    validate_instrument_amount(
        instrument_type=instrument,
        amount=value,
        token_unit=Decimal(str(opportunity.token_unit_price or 100)),
    )

    unit = Decimal(str(opportunity.token_unit_price or 100))
    tokens_qty = _tokens_for(value, unit) if instrument == "TOKEN" else None
    prop = (property_ref or opportunity.property_ref or "").strip() or None

    existing = db.scalar(
        select(InvestmentPosition).where(
            InvestmentPosition.opportunity_id == opportunity.id,
            InvestmentPosition.investor_id == investor.id,
        )
    )
    if existing:
        existing.principal = money(Decimal(str(existing.principal)) + value)
        if tokens_qty is not None:
            existing.tokens_qty = int(existing.tokens_qty or 0) + tokens_qty
        if prop:
            existing.property_ref = prop
        if notes:
            existing.notes = ((existing.notes or "") + f"\n{notes}").strip()
        existing.source = existing.source or "MANUAL"
        existing.recorded_by_user_id = actor.id
        db.add(existing)
        position = existing
    else:
        position = InvestmentPosition(
            organization_id=actor.organization_id,
            opportunity_id=opportunity.id,
            investor_id=investor.id,
            principal=value,
            accrued_return=Decimal("0"),
            instrument_type=instrument,
            source="MANUAL",
            tokens_qty=tokens_qty,
            property_ref=prop,
            notes=(notes or "").strip() or None,
            recorded_by_user_id=actor.id,
            status="ACTIVE",
        )
        db.add(position)

    opportunity.funded_amount = money(Decimal(str(opportunity.funded_amount)) + value)
    if Decimal(str(opportunity.funded_amount)) >= Decimal(str(opportunity.target_amount)):
        opportunity.status = "FUNDED"
    db.add(opportunity)
    db.flush()
    return position


def manual_rentability(
    db: Session,
    actor: User,
    *,
    position_id: str,
    amount: Decimal,
    reference_month: str,
    notes: str | None = None,
) -> RentabilityCredit:
    position = db.scalar(
        select(InvestmentPosition).where(
            InvestmentPosition.id == position_id,
            InvestmentPosition.organization_id == actor.organization_id,
        )
    )
    if not position:
        raise HTTPException(status_code=404, detail="Posição não encontrada")

    value = money(amount)
    if value <= 0:
        raise HTTPException(status_code=422, detail="Valor de rentabilidade deve ser positivo")
    month = (reference_month or "").strip()
    if len(month) != 7 or month[4] != "-":
        raise HTTPException(status_code=422, detail="reference_month deve estar no formato YYYY-MM")

    credit = RentabilityCredit(
        organization_id=actor.organization_id,
        position_id=position.id,
        investor_id=position.investor_id,
        amount=value,
        reference_month=month,
        source="MANUAL",
        status="POSTED",
        notes=(notes or "").strip() or None,
        recorded_by_user_id=actor.id,
    )
    position.accrued_return = money(Decimal(str(position.accrued_return)) + value)
    db.add(credit)
    db.add(position)
    db.flush()
    return credit


def list_rentability_credits(db: Session, user: User) -> list[RentabilityCredit]:
    query = select(RentabilityCredit).where(RentabilityCredit.organization_id == user.organization_id)
    if user.role not in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF}:
        query = query.where(RentabilityCredit.investor_id == user.id)
    return list(db.scalars(query.order_by(RentabilityCredit.created_at.desc())))
