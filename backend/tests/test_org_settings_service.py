from app.org_settings_service import LEGACY_FIELD_ALIASES, SETTING_GROUPS


def test_legacy_aliases_map_price():
    assert LEGACY_FIELD_ALIASES["price"] == "platform_commission_percent"


def test_setting_groups_include_contract_template():
    keys = {item["key"] for items in SETTING_GROUPS.values() for item in items}
    assert "marketplace_contract_html" in keys
    assert "platform_commission_percent" in keys
