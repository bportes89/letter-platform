"""Parâmetros contábeis e de inventário TAPAF — Inventário NINA v4.0."""

from decimal import Decimal

TAPAF_NOMINAL = Decimal("1500.00")
TAPAF_LOTE_A_API_RESERVE = Decimal("300.00")
TAPAF_LOTE_B_FRANCHISE_SPREAD = Decimal("1200.00")

LEASE_EQUITY_TAPAF_NOMINAL = Decimal("750.00")

# Estimativa de custo por pauta (Lote A) — doc v4.0
TAPAF_ESTIMATED_API_COSTS = {
    "ONR_SERP": Decimal("60.00"),
    "DATAZAP_AVM": Decimal("10.00"),
    "SERASA_QSA": Decimal("40.00"),
    "JUDIS_TRIBUNALS": Decimal("30.00"),
}
TAPAF_ESTIMATED_TOTAL_API_COST = sum(TAPAF_ESTIMATED_API_COSTS.values(), Decimal("0"))
TAPAF_ESTIMATED_INFRA_MARGIN = TAPAF_LOTE_A_API_RESERVE - TAPAF_ESTIMATED_TOTAL_API_COST

LEDGER_TAPAF_POOL = "TAPAF_SETTLEMENT_POOL"
LEDGER_API_PREPAID = "API_PREPAID_RESERVE"
LEDGER_FRANCHISE_UPFRONT = "FRANCHISE_UPFRONT_SPREAD"
LEDGER_BAAS_CLEARING = "BAAS_CLEARING"

INFRA_PROVIDER_CATALOG = [
    {"code": "ONR_SERP", "name": "ONR / SERP", "category": "REGISTRY", "estimated_cost_brl": "60.00"},
    {"code": "DATAZAP_AVM", "name": "DataZap AVM", "category": "APPRAISAL", "estimated_cost_brl": "10.00"},
    {"code": "SERASA_QSA", "name": "Serasa Experian QSA", "category": "CREDIT", "estimated_cost_brl": "40.00"},
    {"code": "JUDIS_TRIBUNALS", "name": "Judis / Digivox", "category": "LEGAL", "estimated_cost_brl": "30.00"},
    {"code": "INFOSIMPLES_CND", "name": "InfoSimples CNDs", "category": "COMPLIANCE", "estimated_cost_brl": "0.00"},
    {"code": "SERPRO_DENATRAN", "name": "SERPRO Denatran/Vio", "category": "VEHICLE", "estimated_cost_brl": "0.00"},
    {"code": "FIPE_CLOUD", "name": "Fipe API Cloud", "category": "VEHICLE", "estimated_cost_brl": "0.00"},
    {"code": "MOLICAR", "name": "Molicar B2B", "category": "VEHICLE", "estimated_cost_brl": "0.00"},
    {"code": "INCRA_PIGT", "name": "INCRA PIGT / SNCR", "category": "RURAL", "estimated_cost_brl": "0.00"},
]


def compute_tapaf_split(total: Decimal) -> dict[str, str]:
    total = total.quantize(Decimal("0.01"))
    ratio_a = TAPAF_LOTE_A_API_RESERVE / TAPAF_NOMINAL
    ratio_b = TAPAF_LOTE_B_FRANCHISE_SPREAD / TAPAF_NOMINAL
    lote_a = (total * ratio_a).quantize(Decimal("0.01"))
    lote_b = (total - lote_a).quantize(Decimal("0.01"))
    return {
        "total_brl": str(total),
        "lote_a_api_reserve_brl": str(lote_a),
        "lote_b_franchise_spread_brl": str(lote_b),
        "split_basis": "300/1200 sobre base R$ 1.500 (proporcional para outros valores)",
    }
