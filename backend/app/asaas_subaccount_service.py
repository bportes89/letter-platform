"""Criação de subcontas Asaas — com ou sem Escrow."""

from __future__ import annotations

import re
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.asaas_client import AsaasClient
from app.asaas_common import asaas_configured, verify_wallet_id
from app.core.config import settings
from app.financial_service import ensure_chart
from app.models import EscrowAccount, Operation, Organization, User
from app.schemas import EscrowSubaccountProfile


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _is_cnpj(document: str) -> bool:
    return len(document) == 14


def build_subaccount_profile(
    db: Session,
    user: User,
    operation_id: str | None,
    overrides: EscrowSubaccountProfile | None,
) -> dict:
    org = db.get(Organization, user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    operation = db.get(Operation, operation_id) if operation_id else None
    profile = overrides or EscrowSubaccountProfile()

    name = profile.name
    if not name:
        if operation:
            name = f"LETTER {operation.product} {operation.id[:8].upper()}"
        else:
            name = f"LETTER {org.name}"

    email = profile.email or user.email
    document = _digits(profile.cpf_cnpj or org.document or user.document)
    if len(document) not in {11, 14}:
        raise HTTPException(
            status_code=422,
            detail="CPF/CNPJ obrigatório para abrir subconta Asaas. Informe no perfil ou cadastre na organização.",
        )

    income = float(profile.income_value) if profile.income_value is not None else settings.asaas_subaccount_default_income_value
    if operation and profile.income_value is None:
        income = max(income, float(operation.amount) * 0.1)

    payload: dict = {
        "name": name[:180],
        "email": email,
        "cpfCnpj": document,
        "mobilePhone": profile.mobile_phone or settings.asaas_subaccount_default_mobile_phone,
        "incomeValue": income,
        "address": profile.address or settings.asaas_subaccount_default_address,
        "addressNumber": profile.address_number or settings.asaas_subaccount_default_address_number,
        "province": profile.province or settings.asaas_subaccount_default_province,
        "postalCode": _digits(profile.postal_code or settings.asaas_subaccount_default_postal_code),
    }
    if profile.complement:
        payload["complement"] = profile.complement
    if profile.phone:
        payload["phone"] = profile.phone

    if _is_cnpj(document):
        payload["companyType"] = profile.company_type or settings.asaas_subaccount_default_company_type
    else:
        payload["birthDate"] = profile.birth_date or settings.asaas_subaccount_default_birth_date

    return payload


def subaccount_profile_preview(
    db: Session,
    user: User,
    operation_id: str | None,
    overrides: EscrowSubaccountProfile | None,
) -> dict:
    payload = build_subaccount_profile(db, user, operation_id, overrides)
    document = payload["cpfCnpj"]
    return {
        "name": payload["name"],
        "email": payload["email"],
        "cpf_cnpj": document,
        "mobile_phone": payload["mobilePhone"],
        "income_value": str(payload["incomeValue"]),
        "address": payload["address"],
        "address_number": payload["addressNumber"],
        "province": payload["province"],
        "postal_code": payload["postalCode"],
        "person_type": "PJ" if _is_cnpj(document) else "PF",
        "operation_id": operation_id,
    }


def _ensure_no_duplicate(db: Session, operation_id: str | None, user_id: str | None = None) -> None:
    if operation_id and db.scalar(select(EscrowAccount).where(EscrowAccount.operation_id == operation_id)):
        raise HTTPException(status_code=409, detail="Operação já possui conta vinculada")
    if user_id and db.scalar(select(EscrowAccount).where(EscrowAccount.user_id == user_id)):
        raise HTTPException(status_code=409, detail="Usuário já possui subconta")


def create_mock_subaccount(
    db: Session,
    user: User,
    operation_id: str | None,
    overrides: EscrowSubaccountProfile | None,
    *,
    enable_escrow: bool = True,
    user_id: str | None = None,
) -> EscrowAccount:
    _ensure_no_duplicate(db, operation_id, user_id)

    preview = build_subaccount_profile(db, user, operation_id, overrides)
    wallet_id = f"mock_sub_{uuid4().hex[:16]}"
    account = EscrowAccount(
        organization_id=user.organization_id,
        user_id=user_id,
        operation_id=operation_id,
        provider="MOCK_SUBACCOUNT",
        external_account_id=wallet_id,
        asaas_account_id=f"mock_acct_{uuid4().hex[:12]}",
        subaccount_name=preview["name"],
        escrow_enabled=enable_escrow,
        status="ACTIVE",
    )
    db.add(account)
    ensure_chart(db, user)
    if user_id:
        from app.asaas_wallet_service import ensure_mock_banking

        ensure_mock_banking(account)
    return account


def create_mock_subaccount_escrow(
    db: Session,
    user: User,
    operation_id: str | None,
    overrides: EscrowSubaccountProfile | None,
) -> EscrowAccount:
    return create_mock_subaccount(db, user, operation_id, overrides, enable_escrow=True)


def create_asaas_subaccount(
    db: Session,
    user: User,
    operation_id: str | None,
    overrides: EscrowSubaccountProfile | None,
    *,
    enable_escrow: bool = True,
    user_id: str | None = None,
) -> EscrowAccount:
    if not asaas_configured():
        raise HTTPException(status_code=503, detail="Integração Asaas não configurada.")

    _ensure_no_duplicate(db, operation_id, user_id)
    payload = build_subaccount_profile(db, user, operation_id, overrides)

    with AsaasClient() as client:
        verify_wallet_id(client)
        created = client.create_subaccount(payload)
        asaas_account_id = str(created.get("id", "")).strip()
        wallet_id = str(created.get("walletId", "")).strip()
        if not asaas_account_id or not wallet_id:
            raise HTTPException(status_code=502, detail="Asaas não retornou id/walletId da subconta.")

        sub_api_key = str(created.get("apiKey", "")).strip() or None

        if enable_escrow:
            client.configure_subaccount_escrow(
                asaas_account_id,
                enabled=settings.asaas_escrow_enabled,
                days_to_expire=settings.asaas_escrow_days_to_expire,
                fee_payer_subaccount=settings.asaas_escrow_fee_payer_subaccount,
            )

    account = EscrowAccount(
        organization_id=user.organization_id,
        user_id=user_id,
        operation_id=operation_id,
        provider="ASAAS_SUBACCOUNT",
        external_account_id=wallet_id,
        asaas_account_id=asaas_account_id,
        asaas_subaccount_api_key=sub_api_key,
        subaccount_name=payload["name"],
        bank_code=settings.asaas_bank_code,
        bank_agency=settings.asaas_default_agency,
        asaas_kyc_status="PENDING",
        asaas_commercial_status="PENDING",
        escrow_enabled=enable_escrow,
        status="ACTIVE",
    )
    db.add(account)
    db.flush()
    if sub_api_key:
        try:
            from app.asaas_wallet_service import sync_account_from_asaas

            sync_account_from_asaas(db, account)
        except HTTPException:
            pass
    ensure_chart(db, user)
    return account


def create_asaas_subaccount_escrow(
    db: Session,
    user: User,
    operation_id: str | None,
    overrides: EscrowSubaccountProfile | None,
) -> EscrowAccount:
    return create_asaas_subaccount(db, user, operation_id, overrides, enable_escrow=True)
