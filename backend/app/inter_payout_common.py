"""Banco Inter — API de pagamento PIX (saída) para parceiros e fornecedores."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.inter_common import DEFAULT_BASE_URL, inter_base_url

INTER_PAYOUT_SCOPE = (
    "pagamento-pix.write pagamento-pix.read extrato.read saldo.read"
)


def inter_payout_base_url() -> str:
    return inter_base_url()


def inter_payout_configured() -> bool:
    conta = (settings.inter_payout_conta_corrente or settings.inter_conta_corrente or "").strip()
    return bool(
        (settings.inter_payout_client_id or "").strip()
        and (settings.inter_payout_client_secret or "").strip()
        and conta
        and (settings.inter_payout_cert_path or "").strip()
        and (settings.inter_payout_key_path or "").strip()
        and Path(settings.inter_payout_cert_path).is_file()
        and Path(settings.inter_payout_key_path).is_file()
    )


def inter_payout_conta() -> str:
    return (settings.inter_payout_conta_corrente or settings.inter_conta_corrente or "").strip()


def inter_payout_auto_enabled() -> bool:
    return bool(settings.inter_payout_auto_on_withdraw) and inter_payout_configured()


def inter_payout_webhook_token() -> str:
    return (settings.inter_payout_webhook_access_token or settings.inter_webhook_access_token or "").strip()
