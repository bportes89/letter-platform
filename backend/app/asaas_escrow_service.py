"""Abertura de conta Escrow via Asaas (conta principal + configuração Escrow)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.asaas_client import AsaasClient
from app.core.config import settings
from app.financial_service import ensure_chart
from app.models import EscrowAccount, User


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


def asaas_status() -> dict:
    if not asaas_configured():
        return {
            "configured": False,
            "connected": False,
            "provider": "ASAAS",
            "wallet_id": None,
            "wallet_id_masked": None,
            "environment": "sandbox" if "sandbox" in settings.asaas_base_url else "production",
            "balance": None,
            "message": "Configure LETTER_ASAAS_API_KEY e LETTER_ASAAS_WALLET_ID.",
        }
    with AsaasClient() as client:
        balance_payload = client.get_balance()
        verify_wallet_id(client)
    balance = balance_payload.get("balance")
    return {
        "configured": True,
        "connected": True,
        "provider": "ASAAS",
        "wallet_id": settings.asaas_wallet_id,
        "wallet_id_masked": mask_wallet(settings.asaas_wallet_id or ""),
        "environment": "sandbox" if "sandbox" in settings.asaas_base_url else "production",
        "balance": str(balance) if balance is not None else None,
        "message": "Conexão Asaas validada.",
    }


def create_asaas_escrow(db: Session, user: User, operation_id: str | None) -> EscrowAccount:
    if operation_id and db.scalar(select(EscrowAccount).where(EscrowAccount.operation_id == operation_id)):
        raise HTTPException(status_code=409, detail="Operação já possui conta escrow")

    wallet_id = (settings.asaas_wallet_id or "").strip()
    with AsaasClient() as client:
        verify_wallet_id(client)
        client.get_balance()
        client.configure_default_escrow(
            enabled=settings.asaas_escrow_enabled,
            days_to_expire=settings.asaas_escrow_days_to_expire,
            fee_payer_subaccount=settings.asaas_escrow_fee_payer_subaccount,
        )

    account = EscrowAccount(
        organization_id=user.organization_id,
        operation_id=operation_id,
        provider="ASAAS",
        external_account_id=wallet_id,
        status="ACTIVE",
    )
    db.add(account)
    ensure_chart(db, user)
    return account
