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


_SLUG_TO_LEGACY_ID: dict[str, int] = {slug: lid for lid, slug in LEGACY_TEXT_ID_TO_SLUG.items()}

# Corpo com placeholders legado `{nome_cliente}` — normalizados na leitura para `{{client_name}}`.
MARKETPLACE_EMAIL_TEMPLATE_SEEDS: dict[str, dict[str, str | int]] = {
    "email-marketplace-boleto": {
        "name_main": "Marketplace — Boleto entrada (1001)",
        "subject": "Boleto da entrada — {nome_do_site}",
        "body_html": (
            "<p>Olá {nome_cliente},</p>"
            "<p>Segue o boleto/PIX da entrada da sua carta contemplada.</p>"
            "<p>Entrada: {valor_entrada}<br>Crédito: {valor_credito}</p>"
            "<p>Acesse seu escritório: {link_dashboard}</p><p>{nome_do_site}</p>"
        ),
        "sort_order": 1001,
    },
    "email-marketplace-payment-client": {
        "name_main": "Marketplace — Pagamento confirmado cliente (1005)",
        "subject": "Pagamento confirmado — {nome_do_site}",
        "body_html": (
            "<p>Olá {nome_cliente},</p>"
            "<p>Confirmamos o pagamento da entrada.</p>"
            "<p>Crédito: {valor_credito}</p>"
            "<p>{link_dashboard}</p><p>{nome_do_site}</p>"
        ),
        "sort_order": 1005,
    },
    "email-marketplace-payment-partner": {
        "name_main": "Marketplace — Pagamento confirmado parceiro (1007)",
        "subject": "Entrada paga — cliente {nome_cliente}",
        "body_html": (
            "<p>Olá,</p>"
            "<p>O cliente {nome_cliente} quitou a entrada.</p>"
            "<p>Crédito: {valor_credito}</p><p>LETTER</p>"
        ),
        "sort_order": 1007,
    },
    "email-marketplace-welcome-client": {
        "name_main": "Marketplace — Boas-vindas cliente (1017)",
        "subject": "Bem-vindo — {nome_do_site}",
        "body_html": (
            "<p>Olá {nome_cliente},</p>"
            "<p>Sua conta foi criada.</p>"
            "<p>E-mail: {email_cliente}<br>Senha: {senha_cliente}</p>"
            "<p>{link_dashboard}</p><p>{nome_do_site}</p>"
        ),
        "sort_order": 1017,
    },
    "email-marketplace-document-client": {
        "name_main": "Marketplace — Documento recebido cliente (1009)",
        "subject": "Documento recebido — {nome_do_site}",
        "body_html": (
            "<p>Olá {nome_cliente},</p>"
            "<p>Recebemos o documento {nome_documento} da sua compra.</p>"
            "<p>Crédito: {valor_credito}</p>"
            "<p>{link_dashboard}</p><p>{nome_do_site}</p>"
        ),
        "sort_order": 1009,
    },
    "email-marketplace-document-supplier": {
        "name_main": "Marketplace — Documento fornecedor (1010)",
        "subject": "Documento do cliente — {nome_cliente}",
        "body_html": (
            "<p>Olá {fornecedor},</p>"
            "<p>O cliente {nome_cliente} enviou o documento {nome_documento}.</p>"
            "<p>Crédito: {valor_credito}</p><p>LETTER</p>"
        ),
        "sort_order": 1010,
    },
    "email-marketplace-document-platform": {
        "name_main": "Marketplace — Documento plataforma (1012)",
        "subject": "Documento recebido — {nome_cliente}",
        "body_html": (
            "<p>Novo documento na venda.</p>"
            "<p>Cliente: {nome_cliente}<br>Documento: {nome_documento}<br>Crédito: {valor_credito}</p>"
            "<p>{nome_do_site}</p>"
        ),
        "sort_order": 1012,
    },
    "email-marketplace-conclude-client": {
        "name_main": "Marketplace — Conclusão cliente (1013)",
        "subject": "Processo concluído — {nome_do_site}",
        "body_html": (
            "<p>Olá {nome_cliente},</p>"
            "<p>Sua compra foi concluída com sucesso.</p>"
            "<p>Crédito: {valor_credito}</p><p>{nome_do_site}</p>"
        ),
        "sort_order": 1013,
    },
    "email-marketplace-conclude-supplier": {
        "name_main": "Marketplace — Conclusão fornecedor (1014)",
        "subject": "Venda concluída — {nome_cliente}",
        "body_html": (
            "<p>Olá {fornecedor},</p>"
            "<p>A venda vinculada foi concluída.</p>"
            "<p>Cliente: {nome_cliente} · Crédito: {valor_credito}</p><p>LETTER</p>"
        ),
        "sort_order": 1014,
    },
    "email-marketplace-conclude-partner": {
        "name_main": "Marketplace — Conclusão parceiro (1015)",
        "subject": "Venda concluída — {nome_cliente}",
        "body_html": (
            "<p>Olá,</p>"
            "<p>A venda do cliente {nome_cliente} foi concluída.</p>"
            "<p>Crédito: {valor_credito}</p><p>LETTER</p>"
        ),
        "sort_order": 1015,
    },
    "email-marketplace-conclude-platform": {
        "name_main": "Marketplace — Conclusão plataforma (1016)",
        "subject": "Venda marketplace concluída — {nome_cliente}",
        "body_html": (
            "<p>Cadastro concluído.</p>"
            "<p>Cliente: {nome_cliente}<br>Crédito: {valor_credito}</p>"
        ),
        "sort_order": 1016,
    },
}


def ensure_marketplace_email_templates(db: Session, organization_id: str) -> dict[str, int]:
    """Cria registros CMS faltantes (slug email-marketplace-*). Não sobrescreve textos já editados."""
    created = 0
    skipped = 0
    for slug, meta in MARKETPLACE_EMAIL_TEMPLATE_SEEDS.items():
        existing = db.scalar(
            select(CmsText).where(
                CmsText.organization_id == organization_id,
                CmsText.slug == slug,
                CmsText.kind == "EMAIL",
            )
        )
        if existing:
            skipped += 1
            continue
        legacy_id = _SLUG_TO_LEGACY_ID.get(slug)
        db.add(
            CmsText(
                organization_id=organization_id,
                legacy_id=legacy_id,
                active=True,
                kind="EMAIL",
                name_main=str(meta["name_main"]),
                subject=str(meta["subject"]),
                slug=slug,
                body_html=str(meta["body_html"]),
                sort_order=int(meta["sort_order"]),
            )
        )
        created += 1
    db.flush()
    return {"created": created, "skipped": skipped, "total_slugs": len(MARKETPLACE_EMAIL_TEMPLATE_SEEDS)}
