"""Apuração mensal SaaS + taxas bancárias — fechamento dia 1–30, pagamento dia 10."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RecurringCommissionAccrual, User
from app.network_service import money
from app.universal_mmn_service import (
    PAYOUT_MONTHLY_D10,
    allocate_universal_mmn,
)

NETWORK_POOL_PERCENT = Decimal("30")


def accrual_period_for(dt: datetime | None = None) -> str:
    when = dt or datetime.now(UTC)
    return when.strftime("%Y-%m")


def _default_settlement_period(dt: datetime | None = None) -> str:
    """No dia 10 liquida o fechamento do mês anterior (apurado do dia 1 ao 30)."""
    when = dt or datetime.now(UTC)
    year = when.year
    month = when.month - 1
    if month < 1:
        month = 12
        year -= 1
    return f"{year}-{month:02d}"


def record_recurring_accrual(
    db: Session,
    *,
    organization_id: str,
    source_type: str,
    source_reference: str,
    originator_id: str | None,
    gross_amount: Decimal,
    accrual_period: str | None = None,
) -> RecurringCommissionAccrual:
    period = accrual_period or accrual_period_for()
    pool = money(gross_amount * NETWORK_POOL_PERCENT / Decimal("100"))
    existing = db.scalar(
        select(RecurringCommissionAccrual).where(
            RecurringCommissionAccrual.organization_id == organization_id,
            RecurringCommissionAccrual.source_type == source_type,
            RecurringCommissionAccrual.source_reference == source_reference,
            RecurringCommissionAccrual.accrual_period == period,
        )
    )
    if existing:
        return existing
    item = RecurringCommissionAccrual(
        organization_id=organization_id,
        accrual_period=period,
        source_type=source_type,
        source_reference=source_reference,
        originator_id=originator_id,
        gross_amount=float(gross_amount),
        network_pool_amount=float(pool),
        status="ACCRUED",
    )
    db.add(item)
    db.flush()
    return item


def settle_recurring_period(
    db: Session,
    actor: User,
    accrual_period: str | None = None,
    *,
    source_types: tuple[str, ...] = ("LSS_SUBSCRIPTION", "WALLET_FEE"),
) -> dict:
    """Liquida apuração do período (executar no dia 10)."""
    period = accrual_period or _default_settlement_period()
    rows = list(
        db.scalars(
            select(RecurringCommissionAccrual).where(
                RecurringCommissionAccrual.organization_id == actor.organization_id,
                RecurringCommissionAccrual.accrual_period == period,
                RecurringCommissionAccrual.status == "ACCRUED",
                RecurringCommissionAccrual.source_type.in_(source_types),
            )
        )
    )
    settled = 0
    skipped = 0
    for row in rows:
        if not row.originator_id or Decimal(str(row.network_pool_amount or 0)) <= 0:
            row.status = "SKIPPED"
            skipped += 1
            continue
        reference = f"RECURRING-{row.source_type}-{row.accrual_period}-{row.id[:8]}"
        allocate_universal_mmn(
            db,
            actor,
            originator_id=row.originator_id,
            proposal_id=None,
            reference=reference,
            product=row.source_type,
            commission_type="SALES",
            pool_amount=Decimal(str(row.network_pool_amount)),
            pool_rate_percent=NETWORK_POOL_PERCENT,
            calculation_base=Decimal(str(row.gross_amount)),
            payout_schedule=PAYOUT_MONTHLY_D10,
        )
        row.status = "SETTLED"
        row.settled_at = datetime.now(UTC)
        row.settlement_reference = reference
        settled += 1
    db.flush()
    return {
        "accrual_period": period,
        "settled": settled,
        "skipped": skipped,
        "total_rows": len(rows),
    }


def run_monthly_recurring_settlement_job(
    db: Session,
    actor: User,
    *,
    accrual_period: str | None = None,
) -> dict:
    return settle_recurring_period(db, actor, accrual_period)
