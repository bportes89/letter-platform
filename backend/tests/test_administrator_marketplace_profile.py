from app.administrator_marketplace_profile import (
    alienations_from_legacy_row,
    parse_legacy_ano_max,
    rules_patch_from_legacy_flags,
)


def test_parse_legacy_ano_max():
    assert parse_legacy_ano_max("") is None
    assert parse_legacy_ano_max("- - -") is None
    assert parse_legacy_ano_max("zero") == 0
    assert parse_legacy_ano_max("15") == 15


def test_alienations_from_legacy_row():
    row = {
        "cotas_categories": "[5,6]",
        "ano_fabricacao_max": '["10","zero"]',
    }
    items = alienations_from_legacy_row(row)
    assert len(items) == 2
    assert items[0]["legacy_quota_category_id"] == 5
    assert items[0]["max_vehicle_age_years"] == 10
    assert items[1]["max_vehicle_age_years"] == 0


def test_rules_patch_from_legacy_flags():
    patch = rules_patch_from_legacy_flags({"banco": 1, "correntista": 1, "nome_sujo": 0})
    assert patch["is_bank"] is True
    assert patch["requires_account_holder"] is True
    assert patch["accepts_dirty_name"] is False
