"""Provisionamento automático de subconta normal (sem Escrow) após KYC aprovado."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import re
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.asaas_common import asaas_configured
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
    if len(cnpj) != 14 and len(cpf) == 14:
        cnpj, cpf = cpf, ""
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

    try:
        account = create_client_plain_subaccount(db, actor, user, profile=profile)
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc
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

    if asaas_configured():
        from app.account_uniqueness import assert_valid_cpf_or_cnpj

        try:
            assert_valid_cpf_or_cnpj(profile.cpf_cnpj)
        except HTTPException as exc:
            raise ValueError(str(exc.detail)) from exc

    case = ensure_kyc_case_for_user(db, user)

    if case.status == "APPROVED":
        account = provision_plain_subaccount_for_user(db, user, user)
        return {
            "kyc_status": case.status,
            "kyc_case_id": case.id,
            "subaccount": _subaccount_payload(account) if account else None,
            "message": (
                "Verificação já concluída — conta LETTER disponível."
                if account
                else "Verificação concluída — complete CPF/CNPJ para abrir a conta."
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
            "KYC aprovado e conta LETTER criada automaticamente."
            if account
            else "Verificação enviada — a conta será aberta após validação dos dados."
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


def list_pending_subaccount_provisions(db: Session, organization_id: str) -> list[dict]:
    """Usuários com KYC aprovado e sem subconta — fila para abertura manual pelo admin."""
    from app.asaas_subaccount_service import subaccount_profile_preview

    rows: list[dict] = []
    users = list(
        db.scalars(
            select(User)
            .where(User.organization_id == organization_id, User.active.is_(True))
            .order_by(User.created_at.asc())
        )
    )
    for subject in users:
        if find_user_plain_subaccount(db, subject):
            continue
        kyc = find_user_kyc_case(db, subject)
        if not kyc or kyc.status != "APPROVED":
            continue
        profile = build_subaccount_profile_for_user(subject)
        blockers: list[str] = []
        if len(_digits(profile.cpf_cnpj)) not in {11, 14}:
            blockers.append("CPF/CNPJ ausente ou inválido")
        if not (profile.mobile_phone or "").strip():
            blockers.append("Telefone celular ausente")
        preview = subaccount_profile_preview(db, subject, None, profile)
        rows.append(
            {
                "user_id": subject.id,
                "name": subject.name,
                "email": subject.email,
                "role": subject.role,
                "kyc_status": kyc.status,
                "ready": not blockers,
                "blockers": blockers,
                "preview": preview,
            }
        )
    return rows


def next_ready_subaccount_user(db: Session, organization_id: str, *, user_id: str | None = None) -> User | None:
    pending = list_pending_subaccount_provisions(db, organization_id)
    if user_id:
        match = next((row for row in pending if row["user_id"] == user_id), None)
        if not match:
            return None
        if not match["ready"]:
            raise HTTPException(
                status_code=422,
                detail=f"Usuário não está pronto para subconta: {', '.join(match['blockers'])}.",
            )
        return db.get(User, user_id)
    ready = next((row for row in pending if row["ready"]), None)
    if not ready:
        return None
    return db.get(User, ready["user_id"])


def provision_manual_subaccount(
    db: Session,
    actor: User,
    *,
    user_id: str | None = None,
    enable_escrow: bool = False,
) -> EscrowAccount:
    target = next_ready_subaccount_user(db, actor.organization_id, user_id=user_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail="Nenhum usuário com KYC aprovado aguardando abertura de subconta.",
        )
    from app.financial_service import create_client_plain_subaccount

    profile = build_subaccount_profile_for_user(target)
    return create_client_plain_subaccount(db, actor, target, profile=profile, enable_escrow=enable_escrow)


def manual_subaccount_preview(
    db: Session,
    actor: User,
    *,
    user_id: str | None = None,
) -> dict | None:
    from app.asaas_subaccount_service import subaccount_profile_preview

    target = next_ready_subaccount_user(db, actor.organization_id, user_id=user_id)
    if not target:
        return None
    profile = build_subaccount_profile_for_user(target)
    preview = subaccount_profile_preview(db, actor, None, profile)
    preview["user_id"] = target.id
    preview["user_name"] = target.name
    preview["user_email"] = target.email
    return preview
