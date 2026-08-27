import json
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CalculationMemory, FlashCreditPolicy, Proposal, Quota, User
from app.pool_investor_tiers import resolve_pool_investor_rate
from app.services import validate_quota_combination


HUNDRED = Decimal("100")
TWELVE = Decimal("12")
FLASH_CAPITAL_PRODUCT = "FLASH_CREDIT"  # identificador interno preservado; exibição: Flash Capital


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


def build_sdc_simulation_output(
    quotas: list[Quota],
    requested_amount: float,
    duration_months: int,
    capital_source: str = "POOL",
    pool_investor_rate_percent: Decimal | None = None,
    pool_investment_amount: Decimal | None = None,
) -> tuple[str, dict, dict]:
    if capital_source not in {"POOL", "FUND"}:
        raise HTTPException(status_code=422, detail="Fonte SDC deve ser POOL ou FUND")
    validated = validate_quota_combination(quotas, requested_amount)
    if not validated["valid"]:
        raise HTTPException(
            status_code=422,
            detail=f"Combinação fora da tolerância de ±10%: {validated['deviation_percent']}%",
        )
    principal = money(sum((Decimal(str(q.credit_value)) for q in quotas), Decimal("0")))
    category = validated["category"]
    start_rate = Decimal("3") if category == "REAL_ESTATE" else Decimal("5")
    monthly_interest_rate = Decimal("4.5")
    total_interest = money(principal * monthly_interest_rate / HUNDRED * duration_months)
    if capital_source == "FUND":
        investor_rate = monthly_interest_rate
        platform_rate = Decimal("0")
        investor_interest = total_interest
        platform_spread = money(Decimal("0"))
        pool_meta: dict = {}
    else:
        default_investor = Decimal("2.5")
        investor_rate, pool_meta = resolve_pool_investor_rate(
            pool_investment_amount=pool_investment_amount,
            pool_investor_rate_percent=pool_investor_rate_percent,
            max_rate=monthly_interest_rate,
            default_rate=default_investor,
        )
        platform_rate = money(monthly_interest_rate - investor_rate)
        investor_interest = money(principal * investor_rate / HUNDRED * duration_months)
        platform_spread = money(principal * platform_rate / HUNDRED * duration_months)
    start_fee_total = money(principal * start_rate / HUNDRED)
    milestone_one = min(start_fee_total, Decimal("1500.00")) if category == "REAL_ESTATE" else start_fee_total
    milestone_two = money(start_fee_total - milestone_one)
    intermediation_fee = money(principal * Decimal("10") / HUNDRED)
    capital_commission = money(principal * Decimal("1") / HUNDRED)
    maturity_total = money(principal + total_interest)
    formula_version = "sdc-bullet-v2" if capital_source == "FUND" else "sdc-bullet-v1"
    input_data = {
        "quota_ids": [q.id for q in quotas], "duration_months": duration_months,
        "capital_source": capital_source,
        "interest_rate_monthly": str(monthly_interest_rate),
        "investor_rate_monthly": str(investor_rate),
        "platform_spread_rate_monthly": str(platform_rate),
        "pool_investor_rate_override": str(pool_investor_rate_percent) if pool_investor_rate_percent is not None else None,
        "pool_investment_amount": pool_meta.get("pool_investment_amount"),
        "start_fee_rate": str(start_rate),
        **pool_meta,
    }
    output_data = {
        "principal": decimal_string(principal), "duration_months": duration_months,
        "capital_source": capital_source,
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
        "interest_model": "SIMPLE",
        **pool_meta,
    }
    return formula_version, input_data, output_data


def calculate_sdc(
    db: Session, user: User, proposal: Proposal, quotas: list[Quota], duration_months: int,
    capital_source: str = "POOL",
    pool_investor_rate_percent: Decimal | None = None,
    pool_investment_amount: Decimal | None = None,
) -> CalculationMemory:
    if proposal.product != "SDC":
        raise HTTPException(status_code=422, detail="A proposta deve ser do produto SDC")
    formula_version, input_data, output_data = build_sdc_simulation_output(
        quotas, float(proposal.requested_amount), duration_months, capital_source,
        pool_investor_rate_percent, pool_investment_amount,
    )
    return persist_calculation(db, user, proposal, formula_version, input_data, output_data)


def price_payment(principal: Decimal, monthly_rate: Decimal, months: int) -> Decimal:
    factor = (Decimal("1") + monthly_rate) ** months
    return money(principal * monthly_rate * factor / (factor - Decimal("1")))


def pool_monthly_schedule(
    principal: Decimal, payment: Decimal, monthly_rate: Decimal,
    investor_rate: Decimal, platform_rate: Decimal, months: int,
) -> list[dict]:
    balance = principal
    schedule: list[dict] = []
    for month in range(1, months + 1):
        opening = balance
        interest = money(opening * monthly_rate)
        investor_share = money(opening * investor_rate)
        platform_share = money(opening * platform_rate)
        amortization = money(max(Decimal("0"), payment - interest))
        balance = money(max(Decimal("0"), opening - amortization))
        schedule.append({
            "month": month,
            "opening_balance": decimal_string(opening),
            "installment": decimal_string(payment),
            "interest": decimal_string(interest),
            "investor_share": decimal_string(investor_share),
            "platform_share": decimal_string(platform_share),
            "common_fund_amortization": decimal_string(amortization),
            "closing_balance": decimal_string(balance),
            "common_fund_destination": "PLATFORM_INVESTMENT_ESCROW_FOR_POOL_REIMBURSEMENT",
        })
    return schedule


def fund_monthly_schedule(
    principal: Decimal, base_annual_rate: Decimal, ipca_annual: Decimal, months: int,
) -> tuple[Decimal, Decimal, list[dict]]:
    annual_rate = base_annual_rate + ipca_annual
    total_interest = money(principal * annual_rate / HUNDRED * Decimal(months) / TWELVE)
    payment = money((principal + total_interest) / months)
    balance = principal
    schedule: list[dict] = []
    for month in range(1, months + 1):
        if month in {13, 25}:
            payment = money(payment * (Decimal("1") + ipca_annual / HUNDRED))
        opening = balance
        interest = money(opening * annual_rate / HUNDRED / TWELVE)
        amortization = money(max(Decimal("0"), payment - interest))
        balance = money(max(Decimal("0"), opening - amortization))
        schedule.append({
            "month": month,
            "opening_balance": decimal_string(opening),
            "installment": decimal_string(payment),
            "interest": decimal_string(interest),
            "principal_amortization": decimal_string(amortization),
            "closing_balance": decimal_string(balance),
            "ipca_adjusted": month in {13, 25},
            "annual_rate_percent": decimal_string(annual_rate),
        })
    management_fee = money(principal * Decimal("0.5") / HUNDRED * Decimal(months) / TWELVE)
    return payment, management_fee, schedule


def calculate_flash_credit(
    db: Session, user: User, proposal: Proposal, asset_value: Decimal, capital_source: str,
    term_months: int, ipca_annual: Decimal,
    pool_investor_rate_percent: Decimal | None = None,
    pool_investment_amount: Decimal | None = None,
) -> CalculationMemory:
    if proposal.product != FLASH_CAPITAL_PRODUCT:
        raise HTTPException(status_code=422, detail="A proposta deve ser do produto Flash Capital")
    policy = db.scalar(
        select(FlashCreditPolicy).where(
            FlashCreditPolicy.organization_id == user.organization_id,
            FlashCreditPolicy.status == "ACTIVE",
        ).order_by(FlashCreditPolicy.version.desc())
    )
    max_ltv = Decimal(str(policy.max_ltv_percent)) if policy else Decimal("40")
    institutional_base = Decimal(str(policy.institutional_rate_annual)) if policy else Decimal("14")
    retail_rate = Decimal(str(policy.retail_rate_monthly)) if policy else Decimal("2.5")
    default_investor = Decimal(str(policy.investor_rate_monthly)) if policy else Decimal("1.6")
    treasury_spread = Decimal(str(policy.treasury_spread_monthly)) if policy else Decimal("0.9")
    platform_fee_percent = Decimal(str(policy.intermediation_fee_percent)) if policy else Decimal("10")
    itbi_percent = Decimal("3")
    pool_meta: dict = {}
    if capital_source == "RETAIL":
        investor_rate, pool_meta = resolve_pool_investor_rate(
            pool_investment_amount=pool_investment_amount,
            pool_investor_rate_percent=pool_investor_rate_percent,
            max_rate=retail_rate,
            default_rate=default_investor,
        )
        treasury_spread = money(retail_rate - investor_rate)
    principal = money(Decimal(str(proposal.requested_amount)))
    asset = money(asset_value)
    ltv = money(principal / asset * HUNDRED)
    if ltv > max_ltv:
        raise HTTPException(status_code=422, detail=f"LTV máximo de {max_ltv}% excedido: {ltv}%")
    if term_months not in {36, 60}:
        raise HTTPException(status_code=422, detail="Prazo deve ser de 36 ou 60 meses")
    if capital_source not in {"RETAIL", "INSTITUTIONAL"}:
        raise HTTPException(status_code=422, detail="Fonte deve ser RETAIL (pool) ou INSTITUTIONAL (fundo)")

    platform_fee = money(principal * platform_fee_percent / HUNDRED)
    itbi_provision = money(principal * itbi_percent / HUNDRED)
    net_payout = money(principal - platform_fee - itbi_provision)
    partner_commission_base = net_payout
    balloon_month = 36 if term_months == 60 else None
    output: dict = {
        "principal": decimal_string(principal), "asset_value": decimal_string(asset),
        "ltv_percent": decimal_string(ltv), "term_months": term_months,
        "capital_source": capital_source, "product_label": "Flash Capital",
        "platform_fee_percent": decimal_string(platform_fee_percent),
        "platform_fee": decimal_string(platform_fee),
        "structuring_fee": decimal_string(platform_fee),
        "itbi_percent": decimal_string(itbi_percent),
        "itbi_provision": decimal_string(itbi_provision),
        "net_payout": decimal_string(net_payout),
        "partner_commission_base": decimal_string(partner_commission_base),
        "interest_basis": "NOMINAL_PRINCIPAL",
        "interest_basis_note": "Juros e amortização Price calculados sobre o valor nominal alavancado (principal).",
        "partner_commission_basis_note": "Comissão da rede (MMN) calculada sobre o líquido remanescente ao cliente após fee da plataforma e ITBI.",
        "balloon_month": balloon_month,
    }
    if capital_source == "RETAIL":
        monthly_rate = retail_rate / HUNDRED
        investor_rate_m = investor_rate / HUNDRED
        platform_rate_m = treasury_spread / HUNDRED
        payment = price_payment(principal, monthly_rate, term_months)
        schedule_months = min(term_months, 36)
        schedule = pool_monthly_schedule(
            principal, payment, monthly_rate, investor_rate_m, platform_rate_m, schedule_months,
        )
        balance_at_balloon = Decimal(schedule[-1]["closing_balance"]) if schedule else Decimal("0")
        total_before_balloon = money(payment * schedule_months)
        balloon = balance_at_balloon if term_months == 60 else Decimal("0")
        total_contract = money(total_before_balloon + balloon)
        output.update({
            "amortization": "PRICE", "monthly_rate_percent": decimal_string(retail_rate),
            "monthly_payment": decimal_string(payment), "balloon_payment": decimal_string(balloon),
            "total_contract": decimal_string(total_contract),
            "investor_rate_percent": decimal_string(investor_rate),
            "platform_spread_rate_percent": decimal_string(treasury_spread),
            "monthly_schedule": schedule,
            "split_basis": f"POOL_MONTHLY: investidor {investor_rate}% + plataforma {treasury_spread}% sobre juros; fundo comum amortiza saldo",
            "pool_investor_rate_override": str(pool_investor_rate_percent) if pool_investor_rate_percent is not None else None,
            **pool_meta,
        })
    else:
        payment, management_fee, schedule = fund_monthly_schedule(
            principal, institutional_base, ipca_annual, term_months,
        )
        annual_rate = institutional_base + ipca_annual
        total_interest = money(principal * annual_rate / HUNDRED * Decimal(term_months) / TWELVE)
        output.update({
            "amortization": "LINEAR_INDEXED", "base_rate_annual_percent": decimal_string(institutional_base),
            "ipca_annual_percent": decimal_string(ipca_annual),
            "combined_rate_annual_percent": decimal_string(annual_rate),
            "total_interest": decimal_string(total_interest),
            "monthly_payment": decimal_string(payment),
            "management_fee_total": decimal_string(management_fee),
            "total_contract": decimal_string(principal + total_interest),
            "balloon_payment": "0.00",
            "monthly_schedule": schedule,
            "ipca_adjustment": "ANNUAL_AT_MONTHS_13_AND_25",
        })
    input_data = {
        "asset_value": decimal_string(asset), "capital_source": capital_source,
        "term_months": term_months, "ipca_annual_percent": decimal_string(ipca_annual),
        "platform_fee_percent": decimal_string(platform_fee_percent),
        "itbi_percent": decimal_string(itbi_percent),
        "pool_investor_rate_override": str(pool_investor_rate_percent) if pool_investor_rate_percent is not None else None,
        "pool_investment_amount": pool_meta.get("pool_investment_amount"),
        **pool_meta,
    }
    output["policy_version"] = policy.version if policy else 1
    output["borrower_eligibility"] = "PJ_ONLY"
    formula_version = "flash-capital-v3"
    return persist_calculation(db, user, proposal, formula_version, input_data, output)
