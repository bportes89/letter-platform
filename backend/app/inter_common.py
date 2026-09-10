"""Config compartilhada da integração Banco Inter (cobrança boleto/PIX)."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings

INTER_SCOPE = "boleto-cobranca.read boleto-cobranca.write pagamento-boleto.read"
DEFAULT_BASE_URL = "https://cdpj.partners.bancointer.com.br"


def inter_base_url() -> str:
    return (settings.inter_base_url or DEFAULT_BASE_URL).rstrip("/")


def inter_configured() -> bool:
    """Credenciais + mTLS presentes → cliente real; senão modo MOCK."""
    return bool(
        (settings.inter_client_id or "").strip()
        and (settings.inter_client_secret or "").strip()
        and (settings.inter_conta_corrente or "").strip()
        and (settings.inter_cert_path or "").strip()
        and (settings.inter_key_path or "").strip()
        and Path(settings.inter_cert_path).is_file()
        and Path(settings.inter_key_path).is_file()
    )


def inter_webhook_token() -> str:
    return (settings.inter_webhook_access_token or "").strip()


def inter_vencimento_dias() -> int:
    days = int(settings.inter_boleto_vencimento_dias or 5)
    return max(1, min(days, 60))
