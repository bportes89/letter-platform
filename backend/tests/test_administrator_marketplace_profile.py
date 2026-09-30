import json
from unittest.mock import MagicMock

from app.administrator_marketplace_profile import (
    alienation_row_for_quota,
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


def test_alienation_row_matches_parent_category():
    admin = MagicMock()
    admin.rules_json = json.dumps(
        {"alienations": [{"quota_category_id": "parent-1", "max_vehicle_age_years": 10}]},
        ensure_ascii=False,
    )
    quota = MagicMock()
    quota.quota_category_id = "child-9"
    db = MagicMock()
    cat = MagicMock()
    cat.parent_id = "parent-1"
    db.get.return_value = cat
    row = alienation_row_for_quota(db, admin, quota)
    assert row is not None
    assert row.get("max_vehicle_age_years") == 10


def test_alienation_row_blocks_unknown_subcategory():
    admin = MagicMock()
    admin.rules_json = json.dumps(
        {"alienations": [{"quota_category_id": "parent-1", "max_vehicle_age_years": None}]},
        ensure_ascii=False,
    )
    quota = MagicMock()
    quota.quota_category_id = "other-99"
    db = MagicMock()
    cat = MagicMock()
    cat.parent_id = "other-parent"
    db.get.return_value = cat
    assert alienation_row_for_quota(db, admin, quota) == {}
