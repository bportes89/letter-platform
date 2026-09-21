from app.valid_stamp_consult_client import consult, valid_stamp_consult_configured


def test_valid_stamp_consult_not_configured_without_env():
    assert valid_stamp_consult_configured() is False
    ok, body = consult("/v1/test", {})
    assert ok is False
    assert body.get("error") == "VALID_STAMP_API_NOT_CONFIGURED"


def test_valid_stamp_consult_configured_flag(monkeypatch):
    monkeypatch.setattr("app.valid_stamp_consult_client.settings.valid_stamp_api_key", "psk_test")
    monkeypatch.setattr(
        "app.valid_stamp_consult_client.settings.valid_stamp_api_base_url",
        "https://example.test",
    )
    assert valid_stamp_consult_configured() is True
