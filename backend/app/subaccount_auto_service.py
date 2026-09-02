"""Provisionamento automático de subconta normal (sem Escrow) após KYC aprovado."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import re
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.identity_service import create_kyc_case
from app.models import EscrowAccount, KycCase, Role, User
from app.schemas import EscrowSubaccountProfile


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


AUTO_SUBACCOUNT_ROLES = frozenset(Role)


def user_eligible_for_auto_subaccount(user: User) -> bool:
    return user.role in AUTO_SUBACCOUNT_ROLES


def find_user_kyc_case(db: Session, user: User) -> KycCase | None:
    return db.scalar(
        select(KycCase).where(
            KycCase.organization_id == user.organization_id,
            KycCase.subject_type == "USER",
            KycCase.subject_id == user.id,
        ).order_by(KycCase.created_at.desc())
    )


def find_user_plain_subaccount(db: Session, user: User) -> EscrowAccount | None:
    return db.scalar(select(EscrowAccount).where(EscrowAccount.user_id == user.id))


def build_subaccount_profile_for_user(user: User) -> EscrowSubaccountProfile:
    """Monta perfil Asaas — PJ usa CNPJ/razão social quando cadastrados no convite."""
    cnpj = _digits(user.company_cnpj)
    cpf = _digits(user.document)
    phone = (user.phone or "").strip() or None

    if len(cnpj) == 14:
        return EscrowSubaccountProfile(
            name=(user.company_name or user.name).strip(),
            email=user.email,
            cpf_cnpj=cnpj,
            mobile_phone=phone,
            address=(user.company_address or settings.asaas_subaccount_default_address).strip(),
            province=(user.company_city or settings.asaas_subaccount_default_province).strip(),
            company_type=settings.asaas_subaccount_default_company_type,
        )

    return EscrowSubaccountProfile(
        name=user.name,
        email=user.email,
        cpf_cnpj=cpf or None,
        mobile_phone=phone,
    )


def ensure_kyc_case_for_user(db: Session, user: User) -> KycCase:
    existing = find_user_kyc_case(db, user)
    if existing:
        return existing
    case = create_kyc_case(user, "USER", user.id)
    db.add(case)
    db.flush()
    return case


def provision_plain_subaccount_for_user(db: Session, user: User, actor: User) -> EscrowAccount | None:
    """Cria subconta Asaas/mock sem Escrow — idempotente por usuário."""
    if not settings.auto_plain_subaccount_on_kyc:
        return None
    if not user_eligible_for_auto_subaccount(user):
        return None
    existing = find_user_plain_subaccount(db, user)
    if existing:
        return existing
    profile = build_subaccount_profile_for_user(user)
    if len(_digits(profile.cpf_cnpj)) not in {11, 14}:
        return None
    if not (profile.mobile_phone or "").strip():
        return None

    from app.financial_service import create_client_plain_subaccount

    account = create_client_plain_subaccount(db, actor, user, profile=profile)
    if account:
        db.flush()
    return account


def complete_user_kyc_and_provision(db: Session, user: User) -> dict:
    if not user_eligible_for_auto_subaccount(user):
        raise ValueError("Perfil não elegível para subconta automática")
    profile = build_subaccount_profile_for_user(user)
    if len(_digits(profile.cpf_cnpj)) not in {11, 14}:
        raise ValueError("CPF ou CNPJ obrigatório no cadastro para abrir subconta")
    if not (profile.mobile_phone or "").strip():
        raise ValueError("Telefone celular obrigatório para abrir subconta Asaas")

    case = ensure_kyc_case_for_user(db, user)

    if case.status == "APPROVED":
        account = provision_plain_subaccount_for_user(db, user, user)
        return {
            "kyc_status": case.status,
            "kyc_case_id": case.id,
            "subaccount": _subaccount_payload(account) if account else None,
            "message": (
                "KYC já aprovado — subconta normal disponível."
                if account
                else "KYC aprovado — complete CPF/CNPJ para abrir subconta."
            ),
        }

    now = datetime.now(UTC)
    case.status = "SUBMITTED"
    case.result_json = json.dumps({"source": "CLIENT_SELF_SERVICE", "submitted_at": now.isoformat()}, ensure_ascii=False)

    account = None
    if case.provider == "MOCK" or not settings.asaas_api_key:
        case.status = "APPROVED"
        case.risk_level = "LOW"
        case.reviewed_at = now
        case.result_json = json.dumps(
            {"source": "AUTO_MOCK_KYC", "approved_at": now.isoformat()},
            ensure_ascii=False,
        )
        account = provision_plain_subaccount_for_user(db, user, user)

    return {
        "kyc_status": case.status,
        "kyc_case_id": case.id,
        "subaccount": _subaccount_payload(account) if account else None,
        "message": (
            "KYC aprovado e subconta normal criada automaticamente."
            if account
            else "KYC enviado — subconta será criada após aprovação."
        ),
    }


def maybe_provision_after_kyc_decision(db: Session, case: KycCase, actor: User) -> EscrowAccount | None:
    if case.status != "APPROVED" or case.subject_type != "USER":
        return None
    user = db.get(User, case.subject_id)
    if not user:
        return None
    return provision_plain_subaccount_for_user(db, user, actor)


def _subaccount_payload(account: EscrowAccount) -> dict:
    return {
        "id": account.id,
        "provider": account.provider,
        "subaccount_name": account.subaccount_name,
        "escrow_enabled": account.escrow_enabled,
        "status": account.status,
        "external_account_id": account.external_account_id,
    }
