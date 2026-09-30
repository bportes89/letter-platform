from app.marketplace_cms_email_service import (
    MARKETPLACE_BOLETO_CLIENT,
    MARKETPLACE_DOCUMENT_SUPPLIER,
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


def test_resolve_uses_cms_supplier_template():
    class Row:
        subject = "FORNECEDOR TESTE {nome_cliente}"
        name_main = "x"
        body_html = "<p>Olá {fornecedor}, doc {nome_documento}</p>"
        sms = None
        whatsapp = None

    class FakeDb:
        def scalar(self, _q):
            return Row()

    subject, body = resolve_marketplace_email_template(
        FakeDb(),
        "org-1",
        MARKETPLACE_DOCUMENT_SUPPLIER,
        default_subject="fallback",
        default_body="fallback body",
    )
    assert "FORNECEDOR TESTE" in subject
    assert "{{client_name}}" in subject
    assert "{{supplier_name}}" in body
    assert "{{document_name}}" in body
