"""Abertura de conta Escrow via Asaas (conta principal ou subconta)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.asaas_client import AsaasClient
from app.asaas_common import asaas_configured, mask_wallet, verify_wallet_id
from app.asaas_subaccount_service import create_asaas_subaccount, create_mock_subaccount
from app.core.config import settings
from app.financial_service import ensure_chart
from app.models import EscrowAccount, User
from app.schemas import EscrowSubaccountProfile


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
            "subaccounts_enabled": False,
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
        "subaccounts_enabled": True,
        "message": "Conexão Asaas validada. Subcontas com ou sem Escrow disponíveis.",
    }


def create_asaas_escrow(
    db: Session,
    user: User,
    operation_id: str | None,
    *,
    create_subaccount: bool = True,
    enable_escrow: bool = True,
    profile: EscrowSubaccountProfile | None = None,
) -> EscrowAccount:
    if create_subaccount:
        if asaas_configured():
            return create_asaas_subaccount(db, user, operation_id, profile, enable_escrow=enable_escrow)
        return create_mock_subaccount(db, user, operation_id, profile, enable_escrow=enable_escrow)

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
        escrow_enabled=True,
        status="ACTIVE",
    )
    db.add(account)
    ensure_chart(db, user)
    return account
