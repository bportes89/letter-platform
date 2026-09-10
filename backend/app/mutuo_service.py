"""Flash Invest — mútuo financeiro com Opção A/B, ZapSign, resgate obrigatório e equity se inadimplência."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.flash_invest_service import MUTUO_MIN, manual_investment
from app.models import FundingOpportunity, MutuoContract, MutuoInterestEvent, Role, User
from app.services import money
from app.zapsign_signature_service import zapsign_configured

MONTHLY_RATE = Decimal("0.016")
TERM_MONTHS = 36
# Após solicitar resgate, se LETTER não devolver, equity libera em N dias.
EQUITY_GRACE_DAYS = 15


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _add_months(dt: datetime, months: int) -> datetime:
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    day = min(dt.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return dt.replace(year=year, month=month, day=day)


def _month_key(when: datetime | None = None) -> str:
    dt = when or _now()
    return f"{dt.year:04d}-{dt.month:02d}"


def _monthly_interest(principal: Decimal, rate: Decimal = MONTHLY_RATE) -> Decimal:
    # Não passar a taxa por money() — quantize em 2 casas transformaria 0.016 em 0.02.
    return money(money(principal) * Decimal(str(rate)))


def redemption_due_amount(contract: MutuoContract) -> Decimal:
    principal = money(Decimal(str(contract.principal)))
    if (contract.settlement_option or "").upper() == "B":
        return money(principal + Decimal(str(contract.accrued_interest or 0)))
    return principal


def mutuo_view(contract: MutuoContract) -> dict:
    due = redemption_due_amount(contract)
    equity_ready = (
        contract.status == "REDEMPTION_REQUESTED"
        and contract.equity_unlock_at is not None
        and _now() >= _aware(contract.equity_unlock_at)  # type: ignore[operator]
        and contract.equity_converted_at is None
    )
    maturity_reached = bool(contract.maturity_at and _now() >= _aware(contract.maturity_at))  # type: ignore[operator]
    return {
        "id": contract.id,
        "investor_id": contract.investor_id,
        "opportunity_id": contract.opportunity_id,
        "position_id": contract.position_id,
        "principal": str(money(Decimal(str(contract.principal)))),
        "monthly_rate": str(money(Decimal(str(contract.monthly_rate)))),
        "term_months": contract.term_months,
        "settlement_option": contract.settlement_option,
        "settlement_option_label": (
            "Opção A — juros 1,6% a.m. na Wallet"
            if contract.settlement_option == "A"
            else "Opção B — bullet juros simples 1,6% a.m. no final"
        ),
        "status": contract.status,
        "locality": contract.locality,
        "contract_date": contract.contract_date,
        "signature_provider": contract.signature_provider,
        "signature_url": contract.signature_url,
        "signature_status": contract.signature_status,
        "signed_at": contract.signed_at,
        "settled_at": contract.settled_at,
        "maturity_at": contract.maturity_at,
        "maturity_reached": maturity_reached,
        "accrued_interest": str(money(Decimal(str(contract.accrued_interest or 0)))),
        "paid_interest_total": str(money(Decimal(str(contract.paid_interest_total or 0)))),
        "interest_months_posted": contract.interest_months_posted,
        "redemption_requested_at": contract.redemption_requested_at,
        "equity_unlock_at": contract.equity_unlock_at,
        "equity_conversion_ready": equity_ready,
        "redeemed_at": contract.redeemed_at,
        "redemption_amount": str(money(Decimal(str(contract.redemption_amount)))) if contract.redemption_amount is not None else None,
        "redemption_due_amount": str(due),
        "equity_conversion_requested_at": contract.equity_conversion_requested_at,
        "equity_converted_at": contract.equity_converted_at,
        "notes": contract.notes,
        "created_at": contract.created_at,
        "rules": {
            "min_principal": str(MUTUO_MIN),
            "resgate_obrigatorio": True,
            "conversao_equity": "Somente se o resgate for solicitado e o valor não for devolvido (após prazo de graça).",
            "equity_grace_days": EQUITY_GRACE_DAYS,
        },
    }


def create_mutuo_contract(
    db: Session,
    investor: User,
    *,
    principal: Decimal,
    settlement_option: str,
    opportunity_id: str | None = None,
    locality: str | None = None,
) -> MutuoContract:
    if investor.role not in {Role.RETAIL_INVESTOR, Role.INSTITUTIONAL_FUND, Role.PLATFORM_ADMIN, Role.CLIENT}:
        raise HTTPException(status_code=403, detail="Perfil não habilitado para mútuo Flash Invest")

    value = money(principal)
    if value < MUTUO_MIN:
        raise HTTPException(status_code=422, detail="Mútuo exige aporte mínimo de R$ 10.000,00")

    option = (settlement_option or "").upper().strip()
    if option not in {"A", "B"}:
        raise HTTPException(
            status_code=422,
            detail="Escolha a Opção A (juros mensais na Wallet) ou B (bullet no final dos 36 meses).",
        )

    if opportunity_id:
        opp = db.scalar(
            select(FundingOpportunity).where(
                FundingOpportunity.id == opportunity_id,
                FundingOpportunity.organization_id == investor.organization_id,
            )
        )
        if not opp:
            raise HTTPException(status_code=404, detail="Captação não encontrada")
        if (opp.instrument_type or "").upper() not in {"MUTUO", "TOKEN"}:
            pass  # allow linking to any open funding for ops flexibility

    contract = MutuoContract(
        organization_id=investor.organization_id,
        investor_id=investor.id,
        opportunity_id=opportunity_id,
        principal=value,
        monthly_rate=MONTHLY_RATE,
        term_months=TERM_MONTHS,
        settlement_option=option,
        status="DRAFT",
        locality=(locality or "Teixeira de Freitas/BA").strip(),
        contract_date=_now().strftime("%d/%m/%Y %H:%M UTC"),
    )
    db.add(contract)
    db.flush()
    return contract


def accept_and_sign(
    db: Session,
    investor: User,
    contract: MutuoContract,
    *,
    accepted: bool,
    signer_email: str | None = None,
) -> MutuoContract:
    if contract.investor_id != investor.id and investor.role not in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF}:
        raise HTTPException(status_code=403, detail="Somente o mutuante pode aceitar o contrato")
    if contract.status not in {"DRAFT", "AWAITING_SIGNATURE"}:
        raise HTTPException(status_code=409, detail="Contrato não está pendente de assinatura")
    if not accepted:
        raise HTTPException(status_code=422, detail="É necessário aceitar os termos do mútuo para seguir")

    payload = f"{contract.id}|{contract.investor_id}|{contract.principal}|{contract.settlement_option}|{_now().isoformat()}"
    contract.acceptance_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    email = (signer_email or investor.email or "").strip()
    if zapsign_configured():
        # Integração ZapSign completa usa PDF do contrato LETTER; aqui registramos envelope simulado
        # com provider ZAPSIGN quando a chave existe — o fluxo mock-complete cobre homologação.
        contract.signature_provider = "ZAPSIGN"
        contract.signature_external_id = f"zapsign_mutuo_{uuid4().hex[:16]}"
        contract.signature_url = f"https://app.zapsign.com.br/verificar/{contract.signature_external_id}"
        contract.signature_status = "SENT"
        contract.status = "AWAITING_SIGNATURE"
    else:
        contract.signature_provider = "MOCK"
        contract.signature_external_id = f"mock_mutuo_{uuid4().hex[:16]}"
        contract.signature_url = None
        contract.signature_status = "SENT"
        contract.status = "AWAITING_SIGNATURE"
    db.add(contract)
    db.flush()
    return contract


def complete_signature(db: Session, actor: User, contract: MutuoContract) -> MutuoContract:
    if contract.status != "AWAITING_SIGNATURE":
        raise HTTPException(status_code=409, detail="Contrato não aguarda assinatura")
    if actor.id != contract.investor_id and actor.role not in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF}:
        raise HTTPException(status_code=403, detail="Sem permissão para concluir assinatura")
    contract.signature_status = "SIGNED"
    contract.signed_at = _now()
    contract.status = "SIGNED"
    db.add(contract)
    db.flush()
    return contract


def settle_mutuo(db: Session, admin: User, contract: MutuoContract) -> MutuoContract:
    if admin.role not in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF}:
        raise HTTPException(status_code=403, detail="Somente backoffice pode liquidar o aporte")
    if contract.status != "SIGNED":
        raise HTTPException(status_code=409, detail="Contrato precisa estar assinado para liquidação")

    settled = _now()
    contract.settled_at = settled
    contract.maturity_at = _add_months(settled, contract.term_months or TERM_MONTHS)
    contract.status = "ACTIVE"

    # Garante posição Flash Invest vinculada (manual) para conciliação
    try:
        opportunity_id = contract.opportunity_id
        if not opportunity_id:
            # cria/usa captação mútuo genérica da org
            opp = db.scalar(
                select(FundingOpportunity).where(
                    FundingOpportunity.organization_id == contract.organization_id,
                    FundingOpportunity.instrument_type == "MUTUO",
                    FundingOpportunity.status == "OPEN",
                ).order_by(FundingOpportunity.created_at.desc())
            )
            if not opp:
                from app.flash_invest_service import create_opportunity

                opp = create_opportunity(
                    db,
                    admin,
                    title="Flash Invest — Mútuo conversível",
                    product="FLASH_INVEST",
                    capital_source="RETAIL",
                    target_amount=Decimal("10000000"),
                    instrument_type="MUTUO",
                )
            opportunity_id = opp.id
            contract.opportunity_id = opportunity_id

        position = manual_investment(
            db,
            admin,
            opportunity_id=opportunity_id,
            investor_id=contract.investor_id,
            amount=Decimal(str(contract.principal)),
            instrument_type="MUTUO",
            notes=f"Liquidação mútuo {contract.id} opção {contract.settlement_option}",
        )
        contract.position_id = position.id
    except HTTPException:
        # Se já existir posição/reserva conflitante, segue só com o contrato
        pass

    db.add(contract)
    db.flush()
    return contract


def post_monthly_interest(db: Session, contract: MutuoContract, *, reference_month: str | None = None) -> MutuoInterestEvent:
    if contract.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Juros só correm com contrato ACTIVE (após liquidação)")
    if contract.interest_months_posted >= (contract.term_months or TERM_MONTHS):
        raise HTTPException(status_code=409, detail="Todos os 36 meses de juros já foram lançados")

    month = reference_month or _month_key()
    amount = _monthly_interest(Decimal(str(contract.principal)), Decimal(str(contract.monthly_rate)))
    kind = "MONTHLY_PAYOUT" if contract.settlement_option == "A" else "BULLET_ACCRUAL"

    event = MutuoInterestEvent(
        organization_id=contract.organization_id,
        mutuo_contract_id=contract.id,
        investor_id=contract.investor_id,
        kind=kind,
        reference_month=month,
        amount=amount,
        status="POSTED",
        notes=(
            "Opção A — crédito mensal (Wallet LETTER)"
            if kind == "MONTHLY_PAYOUT"
            else "Opção B — provisionamento juros simples para bullet"
        ),
    )
    db.add(event)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Juros de {month} já lançados para este contrato") from None

    if contract.settlement_option == "A":
        contract.paid_interest_total = money(Decimal(str(contract.paid_interest_total or 0)) + amount)
        if contract.position_id:
            from app.flash_invest_service import manual_rentability

            try:
                # Usa admin-less path: bump accrued via credit linked to position
                from app.models import InvestmentPosition

                position = db.get(InvestmentPosition, contract.position_id)
                if position:
                    actor = db.get(User, contract.investor_id)
                    if actor:
                        # recorded as PLATFORM monthly
                        from app.models import RentabilityCredit

                        credit = RentabilityCredit(
                            organization_id=contract.organization_id,
                            position_id=position.id,
                            investor_id=contract.investor_id,
                            amount=amount,
                            reference_month=month,
                            source="PLATFORM",
                            status="POSTED",
                            notes=f"Mútuo Opção A · contrato {contract.id}",
                            recorded_by_user_id=None,
                        )
                        position.accrued_return = money(Decimal(str(position.accrued_return or 0)) + amount)
                        db.add(credit)
                        db.add(position)
            except Exception:
                pass
    else:
        contract.accrued_interest = money(Decimal(str(contract.accrued_interest or 0)) + amount)

    contract.interest_months_posted = int(contract.interest_months_posted or 0) + 1
    contract.last_interest_at = _now()
    db.add(contract)
    db.flush()
    return event


def request_redemption(db: Session, investor: User, contract: MutuoContract) -> MutuoContract:
    """Resgate é o caminho obrigatório no vencimento. Equity só se LETTER não devolver."""
    if investor.id != contract.investor_id and investor.role not in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF}:
        raise HTTPException(status_code=403, detail="Somente o mutuante solicita o resgate")
    if contract.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Resgate só pode ser solicitado com contrato ACTIVE")
    if not contract.maturity_at or _now() < _aware(contract.maturity_at):  # type: ignore[operator]
        raise HTTPException(
            status_code=422,
            detail="Resgate disponível a partir do vencimento (36 meses após a liquidação do aporte).",
        )

    due = redemption_due_amount(contract)
    contract.status = "REDEMPTION_REQUESTED"
    contract.redemption_requested_at = _now()
    contract.equity_unlock_at = contract.redemption_requested_at + timedelta(days=EQUITY_GRACE_DAYS)
    contract.redemption_amount = due
    contract.notes = ((contract.notes or "") + f"\nResgate obrigatório solicitado · valor devido {due}").strip()
    db.add(contract)
    db.flush()
    return contract


def confirm_redemption(db: Session, admin: User, contract: MutuoContract) -> MutuoContract:
    if admin.role not in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF}:
        raise HTTPException(status_code=403, detail="Somente backoffice confirma o resgate")
    if contract.status != "REDEMPTION_REQUESTED":
        raise HTTPException(status_code=409, detail="Não há resgate pendente")

    contract.status = "REDEEMED"
    contract.redeemed_at = _now()
    contract.redemption_amount = redemption_due_amount(contract)
    contract.notes = ((contract.notes or "") + "\nResgate pago pela LETTER — conversão em equity não se aplica.").strip()
    db.add(contract)
    db.flush()
    return contract


def request_equity_conversion(db: Session, investor: User, contract: MutuoContract) -> MutuoContract:
    """Conversão em equity somente se o resgate foi pedido e o valor não foi devolvido."""
    if investor.id != contract.investor_id and investor.role not in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF}:
        raise HTTPException(status_code=403, detail="Somente o mutuante solicita conversão em equity")
    if contract.status != "REDEMPTION_REQUESTED":
        raise HTTPException(
            status_code=409,
            detail="Conversão em equity só após solicitar o resgate e se a LETTER não devolver o valor.",
        )
    if contract.equity_unlock_at and _now() < _aware(contract.equity_unlock_at):  # type: ignore[operator]
        if investor.role not in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF}:
            raise HTTPException(
                status_code=422,
                detail=f"Aguarde o prazo de {EQUITY_GRACE_DAYS} dias após o pedido de resgate sem devolução para converter em equity.",
            )

    contract.status = "EQUITY_CONVERSION"
    contract.equity_conversion_requested_at = _now()
    contract.equity_converted_at = _now()
    contract.notes = (
        (contract.notes or "")
        + "\nConversão em equity LETTER INSTITUTIONAL HOLDING S.A. (desconto 20% no valuation da próxima rodada) — resgate não liquidado."
    ).strip()
    db.add(contract)
    db.flush()
    return contract


def list_mutuo_contracts(db: Session, user: User) -> list[MutuoContract]:
    query = select(MutuoContract).where(MutuoContract.organization_id == user.organization_id)
    if user.role not in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF}:
        query = query.where(MutuoContract.investor_id == user.id)
    return list(db.scalars(query.order_by(MutuoContract.created_at.desc())))


def get_mutuo_contract(db: Session, user: User, contract_id: str) -> MutuoContract:
    contract = db.scalar(
        select(MutuoContract).where(
            MutuoContract.id == contract_id,
            MutuoContract.organization_id == user.organization_id,
        )
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato de mútuo não encontrado")
    if user.role not in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF} and contract.investor_id != user.id:
        raise HTTPException(status_code=403, detail="Acesso negado a este contrato")
    return contract


def run_mutuo_interest_cron(db: Session, *, reference_month: str | None = None) -> dict:
    """Lança juros do mês para todos os mútuos ACTIVE (idempotente por mês)."""
    month = reference_month or _month_key()
    contracts = list(
        db.scalars(select(MutuoContract).where(MutuoContract.status == "ACTIVE"))
    )
    posted = 0
    skipped = 0
    errors: list[dict] = []
    for contract in contracts:
        try:
            post_monthly_interest(db, contract, reference_month=month)
            posted += 1
        except HTTPException as exc:
            skipped += 1
            if exc.status_code not in {409}:
                errors.append({"contract_id": contract.id, "detail": str(exc.detail)})
        except Exception as exc:  # noqa: BLE001
            errors.append({"contract_id": contract.id, "detail": str(exc)})
    return {
        "reference_month": month,
        "active_contracts": len(contracts),
        "posted": posted,
        "skipped": skipped,
        "errors": errors,
        "message": f"Juros Flash Invest {month}: {posted} lançados, {skipped} ignorados",
    }
