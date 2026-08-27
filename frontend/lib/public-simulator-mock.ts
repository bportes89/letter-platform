/** Simulação local do site público (demonstração — sem API). */

export type MmnPreview = {
  configured: boolean;
  message?: string;
  pool_rate_percent?: string;
  commission_pool?: string;
  holding_retained_from_fee?: string | null;
  base_type?: string;
};

export type FlashMockResult = {
  principal: string;
  platform_fee: string;
  itbi_provision: string;
  net_payout: string;
  monthly_payment: string;
  retail_rate_monthly: string;
  mmn: MmnPreview;
};

export type SdcMockResult = {
  formula_version: string;
  output: Record<string, string | number>;
  mmn: MmnPreview;
};

const money = (v: number) => Math.round(v * 100) / 100;
const str = (v: number) => money(v).toFixed(2);

function mmnPreview(base: number, poolRate: number, baseType: string, platformFee?: number): MmnPreview {
  const pool = money(base * poolRate / 100);
  return {
    configured: true,
    pool_rate_percent: String(poolRate),
    base_type: baseType,
    commission_pool: str(pool),
    holding_retained_from_fee: platformFee != null ? str(Math.max(0, platformFee - pool)) : null,
  };
}

function pricePayment(principal: number, ratePercent: number, months: number): number {
  const r = ratePercent / 100;
  const factor = (1 + r) ** months;
  return money(principal * r * factor / (factor - 1));
}

export function mockFlashPool(assetValue: number, requestedAmount?: number | null): FlashMockResult {
  const limit = money(assetValue * 0.4);
  let principal = requestedAmount != null && requestedAmount > 0 ? money(requestedAmount) : limit;
  if (principal > limit) throw new Error(`LTV máximo de 40% excedido; limite ${str(limit)}`);
  const platformFee = money(principal * 0.1);
  const itbi = money(principal * 0.03);
  const net = money(principal - platformFee - itbi);
  const retail = 2.5;
  return {
    principal: str(principal),
    platform_fee: str(platformFee),
    itbi_provision: str(itbi),
    net_payout: str(net),
    monthly_payment: str(pricePayment(principal, retail, 36)),
    retail_rate_monthly: String(retail),
    mmn: mmnPreview(net, 3, "NET_PAYOUT", platformFee),
  };
}

export function mockSdcPool(
  principal: number,
  durationMonths: number,
  category: "REAL_ESTATE" | "OTHER" = "REAL_ESTATE",
): SdcMockResult {
  const p = money(principal);
  const months = Math.max(1, Math.floor(durationMonths));
  const totalInterest = money(p * 0.045 * months);
  const startRate = category === "REAL_ESTATE" ? 0.03 : 0.05;
  const startTotal = money(p * startRate);
  const milestoneOne = category === "REAL_ESTATE" ? Math.min(startTotal, 1500) : startTotal;
  const milestoneTwo = money(startTotal - milestoneOne);
  const intermediation = money(p * 0.1);
  const capitalCommission = money(p * 0.01);
  const investorInterest = money(p * 0.025 * months);
  const platformSpread = money(totalInterest - investorInterest);
  return {
    formula_version: "sdc-bullet-v1-demo",
    output: {
      principal: str(p),
      duration_months: months,
      total_interest: str(totalInterest),
      investor_interest: str(investorInterest),
      platform_spread: str(platformSpread),
      maturity_total: str(p + totalInterest),
      start_fee_total: str(startTotal),
      start_fee_milestone_1: str(milestoneOne),
      start_fee_milestone_2: str(milestoneTwo),
      intermediation_fee: str(intermediation),
      capital_commission: str(capitalCommission),
      amortization: "BULLET",
      interest_model: "SIMPLE",
    },
    mmn: mmnPreview(intermediation, 3, "INTERMEDIATION_FEE"),
  };
}

export const DEMO_QUOTAS = [
  { id: "demo-q1", group_code: "1001", quota_code: "001", category: "REAL_ESTATE", credit_value: "400000.00", status: "AVAILABLE" },
  { id: "demo-q2", group_code: "1001", quota_code: "002", category: "REAL_ESTATE", credit_value: "400000.00", status: "AVAILABLE" },
] as const;
