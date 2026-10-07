from app.org_settings_service import (
    LEGACY_FIELD_ALIASES,
    SETTING_GROUP_META,
    SETTING_GROUPS,
    _merge_import_setting_value,
)


def test_legacy_aliases_map_price():
    assert LEGACY_FIELD_ALIASES["price"] == "platform_commission_percent"


def test_merge_import_setting_value_whatsapp_dupes():
    assert _merge_import_setting_value("", "Olá") == "Olá"
    assert _merge_import_setting_value("Olá", "") == "Olá"


def test_setting_groups_include_contract_template():
    keys = {item["key"] for items in SETTING_GROUPS.values() for item in items}
    assert "marketplace_contract_html" in keys
    assert "platform_commission_percent" in keys


def test_setting_group_meta_documents_mmn_vs_platform_fee():
    assert "payments" in SETTING_GROUP_META
    assert "MMN" in SETTING_GROUP_META["payments"]["summary"]
    pay_fields = {f["key"]: f for f in SETTING_GROUPS["payments"]}
    assert "hint" in pay_fields["platform_commission_percent"]
    assert "Fornecedores" in pay_fields["platform_commission_percent"]["hint"]
