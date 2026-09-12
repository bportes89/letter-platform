"""Configuração de webhooks Asaas para subcontas LETTER."""

from __future__ import annotations

from app.core.config import settings

_SUBACCOUNT_WEBHOOK_EVENTS = (
    "ACCOUNT_STATUS_UPDATED",
    "ACCOUNT_STATUS_GENERAL_APPROVAL_APPROVED",
    "ACCOUNT_STATUS_GENERAL_APPROVAL_REJECTED",
    "ACCOUNT_DOCUMENTATION_APPROVED",
    "ACCOUNT_DOCUMENTATION_REJECTED",
    "ACCOUNT_DOCUMENTATION_AWAITING_APPROVAL",
    "PAYMENT_CREATED",
    "PAYMENT_CONFIRMED",
    "PAYMENT_RECEIVED",
    "TRANSFER_CREATED",
    "TRANSFER_DONE",
    "TRANSFER_FAILED",
)


def asaas_webhook_callback_url() -> str | None:
    base = (settings.api_public_url or "").rstrip("/")
    if not base:
        return None
    return f"{base}/webhooks/asaas"


def build_subaccount_webhooks() -> list[dict]:
    """Webhooks criados junto com a subconta — evita configurar manualmente no painel Asaas."""
    if not settings.asaas_subaccount_webhooks_enabled:
        return []
    url = asaas_webhook_callback_url()
    if not url:
        return []
    token = (settings.asaas_webhook_access_token or "").strip()
    if len(token) < 16:
        return []
    return [
        {
            "name": "LETTER Platform — conta e pagamentos",
            "url": url,
            "email": settings.company_email,
            "sendType": "SEQUENTIALLY",
            "interrupted": False,
            "enabled": True,
            "apiVersion": 3,
            "authToken": token,
            "events": list(_SUBACCOUNT_WEBHOOK_EVENTS),
        }
    ]
