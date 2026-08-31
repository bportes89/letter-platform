"""Parâmetros versionados de simulação Flash Capital (taxas da mesa FinOps)."""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.flash_valid_lss_service import approve_flash_policy, create_flash_policy
from app.models import FlashCreditPolicy, User

DEFAULT_INSTITUTIONAL_RATE_ANNUAL = Decimal("14")
DEFAULT_RETAIL_RATE_MONTHLY = Decimal("2.5")
DEFAULT_FRUICAO_RATE_MONTHLY = Decimal("2.5")
DEFAULT_IPCA_PROJECTED_PERCENT = Decimal("4.5")


def _rate_str(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _format_br_rate(value: Decimal, suffix: str) -> str:
    text = format(value.normalize(), "f").rstrip("0").rstrip(".")
    return text.replace(".", ",") + suffix


def flash_capital_rate_labels(institutional: Decimal, retail: Decimal) -> dict[str, str]:
    fruicao = _format_br_rate(retail, "% a.m.")
    label = f"Fruição — {fruicao} (pool e fundo)"
    _ = institutional
    return {"funds": label, "pool": label}


def get_active_flash_simulation_params(db: Session, organization_id: str) -> dict:
    policy = db.scalar(
        select(FlashCreditPolicy).where(
            FlashCreditPolicy.organization_id == organization_id,
            FlashCreditPolicy.status == "ACTIVE",
        ).order_by(FlashCreditPolicy.version.desc())
    )
    institutional = (
        Decimal(str(policy.institutional_rate_annual))
        if policy
        else DEFAULT_INSTITUTIONAL_RATE_ANNUAL
    )
    retail = (
        Decimal(str(policy.retail_rate_monthly))
        if policy
        else DEFAULT_RETAIL_RATE_MONTHLY
    )
    return {
        "institutional_rate_annual": _rate_str(institutional),
        "retail_rate_monthly": _rate_str(retail),
        "default_ipca_projected_percent": _rate_str(DEFAULT_IPCA_PROJECTED_PERCENT),
        "labels": flash_capital_rate_labels(institutional, retail),
        "source": "policy" if policy else "defaults",
        "policy_id": policy.id if policy else None,
        "policy_version": policy.version if policy else None,
        "nota": (
            "Taxas configuradas manualmente na mesa FinOps. "
            "A simulação usa estes parâmetros automaticamente; "
            "o IPCA projetado informado na simulação representa o índice esperado para reajuste."
        ),
    }


def save_flash_simulation_params(
    db: Session,
    user: User,
    *,
    institutional_rate_annual: Decimal,
    retail_rate_monthly: Decimal,
) -> FlashCreditPolicy:
    latest = db.scalar(
        select(FlashCreditPolicy).where(
            FlashCreditPolicy.organization_id == user.organization_id,
        ).order_by(FlashCreditPolicy.version.desc())
    )
    next_version = db.scalar(
        select(func.max(FlashCreditPolicy.version)).where(
            FlashCreditPolicy.organization_id == user.organization_id,
        )
    )
    version = int(next_version or 0) + 1
    base = latest or FlashCreditPolicy(organization_id=user.organization_id)
    item = create_flash_policy(
        db,
        user,
        version=version,
        status="DRAFT",
        max_ltv_percent=base.max_ltv_percent if latest else Decimal("40"),
        institutional_rate_annual=institutional_rate_annual,
        retail_rate_monthly=retail_rate_monthly,
        investor_rate_monthly=base.investor_rate_monthly if latest else Decimal("1.6"),
        treasury_spread_monthly=base.treasury_spread_monthly if latest else Decimal("0.9"),
        auction_steps_json=base.auction_steps_json if latest else "[100,80,70,60]",
        auction_floor_percent=base.auction_floor_percent if latest else Decimal("60"),
        intermediation_fee_percent=base.intermediation_fee_percent if latest else Decimal("10"),
    )
    approve_flash_policy(db, user, item)
    db.flush()
    return item
