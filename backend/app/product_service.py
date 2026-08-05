import json
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CalculationMemory, Proposal, Quota, User
from app.services import validate_quota_combination


HUNDRED = Decimal("100")
TWELVE = Decimal("12")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def decimal_string(value: Decimal) -> str:
    return str(money(value))


def persist_calculation(
    db: Session, user: User, proposal: Proposal, formula_version: str,
    input_data: dict, output_data: dict,
) -> CalculationMemory:
    current = db.scalar(
        select(func.max(CalculationMemory.version)).where(CalculationMemory.proposal_id == proposal.id)
    ) or 0
    calculation = CalculationMemory(
        organization_id=user.organization_id,
        proposal_id=proposal.id,
        version=current + 1,
        product=proposal.product,
        input_json=json.dumps(input_data, ensure_ascii=False),
        output_json=json.dumps(output_data, ensure_ascii=False),
        formula_version=formula_version,
    )
    db.add(calculation)
    proposal.calculation_version = f"{formula_version}.{current + 1}"
    proposal.terms_json = json.dumps(
        {**json.loads(proposal.terms_json or "{}"), "calculation": output_data}, ensure_ascii=False,
    )
    return calculation


def calculate_sdc(
    db: Session, user: User, proposal: Proposal, quotas: list[Quota], duration_months: int,
) -> CalculationMemory:
    if proposal.product != "SDC":
        raise HTTPException(status_code=422, detail="A proposta deve ser do produto SDC")
    validated = validate_quota_combination(quotas, float(proposal.requested_amount))
    if not validated["valid"]:
        raise HTTPException(
            status_code=422,
            detail=f"Combinação fora da tolerância de ±10%: {validated['deviation_percent']}%",
        )
    principal = money(sum((Decimal(str(q.credit_value)) for q in quotas), Decimal("0")))
    category = validated["category"]
    start_rate = Decimal("3") if category == "REAL_ESTATE" else Decimal("5")
    total_interest = money(principal * Decimal("4.5") / HUNDRED * duration_months)
    investor_interest = money(principal * Decimal("2.5") / HUNDRED * duration_months)
    platform_spread = money(principal * Decimal("2.0") / HUNDRED * duration_months)
    start_fee_total = money(principal * start_rate / HUNDRED)
    milestone_one = min(start_fee_total, Decimal("1500.00")) if category == "REAL_ESTATE" else start_fee_total
    milestone_two = money(start_fee_total - milestone_one)
    intermediation_fee = money(principal * Decimal("10") / HUNDRED)
    capital_commission = money(principal * Decimal("1") / HUNDRED)
    maturity_total = money(principal + total_interest)
    input_data = {
        "quota_ids": [q.id for q in quotas], "duration_months": duration_months,
        "interest_rate_monthly": "4.5", "investor_rate_monthly": "2.5",
        "platform_spread_rate_monthly": "2.0", "start_fee_rate": str(start_rate),
    }
    output_data = {
        "principal": decimal_string(principal), "duration_months": duration_months,
        "total_interest": decimal_string(total_interest),
        "investor_interest": decimal_string(investor_interest),
        "platform_spread": decimal_string(platform_spread),
        "maturity_total": decimal_string(maturity_total),
        "start_fee_total": decimal_string(start_fee_total),
        "start_fee_milestone_1": decimal_string(milestone_one),
        "start_fee_milestone_2": decimal_string(milestone_two),
        "intermediation_fee": decimal_string(intermediation_fee),
        "capital_commission": decimal_string(capital_commission),
        "category": category, "administrator_id": validated["administrator_id"],
        "deviation_percent": validated["deviation_percent"], "amortization": "BULLET",
    }
    return persist_calculation(db, user, proposal, "sdc-bullet-v1", input_data, output_data)


def price_payment(principal: Decimal, monthly_rate: Decimal, months: int) -> Decimal:
    factor = (Decimal("1") + monthly_rate) ** months
    return money(principal * monthly_rate * factor / (factor - Decimal("1")))


def calculate_flash_credit(
    db: Session, user: User, proposal: Proposal, asset_value: Decimal, capital_source: str,
    term_months: int, ipca_annual: Decimal,
) -> CalculationMemory:
    if proposal.product != "FLASH_CREDIT":
        raise HTTPException(status_code=422, detail="A proposta deve ser do produto FLASH_CREDIT")
    principal = money(Decimal(str(proposal.requested_amount)))
    asset = money(asset_value)
    ltv = money(principal / asset * HUNDRED)
    if ltv > Decimal("40"):
        raise HTTPException(status_code=422, detail=f"LTV máximo de 40% excedido: {ltv}%")
    if term_months not in {36, 60}:
        raise HTTPException(status_code=422, detail="Prazo deve ser de 36 ou 60 meses")
    if capital_source not in {"RETAIL", "INSTITUTIONAL"}:
        raise HTTPException(status_code=422, detail="Fonte deve ser RETAIL ou INSTITUTIONAL")

    itbi_provision = money(principal * Decimal("3") / HUNDRED)
    structuring_fee = money(principal * Decimal("7") / HUNDRED)
    net_payout = money(principal - itbi_provision - structuring_fee)
    balloon_month = 36 if term_months == 60 else None
    output: dict = {
        "principal": decimal_string(principal), "asset_value": decimal_string(asset),
        "ltv_percent": decimal_string(ltv), "term_months": term_months,
        "capital_source": capital_source, "itbi_provision": decimal_string(itbi_provision),
        "structuring_fee": decimal_string(structuring_fee), "net_payout": decimal_string(net_payout),
        "balloon_month": balloon_month,
    }
    if capital_source == "RETAIL":
        monthly_rate = Decimal("2.5") / HUNDRED
        payment = price_payment(principal, monthly_rate, term_months)
        balance = principal
        balance_at_balloon = Decimal("0")
        for month in range(1, min(term_months, 36) + 1):
            interest = balance * monthly_rate
            balance = max(Decimal("0"), balance - (payment - interest))
            if month == 36:
                balance_at_balloon = money(balance)
        total_before_balloon = money(payment * min(term_months, 36))
        balloon = balance_at_balloon if term_months == 60 else Decimal("0")
        total_contract = money(total_before_balloon + balloon)
        output.update({
            "amortization": "PRICE", "monthly_rate_percent": "2.50",
            "monthly_payment": decimal_string(payment), "balloon_payment": decimal_string(balloon),
            "total_contract": decimal_string(total_contract),
            "investor_rate_percent": "1.60", "platform_spread_rate_percent": "0.90",
        })
    else:
        annual_rate = Decimal("14") + ipca_annual
        total_interest = money(principal * annual_rate / HUNDRED * Decimal(term_months) / TWELVE)
        monthly_payment = money((principal + total_interest) / term_months)
        management_fee = money(principal * Decimal("0.5") / HUNDRED * Decimal(term_months) / TWELVE)
        output.update({
            "amortization": "LINEAR_INDEXED", "base_rate_annual_percent": "14.00",
            "ipca_annual_percent": decimal_string(ipca_annual),
            "combined_rate_annual_percent": decimal_string(annual_rate),
            "total_interest": decimal_string(total_interest),
            "monthly_payment": decimal_string(monthly_payment),
            "management_fee_total": decimal_string(management_fee),
            "total_contract": decimal_string(principal + total_interest), "balloon_payment": "0.00",
        })
    input_data = {
        "asset_value": decimal_string(asset), "capital_source": capital_source,
        "term_months": term_months, "ipca_annual_percent": decimal_string(ipca_annual),
    }
    return persist_calculation(db, user, proposal, "flash-credit-v1", input_data, output)
