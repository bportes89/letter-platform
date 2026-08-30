"""Rentabilidade pool dos investidores (taxa única)."""

from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException


POOL_INVESTOR_RATE_PERCENT = Decimal("1.6")
POOL_INVESTOR_TAX_STATUS = "EXEMPT_NOT_WITHHELD"
POOL_INVESTOR_TAX_NOTE = (
    "Rentabilidade dos investidores do pool isenta de retenção na origem conforme política LETTER."
)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def resolve_pool_investor_rate(
    *,
    pool_investment_amount: Decimal | None,
    pool_investor_rate_percent: Decimal | None,
    max_rate: Decimal,
    default_rate: Decimal,
) -> tuple[Decimal, dict]:
    meta: dict = {
        "pool_investor_tax_status": POOL_INVESTOR_TAX_STATUS,
        "pool_investor_tax_note": POOL_INVESTOR_TAX_NOTE,
    }

    if pool_investor_rate_percent is not None:
        rate = pool_investor_rate_percent
        meta["pool_investor_rate_source"] = "MANUAL_CAMPAIGN_OVERRIDE"
    elif pool_investment_amount is not None:
        rate = POOL_INVESTOR_RATE_PERCENT
        amount = _money(pool_investment_amount)
        meta["pool_investor_rate_source"] = "POOL_FLAT"
        meta["pool_investor_tier"] = "FLAT"
        meta["pool_investor_tier_label"] = "1,6% a.m. (pool)"
        meta["pool_investment_amount"] = str(amount)
    else:
        rate = default_rate
        meta["pool_investor_rate_source"] = "PRODUCT_DEFAULT"

    if rate < Decimal("0") or rate > max_rate:
        raise HTTPException(
            status_code=422,
            detail=f"Repasse pool deve estar entre 0% e {max_rate}% (taxa total travada)",
        )
    meta["pool_investor_rate_percent"] = str(rate)
    return rate, meta
