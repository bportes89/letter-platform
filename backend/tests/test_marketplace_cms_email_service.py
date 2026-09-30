from app.marketplace_cms_email_service import (
    MARKETPLACE_BOLETO_CLIENT,
    _html_to_plain,
    normalize_legacy_email_placeholders,
    resolve_marketplace_email_template,
)


def test_html_to_plain_breaks_lines():
    assert "linha" in _html_to_plain("<p>linha<br>duas</p>")


def test_normalize_legacy_placeholders():
    raw = "Olá {nome_cliente}, crédito {valor_credito}"
    assert "{{client_name}}" in normalize_legacy_email_placeholders(raw)
    assert "{{credit_value}}" in normalize_legacy_email_placeholders(raw)


def test_resolve_falls_back_without_db_row():
    class FakeDb:
        def scalar(self, _q):
            return None

    subject, body = resolve_marketplace_email_template(
        FakeDb(),
        "org-1",
        MARKETPLACE_BOLETO_CLIENT,
        default_subject="Subj",
        default_body="Corpo {{client_name}}",
    )
    assert subject == "Subj"
    assert "Corpo" in body
