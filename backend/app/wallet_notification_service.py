"""E-mails transacionais LETTER BANK — abertura de conta e aprovação KYC (white label)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import CommunicationTemplate, EscrowAccount, User
from app.tax_communication_service import mock_deliver, queue_delivery

WALLET_OPENED_KEY = "WALLET_ACCOUNT_OPENED"
WALLET_KYC_APPROVED_KEY = "WALLET_KYC_APPROVED"


def wallet_onboarding_url() -> str:
    base = (settings.public_app_url or "").rstrip("/")
    if not base:
        return "/modules/my-wallet?onboarding=1"
    return f"{base}/modules/my-wallet?onboarding=1"


def _ensure_email_template(
    db: Session,
    user: User,
    *,
    key: str,
    subject: str,
    body: str,
) -> CommunicationTemplate:
    item = db.scalar(
        select(CommunicationTemplate).where(
            CommunicationTemplate.organization_id == user.organization_id,
            CommunicationTemplate.key == key,
            CommunicationTemplate.channel == "EMAIL",
            CommunicationTemplate.active.is_(True),
        )
    )
    if item:
        return item
    current = db.scalar(
        select(CommunicationTemplate.version).where(
            CommunicationTemplate.organization_id == user.organization_id,
            CommunicationTemplate.key == key,
            CommunicationTemplate.channel == "EMAIL",
        )
    ) or 0
    item = CommunicationTemplate(
        organization_id=user.organization_id,
        key=key,
        channel="EMAIL",
        version=current + 1,
        subject=subject,
        body=body,
        purpose="TRANSACTIONAL",
        active=True,
    )
    db.add(item)
    db.flush()
    return item


def _queue_and_deliver(
    db: Session,
    actor: User,
    *,
    template: CommunicationTemplate,
    subject_type: str,
    subject_id: str,
    destination: str,
    idempotency_key: str,
    variables: dict[str, Any],
) -> dict | None:
    if not destination or "@" not in destination:
        return None
    try:
        delivery, created = queue_delivery(
            db,
            actor,
            template,
            subject_type=subject_type,
            subject_id=subject_id,
            destination=destination,
            idempotency_key=idempotency_key,
            variables=variables,
        )
        if created:
            mock_deliver(delivery)
        return {
            "key": template.key,
            "destination": delivery.destination_masked,
            "status": delivery.status,
            "created": created,
        }
    except Exception:
        return {"key": template.key, "destination": destination, "status": "FAILED", "created": False}


def _account_holder(account: EscrowAccount, user: User | None) -> tuple[str, str]:
    name = (account.subaccount_name or (user.name if user else "") or settings.company_trade_name).strip()
    email = (user.email if user else "").strip().lower()
    return name, email


def dispatch_wallet_opened_notification(
    db: Session,
    actor: User,
    account: EscrowAccount,
    *,
    holder: User | None = None,
) -> dict | None:
    """E-mail LETTER quando a subconta é criada — substitui o boas-vindas Asaas na comunicação."""
    if not settings.wallet_customer_email_enabled:
        return None
    client = holder or (db.get(User, account.user_id) if account.user_id else None)
    name, email = _account_holder(account, client)
    if not email:
        return None
    template = _ensure_email_template(
        db,
        actor,
        key=WALLET_OPENED_KEY,
        subject="Sua conta digital LETTER foi aberta",
        body=(
            "Olá, {{name}}!\n\n"
            "Sua conta digital LETTER (BANK) foi criada com sucesso.\n\n"
            "Para liberar saques, Pix e demais funcionalidades, conclua a verificação de identidade "
            "pelo nosso escritório virtual — não é necessário acessar o site do Asaas.\n\n"
            "Acesse: {{wallet_url}}\n\n"
            "Se você não solicitou esta conta, ignore este e-mail ou contate o suporte LETTER.\n\n"
            "Equipe {{brand_name}}"
        ),
    )
    return _queue_and_deliver(
        db,
        actor,
        template=template,
        subject_type="WALLET_ACCOUNT",
        subject_id=account.id,
        destination=email,
        idempotency_key=f"wallet-opened:{account.id}",
        variables={
            "name": name,
            "wallet_url": wallet_onboarding_url(),
            "brand_name": settings.company_trade_name,
        },
    )


def dispatch_wallet_kyc_approved_notification(
    db: Session,
    actor: User,
    account: EscrowAccount,
    *,
    holder: User | None = None,
) -> dict | None:
    """E-mail LETTER quando a documentação Asaas é aprovada."""
    if not settings.wallet_customer_email_enabled:
        return None
    client = holder or (db.get(User, account.user_id) if account.user_id else None)
    name, email = _account_holder(account, client)
    if not email:
        return None
    template = _ensure_email_template(
        db,
        actor,
        key=WALLET_KYC_APPROVED_KEY,
        subject="Conta LETTER aprovada — carteira liberada",
        body=(
            "Olá, {{name}}!\n\n"
            "Sua verificação de identidade foi concluída e sua conta digital LETTER está ativa.\n\n"
            "Acesse o BANK no escritório virtual para consultar saldo, Pix, boletos e extrato:\n"
            "{{wallet_url}}\n\n"
            "Equipe {{brand_name}}"
        ),
    )
    return _queue_and_deliver(
        db,
        actor,
        template=template,
        subject_type="WALLET_ACCOUNT",
        subject_id=account.id,
        destination=email,
        idempotency_key=f"wallet-kyc-approved:{account.id}",
        variables={
            "name": name,
            "wallet_url": wallet_onboarding_url(),
            "brand_name": settings.company_trade_name,
        },
    )
