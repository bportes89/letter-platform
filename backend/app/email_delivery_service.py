"""Entrega real de e-mails transacionais (Resend ou SMTP)."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from uuid import uuid4

import httpx

from app.core.config import settings

logger = logging.getLogger("letter.email")


def email_delivery_configured() -> bool:
    if (settings.resend_api_key or "").strip():
        return True
    return bool((settings.smtp_host or "").strip() and (settings.smtp_user or "").strip())


def _from_address() -> tuple[str, str]:
    email = (settings.smtp_from_email or settings.company_email or "no-reply@letter.app.br").strip()
    name = (settings.smtp_from_name or settings.company_trade_name or "LETTER").strip()
    return name, email


def _format_from() -> str:
    name, email = _from_address()
    return f"{name} <{email}>"


def _send_resend(destination: str, subject: str, body_text: str) -> tuple[bool, str, str | None]:
    api_key = (settings.resend_api_key or "").strip()
    if not api_key:
        return False, "MOCK", None
    name, email = _from_address()
    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": f"{name} <{email}>",
                "to": [destination],
                "subject": subject,
                "text": body_text,
            },
            timeout=settings.integration_http_timeout_seconds,
        )
        if response.status_code >= 400:
            logger.warning("resend_send_failed", extra={"status": response.status_code, "body": response.text[:300]})
            return False, "RESEND", None
        payload = response.json()
        return True, "RESEND", str(payload.get("id") or uuid4().hex)
    except Exception as exc:
        logger.warning("resend_send_exception", extra={"error": str(exc)})
        return False, "RESEND", None


def _send_smtp(destination: str, subject: str, body_text: str) -> tuple[bool, str, str | None]:
    host = (settings.smtp_host or "").strip()
    user = (settings.smtp_user or "").strip()
    password = settings.smtp_password or ""
    if not host or not user:
        return False, "MOCK", None
    name, from_email = _from_address()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{name} <{from_email}>"
    message["To"] = destination
    message.set_content(body_text)
    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(host, settings.smtp_port, timeout=settings.integration_http_timeout_seconds) as client:
                if password:
                    client.login(user, password)
                client.send_message(message)
        else:
            with smtplib.SMTP(host, settings.smtp_port, timeout=settings.integration_http_timeout_seconds) as client:
                if settings.smtp_use_tls:
                    client.starttls()
                if password:
                    client.login(user, password)
                client.send_message(message)
        return True, "SMTP", f"smtp_{uuid4().hex[:16]}"
    except Exception as exc:
        logger.warning("smtp_send_exception", extra={"error": str(exc), "host": host})
        return False, "SMTP", None


def send_transactional_email(destination: str, subject: str, body_text: str) -> tuple[bool, str, str | None]:
    target = (destination or "").strip().lower()
    if not target or "@" not in target:
        return False, "MOCK", None
    if (settings.resend_api_key or "").strip():
        return _send_resend(target, subject, body_text)
    if email_delivery_configured():
        return _send_smtp(target, subject, body_text)
    return False, "MOCK", None
