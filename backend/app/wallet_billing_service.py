"""Cobrança mensal Escrow, inadimplência e retenção de entradas."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.asaas_common import asaas_configured
from app.asaas_wallet_service import subaccount_client
from app.core.config import settings
from app.models import EscrowAccount, EscrowBillingCycle, EscrowEvent, User
from app.services import money, post_double_entry
from app.wallet_pricing_service import customer_fee_for, resolve_incoming_fee_code

MONTHLY_FEE_DESCRIPTION = "Tarifa Mensal de Manutenção de Plataforma Escrow"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def get_billing_cycle(db: Session, account: EscrowAccount) -> EscrowBillingCycle | None:
    if not account.escrow_enabled:
        return None
    return db.scalar(select(EscrowBillingCycle).where(EscrowBillingCycle.escrow_account_id == account.id))


def billing_cycle_view(cycle: EscrowBillingCycle | None) -> dict | None:
    if not cycle:
        return None
    return {
        "status": cycle.status,
        "monthly_amount": str(cycle.monthly_amount),
        "next_billing_at": cycle.next_billing_at.isoformat() if cycle.next_billing_at else None,
        "last_billed_at": cycle.last_billed_at.isoformat() if cycle.last_billed_at else None,
        "outstanding_amount": str(cycle.outstanding_amount),
        "billing_blocked": cycle.billing_blocked,
        "delinquent_since": cycle.delinquent_since.isoformat() if cycle.delinquent_since else None,
    }


def ensure_escrow_billing_cycle(db: Session, account: EscrowAccount) -> EscrowBillingCycle | None:
    if not settings.wallet_escrow_billing_enabled or not account.escrow_enabled:
        return None
    existing = get_billing_cycle(db, account)
    if existing:
        return existing
    now = datetime.now(UTC)
    cycle = EscrowBillingCycle(
        organization_id=account.organization_id,
        escrow_account_id=account.id,
        monthly_amount=float(settings.wallet_escrow_monthly_fee),
        next_billing_at=now + timedelta(days=settings.wallet_billing_cycle_days),
        status="ACTIVE",
        outstanding_amount=0,
        billing_blocked=False,
    )
    db.add(cycle)
    db.flush()
    return cycle


def assert_withdrawals_allowed(db: Session, account: EscrowAccount) -> None:
    cycle = get_billing_cycle(db, account)
    if cycle and cycle.billing_blocked and Decimal(str(cycle.outstanding_amount or 0)) > 0:
        raise HTTPException(
            status_code=422,
            detail=(
                "Conta inadimplente — saques e pagamentos bloqueados até quitar "
                f"R$ {money(Decimal(str(cycle.outstanding_amount)))} de mensalidade Escrow."
            ),
        )


def _is_mock_account(account: EscrowAccount) -> bool:
    return account.provider in {"MOCK", "MOCK_SUBACCOUNT"} or not asaas_configured()


def _transfer_fee_to_master(account: EscrowAccount, amount: Decimal, description: str) -> dict | None:
    if _is_mock_account(account) or not settings.asaas_wallet_id:
        return None
    with subaccount_client(account) as client:
        return client.create_transfer(
            {
                "value": float(amount),
                "walletId": settings.asaas_wallet_id,
                "description": description,
            }
        )


def _record_platform_fee(
    db: Session,
    user: User,
    account: EscrowAccount,
    *,
    reference: str,
    event_type: str,
    description: str,
    amount: Decimal,
    operation_id: str | None = None,
) -> None:
    if amount <= 0:
        return
    post_double_entry(
        db,
        user,
        reference=reference,
        event_type=event_type,
        description=description,
        debit_account="ESCROW_CASH",
        credit_account="PLATFORM_FEE_REVENUE",
        amount=amount,
        operation_id=operation_id or account.operation_id,
    )


def _apply_retention(
    db: Session,
    user: User,
    account: EscrowAccount,
    cycle: EscrowBillingCycle,
    gross: Decimal,
    event_id: str,
) -> tuple[Decimal, Decimal]:
    outstanding = money(Decimal(str(cycle.outstanding_amount or 0)))
    if outstanding <= 0:
        return gross, Decimal("0")

    retain = min(gross, outstanding)
    credited = money(gross - retain)
    cycle.outstanding_amount = float(money(outstanding - retain))
    if cycle.outstanding_amount <= 0:
        cycle.billing_blocked = False
        cycle.status = "ACTIVE"
        cycle.delinquent_since = None
        now = datetime.now(UTC)
        if _aware(cycle.next_billing_at) <= now:
            cycle.next_billing_at = now + timedelta(days=settings.wallet_billing_cycle_days)

    db.add(
        EscrowEvent(
            organization_id=account.organization_id,
            escrow_account_id=account.id,
            provider_event_id=f"billing_ret_{event_id}",
            event_type="BILLING_RETENTION",
            amount=float(retain),
            payload_json=json.dumps(
                {"outstanding_after": str(cycle.outstanding_amount), "gross": str(gross)},
                ensure_ascii=False,
            ),
        )
    )
    _record_platform_fee(
        db,
        user,
        account,
        reference=f"BILLING_RETENTION:{event_id}",
        event_type="BILLING_RETENTION",
        description="Retenção por inadimplência Escrow",
        amount=retain,
    )
    return credited, retain


def credit_escrow_incoming(
    db: Session,
    user: User,
    account: EscrowAccount,
    event_id: str,
    event_type: str,
    amount: Decimal,
    metadata: dict,
) -> tuple[EscrowEvent, bool]:
    existing = db.scalar(select(EscrowEvent).where(EscrowEvent.provider_event_id == event_id))
    if existing:
        return existing, False
    if event_type not in {"FUNDS_CONFIRMED", "PAYMENT_RECEIVED"}:
        raise HTTPException(status_code=422, detail="Evento suportado: FUNDS_CONFIRMED ou PAYMENT_RECEIVED")

    gross = money(amount)
    fee_code = resolve_incoming_fee_code(event_type, metadata)
    fee = customer_fee_for(fee_code, gross)
    net = money(gross - fee)
    cycle = get_billing_cycle(db, account)
    credited = net
    retained = Decimal("0")

    if cycle and cycle.billing_blocked and Decimal(str(cycle.outstanding_amount or 0)) > 0:
        credited, retained = _apply_retention(db, user, account, cycle, net, event_id)

    account.available_balance = money(Decimal(str(account.available_balance)) + credited)

    event = EscrowEvent(
        organization_id=user.organization_id,
        escrow_account_id=account.id,
        provider_event_id=event_id,
        event_type=event_type,
        amount=float(credited),
        payload_json=json.dumps(
            {
                **metadata,
                "gross_amount": str(gross),
                "platform_fee": str(fee),
                "fee_code": fee_code,
                "retained_for_billing": str(retained),
            },
            ensure_ascii=False,
            default=str,
        ),
    )
    db.add(event)

    post_double_entry(
        db,
        user,
        reference=f"ESCROW:{event_id}",
        event_type=event_type,
        description="Entrada confirmada em escrow",
        debit_account="ESCROW_CASH",
        credit_account="CLIENT_FUNDS_PAYABLE",
        amount=credited,
        operation_id=account.operation_id,
    )
    if fee > 0:
        _record_platform_fee(
            db,
            user,
            account,
            reference=f"TX_FEE:{event_id}",
            event_type="PAYMENT_FEE",
            description=f"Taxa de recebimento ({fee_code})",
            amount=fee,
        )
        db.add(
            EscrowEvent(
                organization_id=account.organization_id,
                escrow_account_id=account.id,
                provider_event_id=f"tx_fee_{event_id}",
                event_type="PAYMENT_FEE",
                amount=float(fee),
                payload_json=json.dumps({"source_event": event_id, "fee_code": fee_code}, ensure_ascii=False),
            )
        )
        try:
            _transfer_fee_to_master(account, fee, f"Taxa LETTER ({fee_code})")
        except Exception:
            pass

    return event, True


def _charge_from_balance(
    db: Session,
    user: User,
    account: EscrowAccount,
    cycle: EscrowBillingCycle,
    amount: Decimal,
) -> bool:
    balance = money(Decimal(str(account.available_balance or 0)))
    if balance < amount:
        return False

    account.available_balance = money(balance - amount)
    provider_ref = f"escrow_monthly_{uuid4().hex[:12]}"
    db.add(
        EscrowEvent(
            organization_id=account.organization_id,
            escrow_account_id=account.id,
            provider_event_id=provider_ref,
            event_type="ESCROW_MONTHLY_FEE",
            amount=float(amount),
            payload_json=json.dumps({"description": MONTHLY_FEE_DESCRIPTION}, ensure_ascii=False),
        )
    )
    _record_platform_fee(
        db,
        user,
        account,
        reference=f"ESCROW_MONTHLY:{provider_ref}",
        event_type="ESCROW_MONTHLY_FEE",
        description=MONTHLY_FEE_DESCRIPTION,
        amount=amount,
    )
    try:
        _transfer_fee_to_master(account, amount, MONTHLY_FEE_DESCRIPTION)
    except Exception:
        pass

    now = datetime.now(UTC)
    cycle.last_billed_at = now
    cycle.next_billing_at = now + timedelta(days=settings.wallet_billing_cycle_days)
    cycle.outstanding_amount = 0
    cycle.billing_blocked = False
    cycle.status = "ACTIVE"
    cycle.delinquent_since = None
    return True


def _mark_delinquent(cycle: EscrowBillingCycle, monthly_amount: Decimal) -> None:
    outstanding = money(Decimal(str(cycle.outstanding_amount or 0)))
    if outstanding <= 0:
        cycle.outstanding_amount = float(monthly_amount)
    cycle.billing_blocked = True
    cycle.status = "DELINQUENT"
    if not cycle.delinquent_since:
        cycle.delinquent_since = datetime.now(UTC)


def process_due_escrow_billing(db: Session) -> dict:
    if not settings.wallet_escrow_billing_enabled:
        return {"processed": 0, "items": [], "enabled": False}

    now = datetime.now(UTC)
    cycles = list(
        db.scalars(
            select(EscrowBillingCycle)
            .join(EscrowAccount, EscrowBillingCycle.escrow_account_id == EscrowAccount.id)
            .where(
                EscrowBillingCycle.next_billing_at <= now,
                EscrowAccount.escrow_enabled.is_(True),
            )
        )
    )
    items: list[dict] = []
    for cycle in cycles:
        if _aware(cycle.next_billing_at) > now:
            continue
        account = db.get(EscrowAccount, cycle.escrow_account_id)
        if not account:
            continue
        actor = db.scalar(select(User).where(User.organization_id == account.organization_id).limit(1))
        if not actor:
            continue

        monthly_amount = money(Decimal(str(cycle.monthly_amount or settings.wallet_escrow_monthly_fee)))
        outstanding = money(Decimal(str(cycle.outstanding_amount or 0)))
        total_due = monthly_amount if outstanding <= 0 else outstanding

        if outstanding > 0 and Decimal(str(account.available_balance or 0)) >= outstanding:
            if _charge_from_balance(db, actor, account, cycle, outstanding):
                items.append({"account_id": account.id, "status": "OUTSTANDING_PAID", "amount": str(outstanding)})
                continue

        if outstanding <= 0:
            if _charge_from_balance(db, actor, account, cycle, monthly_amount):
                items.append({"account_id": account.id, "status": "PAID", "amount": str(monthly_amount)})
            else:
                _mark_delinquent(cycle, monthly_amount)
                items.append(
                    {
                        "account_id": account.id,
                        "status": "DELINQUENT",
                        "outstanding": str(monthly_amount),
                    }
                )
        else:
            combined = money(outstanding + monthly_amount)
            if _charge_from_balance(db, actor, account, cycle, combined):
                items.append({"account_id": account.id, "status": "PAID", "amount": str(combined)})
            else:
                cycle.outstanding_amount = float(combined)
                _mark_delinquent(cycle, combined)
                items.append({"account_id": account.id, "status": "DELINQUENT", "outstanding": str(combined)})

    return {"processed": len(items), "items": items, "enabled": True}


def run_wallet_escrow_billing_job(db: Session, *, organization_id: str | None = None) -> dict:
    result = process_due_escrow_billing(db)
    result["organization_id"] = organization_id
    result["synced_at"] = datetime.now(UTC).isoformat()
    return result
