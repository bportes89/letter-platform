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


def disable_asaas_default_escrow() -> dict:
    """Desliga a config padrão do Asaas que aplica Escrow a todas as subcontas."""
    if not asaas_configured():
        raise HTTPException(status_code=503, detail="Integração Asaas não configurada.")
    with AsaasClient() as client:
        verify_wallet_id(client)
        return client.configure_default_escrow(
            enabled=False,
            days_to_expire=settings.asaas_escrow_days_to_expire,
            fee_payer_subaccount=settings.asaas_escrow_fee_payer_subaccount,
        )


def set_account_escrow(db: Session, account: EscrowAccount, *, enabled: bool) -> EscrowAccount:
    """Liga/desliga Escrow em uma subconta (Asaas + flag local)."""
    if account.asaas_account_id and asaas_configured() and account.provider.startswith("ASAAS"):
        with AsaasClient() as client:
            client.configure_subaccount_escrow(
                account.asaas_account_id,
                enabled=enabled,
                days_to_expire=settings.asaas_escrow_days_to_expire,
                fee_payer_subaccount=settings.asaas_escrow_fee_payer_subaccount,
            )
    account.escrow_enabled = enabled
    if enabled:
        from app.wallet_billing_service import ensure_escrow_billing_cycle

        ensure_escrow_billing_cycle(db, account)
    db.add(account)
    return account


def repair_client_plain_subaccounts(db: Session, organization_id: str) -> dict:
    """
    Contas de carteira do cliente (user_id preenchido) devem ser plain — sem Escrow.
    Força disabled no Asaas para cortar a taxa de R$ 9,90/mês por subconta.
    """
    accounts = list(
        db.scalars(
            select(EscrowAccount).where(
                EscrowAccount.organization_id == organization_id,
                EscrowAccount.user_id.is_not(None),
            )
        )
    )
    repaired: list[str] = []
    errors: list[dict] = []
    for account in accounts:
        try:
            set_account_escrow(db, account, enabled=False)
            repaired.append(account.id)
        except Exception as exc:  # noqa: BLE001 — reparo parcial; segue nas demais
            errors.append({"account_id": account.id, "error": str(exc)})
    return {
        "repaired_count": len(repaired),
        "repaired_ids": repaired,
        "error_count": len(errors),
        "errors": errors,
        "message": (
            f"{len(repaired)} subconta(s) de cliente com Escrow desligado. "
            "Taxa Asaas (~R$ 9,90/mês) deixa de ser cobrada nas próximas ciclos se o recurso ficou disabled."
        ),
    }


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
        # NÃO chamar configure_default_escrow(enabled=True) aqui.
        # Esse endpoint do Asaas liga Escrow em TODAS as subcontas (atuais e futuras)
        # e cobra ~R$ 9,90/mês por subconta na conta matriz quando isFeePayer=false.

    account = EscrowAccount(
        organization_id=user.organization_id,
        operation_id=operation_id,
        provider="ASAAS",
        external_account_id=wallet_id,
        escrow_enabled=True,
        status="ACTIVE",
    )
    db.add(account)
    db.flush()
    ensure_chart(db, user)
    from app.wallet_billing_service import ensure_escrow_billing_cycle

    ensure_escrow_billing_cycle(db, account)
    return account
