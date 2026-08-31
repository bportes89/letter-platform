"""Utilitários compartilhados da integração Asaas."""

from __future__ import annotations

from fastapi import HTTPException

from app.asaas_client import AsaasClient
from app.core.config import settings


def asaas_configured() -> bool:
    return bool(settings.asaas_api_key and settings.asaas_api_key.strip() and settings.asaas_wallet_id and settings.asaas_wallet_id.strip())


def mask_wallet(wallet_id: str) -> str:
    clean = wallet_id.strip()
    if len(clean) <= 8:
        return "***"
    return f"{clean[:4]}…{clean[-4:]}"


def verify_wallet_id(client: AsaasClient) -> None:
    expected = (settings.asaas_wallet_id or "").strip()
    payload = client.list_wallets()
    wallets = payload.get("data") if isinstance(payload.get("data"), list) else []
    ids = {str(item.get("id", "")).strip() for item in wallets if isinstance(item, dict)}
    if expected and ids and expected not in ids:
        raise HTTPException(
            status_code=422,
            detail="Wallet ID informado não corresponde à conta autenticada no Asaas.",
        )
