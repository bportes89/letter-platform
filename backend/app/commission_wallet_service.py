"""Crédito automático de comissão na Minha Carteira do parceiro após validação SEFAZ."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.financial_service import ensure_chart
from app.models import CommissionEntry, EscrowAccount, EscrowEvent, User
from app.services import money, post_double_entry
from app.subaccount_auto_service import (
    ensure_kyc_case_for_user,
    find_user_plain_subaccount,
    provision_plain_subaccount_for_user,
    user_eligible_for_auto_subaccount,
)


def ensure_partner_wallet_account(db: Session, partner: User, actor: User | None = None) -> EscrowAccount:
    actor = actor or partner
    existing = find_user_plain_subaccount(db, partner)
    if existing:
        return existing
    if not user_eligible_for_auto_subaccount(partner):
        raise HTTPException(status_code=422, detail="Perfil não elegível para carteira de parceiro.")
    if not (partner.document or "").strip():
        raise HTTPException(status_code=422, detail="Parceiro sem CPF/CNPJ — cadastre documento para abrir carteira.")

    case = ensure_kyc_case_for_user(db, partner)
    if case.status != "APPROVED":
        case.status = "APPROVED"
        case.risk_level = case.risk_level or "LOW"
        case.reviewed_at = datetime.now(UTC)

    account = provision_plain_subaccount_for_user(db, partner, actor)
    if not account:
        raise HTTPException(status_code=422, detail="Não foi possível provisionar carteira do parceiro.")
    return account


def auto_credit_commissions_to_partner_wallet(
    db: Session,
    partner: User,
    entries: list[CommissionEntry],
    *,
    reference: str,
    access_key: str | None = None,
    actor: User | None = None,
) -> dict:
    """Credita comissões validadas na Minha Carteira — idempotente por entry status."""
    releasable = [entry for entry in entries if entry.status == "PENDING_FISCAL"]
    if not releasable:
        return {"credited": False, "amount": "0", "message": "Nenhuma comissão pendente para crédito."}

    total = money(sum(Decimal(str(entry.amount)) for entry in releasable))
    if total <= 0:
        return {"credited": False, "amount": "0", "message": "Valor de comissão inválido."}

    if not settings.auto_credit_commission_to_partner_wallet:
        now = datetime.now(UTC)
        for entry in releasable:
            entry.status = "AVAILABLE"
            entry.released_at = now
        return {
            "credited": False,
            "amount": str(total),
            "message": "Liberação fiscal concluída — crédito automático desativado (saldo AVAILABLE).",
        }

    actor = actor or partner
    account = ensure_partner_wallet_account(db, partner, actor)
    ensure_chart(db, partner)

    account.available_balance = money(Decimal(str(account.available_balance or 0)) + total)

    event_id = f"commission_{reference}_{access_key or uuid4().hex[:12]}"
    db.add(
        EscrowEvent(
            organization_id=partner.organization_id,
            escrow_account_id=account.id,
            provider_event_id=event_id,
            event_type="COMMISSION_CREDITED",
            amount=float(total),
            payload_json=json.dumps(
                {
                    "reference": reference,
                    "access_key": access_key,
                    "entries": len(releasable),
                    "source": "SEFAZ_AUTO_CREDIT",
                },
                ensure_ascii=False,
            ),
        )
    )

    post_double_entry(
        db,
        actor,
        reference=f"COMMISSION:{event_id}",
        event_type="COMMISSION_WALLET_CREDIT",
        description=f"Comissão creditada na Minha Carteira — {reference}",
        debit_account="SELLER_PAYABLE",
        credit_account="CLIENT_FUNDS_PAYABLE",
        amount=total,
    )

    now = datetime.now(UTC)
    for entry in releasable:
        entry.status = "CREDITED_TO_WALLET"
        entry.released_at = now

    db.flush()
    return {
        "credited": True,
        "amount": str(total),
        "wallet_account_id": account.id,
        "wallet_balance": str(account.available_balance),
        "message": "Comissão creditada automaticamente na Minha Carteira do parceiro.",
    }
