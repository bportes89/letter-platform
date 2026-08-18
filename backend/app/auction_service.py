import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuctionBid, AuctionLot, AuctionQualification, AuctionSettlement,
    DelinquencyCase, Invoice, Proposal, Contract, RecoveredAsset, Role, User,
)


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def create_asset(db: Session, user: User, **data) -> RecoveredAsset:
    case_id = data.get("delinquency_case_id")
    if case_id:
        case = db.scalar(select(DelinquencyCase).where(
            DelinquencyCase.id == case_id,
            DelinquencyCase.organization_id == user.organization_id,
            DelinquencyCase.caducity_eligible.is_(True),
        ))
        if not case:
            raise HTTPException(status_code=422, detail="Caso não elegível para recuperação")
        invoice = db.get(Invoice, case.invoice_id)
        proposal = db.get(Proposal, invoice.proposal_id) if invoice else None
        contract = db.scalar(select(Contract).where(Contract.proposal_id == proposal.id)) if proposal else None
        if proposal and contract:
            from app.collateral_native_inspection_service import resolve_auction_photo_reference
            photo_ref = resolve_auction_photo_reference(db, proposal.id, contract.id)
            if photo_ref:
                gated = data.get("gated_details") or {}
                if isinstance(gated, dict):
                    gated.setdefault("native_inspection_vault_uri", photo_ref)
                    data["gated_details"] = gated
                if "vistoria nativa" not in data.get("public_description", "").lower():
                    data["public_description"] = (
                        f"{data['public_description']} · Laudo fotográfico nativo (conservação/vacância) vinculado."
                    )
    asset = RecoveredAsset(organization_id=user.organization_id, status="READY", **data)
    db.add(asset)
    return asset


def create_lot(db: Session, user: User, asset: RecoveredAsset, **data) -> AuctionLot:
    if asset.status != "READY":
        raise HTTPException(status_code=409, detail="Ativo não está pronto para leilão")
    starts_at, ends_at = aware(data["starts_at"]), aware(data["ends_at"])
    if ends_at <= starts_at:
        raise HTTPException(status_code=422, detail="Encerramento deve ser posterior à abertura")
    if Decimal(str(data["reserve_price"])) < Decimal(str(data["opening_price"])):
        raise HTTPException(status_code=422, detail="Preço de reserva não pode ser inferior ao inicial")
    lot = AuctionLot(
        organization_id=user.organization_id, asset_id=asset.id,
        lot_number=f"LOT-{datetime.now(UTC).strftime('%Y%m')}-{uuid4().hex[:6].upper()}",
        **data,
    )
    asset.status = "LISTED"
    db.add(lot)
    return lot


def activate_lot(lot: AuctionLot) -> AuctionLot:
    if lot.status != "SCHEDULED":
        raise HTTPException(status_code=409, detail="Lote não está agendado")
    if aware(lot.ends_at) <= datetime.now(UTC):
        raise HTTPException(status_code=409, detail="Período do leilão já encerrou")
    lot.status = "OPEN"
    return lot


def qualify(db: Session, user: User, lot: AuctionLot, confirmation: bool) -> AuctionQualification:
    if not confirmation:
        raise HTTPException(status_code=422, detail="Aceite expresso dos termos é obrigatório")
    if user.role not in {Role.RETAIL_INVESTOR, Role.INSTITUTIONAL_FUND}:
        raise HTTPException(status_code=403, detail="Perfil não habilitado para participar de leilões")
    existing = db.scalar(select(AuctionQualification).where(
        AuctionQualification.lot_id == lot.id, AuctionQualification.user_id == user.id,
    ))
    if existing:
        return existing
    item = AuctionQualification(organization_id=user.organization_id, lot_id=lot.id, user_id=user.id)
    db.add(item)
    return item


def gated_asset_details(db: Session, user: User, lot: AuctionLot) -> dict:
    qualification = db.scalar(select(AuctionQualification).where(
        AuctionQualification.lot_id == lot.id,
        AuctionQualification.user_id == user.id,
        AuctionQualification.status == "APPROVED",
    ))
    if not qualification and user.role != Role.PLATFORM_ADMIN:
        raise HTTPException(status_code=403, detail="Habilitação obrigatória para acessar os detalhes")
    asset = db.get(RecoveredAsset, lot.asset_id)
    return json.loads(asset.gated_details_json or "{}")


def place_bid(db: Session, user: User, lot: AuctionLot, amount: Decimal, idempotency_key: str) -> tuple[AuctionBid, bool]:
    replay = db.scalar(select(AuctionBid).where(AuctionBid.idempotency_key == idempotency_key))
    if replay:
        if replay.bidder_id != user.id or replay.lot_id != lot.id:
            raise HTTPException(status_code=409, detail="Chave idempotente já utilizada")
        return replay, False
    now = datetime.now(UTC)
    if lot.status != "OPEN" or now < aware(lot.starts_at) or now >= aware(lot.ends_at):
        raise HTTPException(status_code=409, detail="Lote não está aberto para lances")
    qualification = db.scalar(select(AuctionQualification).where(
        AuctionQualification.lot_id == lot.id,
        AuctionQualification.user_id == user.id,
        AuctionQualification.status == "APPROVED",
    ))
    if not qualification:
        raise HTTPException(status_code=403, detail="Participante não habilitado")
    highest = db.scalar(select(AuctionBid).where(
        AuctionBid.lot_id == lot.id, AuctionBid.status == "VALID",
    ).order_by(AuctionBid.amount.desc(), AuctionBid.placed_at).limit(1))
    minimum = Decimal(str(lot.opening_price)) if not highest else Decimal(str(highest.amount)) + Decimal(str(lot.min_increment))
    if amount < minimum:
        raise HTTPException(status_code=422, detail=f"Lance mínimo: {money(minimum)}")
    bid = AuctionBid(
        organization_id=user.organization_id, lot_id=lot.id, bidder_id=user.id,
        idempotency_key=idempotency_key, amount=money(amount),
    )
    db.add(bid)
    if aware(lot.ends_at) - now <= timedelta(minutes=lot.extension_minutes):
        lot.ends_at = aware(lot.ends_at) + timedelta(minutes=lot.extension_minutes)
    return bid, True


def settle_lot(db: Session, user: User, lot: AuctionLot) -> AuctionSettlement:
    existing = db.scalar(select(AuctionSettlement).where(AuctionSettlement.lot_id == lot.id))
    if existing:
        return existing
    winning = db.scalar(select(AuctionBid).where(
        AuctionBid.lot_id == lot.id, AuctionBid.status == "VALID",
    ).order_by(AuctionBid.amount.desc(), AuctionBid.placed_at).limit(1))
    if not winning:
        raise HTTPException(status_code=409, detail="Lote não possui lances válidos")
    if Decimal(str(winning.amount)) < Decimal(str(lot.reserve_price)):
        lot.status = "RESERVE_NOT_MET"
        raise HTTPException(status_code=409, detail="Preço de reserva não atingido")
    asset = db.get(RecoveredAsset, lot.asset_id)
    gross = money(Decimal(str(winning.amount)))
    costs = min(gross, money(Decimal(str(asset.recovery_costs))))
    fee = min(gross - costs, money(gross * Decimal(str(lot.platform_fee_percent)) / Decimal("100")))
    available = max(Decimal("0"), gross - costs - fee)
    debt_paid = min(available, money(Decimal(str(asset.debt_balance))))
    surplus = money(max(Decimal("0"), available - debt_paid))
    settlement = AuctionSettlement(
        organization_id=user.organization_id, lot_id=lot.id, winning_bid_id=winning.id,
        gross_amount=gross, recovery_costs=costs, debt_paid=debt_paid,
        platform_fee=fee, owner_surplus=surplus,
    )
    lot.status = "SETTLED"; lot.winning_bid_id = winning.id; asset.status = "LIQUIDATED"
    if asset.delinquency_case_id:
        case = db.get(DelinquencyCase, asset.delinquency_case_id)
        if case:
            case.status = "LIQUIDATED" if debt_paid >= Decimal(str(asset.debt_balance)) else "PARTIALLY_RECOVERED"
            invoice = db.get(Invoice, case.invoice_id)
            if invoice:
                invoice.status = "RECOVERED" if case.status == "LIQUIDATED" else "PARTIALLY_RECOVERED"
    db.add(settlement)
    return settlement
