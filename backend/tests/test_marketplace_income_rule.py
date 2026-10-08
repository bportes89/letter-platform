import json
from decimal import Decimal

from app.administrator_service import DEFAULT_RULES
from app.marketplace_service import admin_profile_blockers
from app.models import Administrator


def _admin_with_tight_bacen_margin() -> Administrator:
    rules = dict(DEFAULT_RULES)
    rules["min_income_to_installment_ratio"] = 3
    rules["approval_rules"] = dict(rules["approval_rules"])
    rules["approval_rules"]["min_income_margin"] = 0.10
    return Administrator(
        name="Test Admin",
        code="TEST_ADMIN",
        document="11111111000111",
        authorization_status="AUTHORIZED",
        rules_json=json.dumps(rules),
    )


def test_marketplace_income_rule_uses_three_x_installment_not_bacen_margin():
    """Robô/cartas: renda ≥ 3× parcela; margem Bacen não endurece o teto no Marketplace."""
    admin = _admin_with_tight_bacen_margin()
    common = {
        "category": "REAL_ESTATE",
        "asset_year": 2020,
        "asset_is_zero_km": False,
        "has_credit_restriction": False,
        "credit_total": Decimal("150000"),
        "installment_total": Decimal("8000"),
        "monthly_income": Decimal("50000"),
        "asset_value": Decimal("150000"),
        "target_amount": Decimal("150000"),
        "combo_size": 1,
    }
    with_bacen = admin_profile_blockers(admin, marketplace_income_rule=False, **common)
    marketplace = admin_profile_blockers(admin, marketplace_income_rule=True, **common)
    assert with_bacen, "margem Bacen 10% exige renda 10× parcela (8k → bloqueia)"
    assert not marketplace, "Marketplace deve aceitar com renda 3× (teto ~16,6k para parcela 8k)"
