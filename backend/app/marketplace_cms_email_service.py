"""E-mails transacionais do marketplace — templates no CMS (`cms_texts`, kind=EMAIL)."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CmsText

MARKETPLACE_BOLETO_CLIENT = "MARKETPLACE_BOLETO_CLIENT"
MARKETPLACE_PAYMENT_CLIENT = "MARKETPLACE_PAYMENT_CLIENT"
MARKETPLACE_PAYMENT_PARTNER = "MARKETPLACE_PAYMENT_PARTNER"

CMS_SLUG_BY_COMM_KEY: dict[str, str] = {
    MARKETPLACE_BOLETO_CLIENT: "email-marketplace-boleto",
    MARKETPLACE_PAYMENT_CLIENT: "email-marketplace-payment-client",
    MARKETPLACE_PAYMENT_PARTNER: "email-marketplace-payment-partner",
}


def _html_to_plain(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
    subject = (row.subject or row.name_main or default_subject).strip()
    raw = (row.body_html or row.sms or row.whatsapp or "").strip()
    body = _html_to_plain(raw) if "<" in raw else raw
    return subject or default_subject, body or default_body
