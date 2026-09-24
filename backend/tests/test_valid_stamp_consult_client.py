from app.valid_stamp_consult_client import consult, resolve_template_id, valid_stamp_consult_configured
from app.prismafy_templates import TEMPLATE_BY_SLUG


def test_valid_stamp_consult_not_configured_without_env():
    assert valid_stamp_consult_configured() is False
    ok, body = consult("gravame", {"placa": "ABC1D23"})
    assert ok is False
    assert body.get("error") == "VALID_STAMP_API_NOT_CONFIGURED"


def test_valid_stamp_consult_configured_flag(monkeypatch):
    monkeypatch.setattr("app.valid_stamp_consult_client.settings.valid_stamp_api_key", "psk_test")
    assert valid_stamp_consult_configured() is True


def test_resolve_template_gravame_alias():
    assert resolve_template_id("gravame") == TEMPLATE_BY_SLUG["t-gravame"]
    assert resolve_template_id("t-gravame") == TEMPLATE_BY_SLUG["t-gravame"]
