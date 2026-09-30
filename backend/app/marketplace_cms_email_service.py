"""E-mails transacionais do marketplace — templates no CMS (`cms_texts`, kind=EMAIL)."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CmsText

MARKETPLACE_BOLETO_CLIENT = "MARKETPLACE_BOLETO_CLIENT"
MARKETPLACE_PAYMENT_CLIENT = "MARKETPLACE_PAYMENT_CLIENT"
MARKETPLACE_PAYMENT_PARTNER = "MARKETPLACE_PAYMENT_PARTNER"
MARKETPLACE_WELCOME_CLIENT = "MARKETPLACE_WELCOME_CLIENT"
MARKETPLACE_DOCUMENT_CLIENT = "MARKETPLACE_DOCUMENT_CLIENT"
MARKETPLACE_DOCUMENT_SUPPLIER = "MARKETPLACE_DOCUMENT_SUPPLIER"
MARKETPLACE_DOCUMENT_PLATFORM = "MARKETPLACE_DOCUMENT_PLATFORM"
MARKETPLACE_CONCLUDE_CLIENT = "MARKETPLACE_CONCLUDE_CLIENT"
MARKETPLACE_CONCLUDE_SUPPLIER = "MARKETPLACE_CONCLUDE_SUPPLIER"
MARKETPLACE_CONCLUDE_PARTNER = "MARKETPLACE_CONCLUDE_PARTNER"
MARKETPLACE_CONCLUDE_PLATFORM = "MARKETPLACE_CONCLUDE_PLATFORM"

CMS_SLUG_BY_COMM_KEY: dict[str, str] = {
    MARKETPLACE_BOLETO_CLIENT: "email-marketplace-boleto",
    MARKETPLACE_PAYMENT_CLIENT: "email-marketplace-payment-client",
    MARKETPLACE_PAYMENT_PARTNER: "email-marketplace-payment-partner",
    MARKETPLACE_WELCOME_CLIENT: "email-marketplace-welcome-client",
    MARKETPLACE_DOCUMENT_CLIENT: "email-marketplace-document-client",
    MARKETPLACE_DOCUMENT_SUPPLIER: "email-marketplace-document-supplier",
    MARKETPLACE_DOCUMENT_PLATFORM: "email-marketplace-document-platform",
    MARKETPLACE_CONCLUDE_CLIENT: "email-marketplace-conclude-client",
    MARKETPLACE_CONCLUDE_SUPPLIER: "email-marketplace-conclude-supplier",
    MARKETPLACE_CONCLUDE_PARTNER: "email-marketplace-conclude-partner",
    MARKETPLACE_CONCLUDE_PLATFORM: "email-marketplace-conclude-platform",
}

# Legado `texts.id` → slug canônico LETTER (import-legacy sincroniza corpo + assunto).
LEGACY_TEXT_ID_TO_SLUG: dict[int, str] = {
    1001: "email-marketplace-boleto",
    1005: "email-marketplace-payment-client",
    1007: "email-marketplace-payment-partner",
    1009: "email-marketplace-document-client",
    1010: "email-marketplace-document-supplier",
    1012: "email-marketplace-document-platform",
    1013: "email-marketplace-conclude-client",
    1014: "email-marketplace-conclude-supplier",
    1015: "email-marketplace-conclude-partner",
    1016: "email-marketplace-conclude-platform",
    1017: "email-marketplace-welcome-client",
    1019: "email-vender-cota-platform",
    1020: "email-vender-cota-client",
}

LEGACY_PLACEHOLDER_TO_LETTER: dict[str, str] = {
    "nome_cliente": "client_name",
    "email_cliente": "client_email",
    "valor_credito": "credit_value",
    "valor_entrada": "entrada_amount",
    "senha_cliente": "client_password",
    "nome_do_site": "site_name",
    "dominio": "site_domain",
    "link_dashboard": "portal_link",
    "fornecedor": "supplier_name",
    "administrador": "administrator_name",
    "parcelas": "installments",
    "data_compra": "purchase_date",
    "nome_documento": "document_name",
    "logo": "site_logo_html",
    "nome": "client_name",
    "data_cadastro": "purchase_date",
    "data_da_compra": "purchase_date",
}


def _html_to_plain(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_legacy_email_placeholders(text: str) -> str:
    """Converte `{nome_cliente}` legado para `{{client_name}}` usado no motor LETTER."""
    if not text:
        return text
    out = text
    for legacy_key, letter_key in LEGACY_PLACEHOLDER_TO_LETTER.items():
        out = out.replace("{" + legacy_key + "}", "{{" + letter_key + "}}")
    return out


def resolve_marketplace_email_template(
    db: Session,
    organization_id: str,
    comm_key: str,
    *,
    default_subject: str,
    default_body: str,
) -> tuple[str, str]:
    slug = CMS_SLUG_BY_COMM_KEY.get(comm_key)
    if not slug:
        return default_subject, default_body
    row = db.scalar(
        select(CmsText).where(
            CmsText.organization_id == organization_id,
            CmsText.slug == slug,
            CmsText.kind == "EMAIL",
            CmsText.active.is_(True),
        )
    )
    if not row:
        return default_subject, default_body
    subject = normalize_legacy_email_placeholders((row.subject or row.name_main or default_subject).strip())
    raw = (row.body_html or row.sms or row.whatsapp or "").strip()
    body_src = _html_to_plain(raw) if "<" in raw else raw
    body = normalize_legacy_email_placeholders(body_src or default_body)
    return subject or default_subject, body or default_body
