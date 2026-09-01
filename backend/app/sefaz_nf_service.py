"""Robô fiscal: leitura NF + consulta SEFAZ + liberação de comissão."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CommissionEntry, FiscalEvidence, User
from app.sefaz_client import SefazNfeResult, consult_nfe, infosimples_configured
from app.services import money
from app.tax_communication_service import issue_tax_document


ACCESS_KEY_PATTERN = re.compile(r"\b(\d{44})\b")


def extract_access_key(document_content: str, explicit_key: str | None = None) -> str:
    if explicit_key:
        key = re.sub(r"\D", "", explicit_key)
        if len(key) == 44:
            return key
        raise HTTPException(status_code=422, detail="Chave de acesso informada é inválida (44 dígitos).")

    match = ACCESS_KEY_PATTERN.search(document_content or "")
    if match:
        return match.group(1)

    id_match = re.search(r'Id="NFe(\d{44})"', document_content or "")
    if id_match:
        return id_match.group(1)

    ch_match = re.search(r"<chNFe>(\d{44})</chNFe>", document_content or "", re.IGNORECASE)
    if ch_match:
        return ch_match.group(1)

    raise HTTPException(
        status_code=422,
        detail="Não foi possível extrair a chave NF-e (44 dígitos). Envie o XML ou informe access_key.",
    )


def sefaz_robot_status() -> dict:
    from app.sefaz_client import sefaz_production_required

    configured = infosimples_configured()
    production = sefaz_production_required()
    if production and not configured:
        return {
            "enabled": False,
            "provider": "INFOSIMPLES_SEFAZ",
            "mode": "PRODUCTION",
            "message": "Configure LETTER_INFOSIMPLES_API_TOKEN no Render para ativar consultas reais na SEFAZ.",
        }
    return {
        "enabled": True,
        "provider": "INFOSIMPLES_SEFAZ" if configured else "SEFAZ_SANDBOX",
        "mode": "PRODUCTION" if configured else "SANDBOX",
        "message": (
            "Robô SEFAZ ativo em produção (InfoSimples — consulta SEFAZ/NFE unificada)."
            if configured
            else "Robô SEFAZ em sandbox local — apenas LETTER_ENV=development."
        ),
    }


def _pending_commissions(db: Session, user: User, reference_month: str) -> list[CommissionEntry]:
    entries = list(
        db.scalars(
            select(CommissionEntry).where(
                CommissionEntry.organization_id == user.organization_id,
                CommissionEntry.beneficiary_id == user.id,
                CommissionEntry.status == "PENDING_FISCAL",
            )
        )
    )
    return [e for e in entries if e.created_at.strftime("%Y-%m") == reference_month]


def _validate_amount(sefaz: SefazNfeResult, pending_total: Decimal, declared: Decimal | None) -> None:
    expected = money(pending_total)
    check = declared if declared is not None else sefaz.gross_amount
    if check is None:
        return
    check = money(check)
    if check + Decimal("0.01") < expected:
        raise HTTPException(
            status_code=422,
            detail=f"Valor da NF (R$ {check}) inferior às comissões retidas (R$ {expected}).",
        )


def validate_nf_with_sefaz(
    db: Session,
    user: User,
    *,
    reference_month: str,
    document_content: str,
    access_key: str | None = None,
    gross_amount: Decimal | None = None,
) -> tuple[SefazNfeResult, list[CommissionEntry]]:
    key = extract_access_key(document_content, access_key)
    pending = _pending_commissions(db, user, reference_month)
    if not pending:
        raise HTTPException(status_code=404, detail="Nenhuma comissão em hold fiscal para esta competência.")

    sefaz = consult_nfe(key)
    if sefaz.status != "AUTHORIZED":
        raise HTTPException(
            status_code=422,
            detail=f"SEFAZ não autorizou a NF-e (status: {sefaz.status}). Comissão permanece bloqueada.",
        )

    pending_total = money(sum(Decimal(str(e.amount)) for e in pending))
    _validate_amount(sefaz, pending_total, gross_amount)

    return sefaz, pending


def release_commissions_after_sefaz(
    db: Session,
    user: User,
    *,
    reference_month: str,
    document_content: str,
    access_key: str | None = None,
    gross_amount: Decimal | None = None,
) -> FiscalEvidence:
    sefaz, pending = validate_nf_with_sefaz(
        db,
        user,
        reference_month=reference_month,
        document_content=document_content,
        access_key=access_key,
        gross_amount=gross_amount,
    )

    digest = hashlib.sha256(document_content.encode()).hexdigest()
    existing = db.scalar(select(FiscalEvidence).where(FiscalEvidence.document_hash == digest))
    if existing:
        raise HTTPException(status_code=409, detail="Documento fiscal já utilizado para liberação.")

    key_used = sefaz.access_key
    if db.scalar(select(FiscalEvidence).where(FiscalEvidence.access_key == key_used)):
        raise HTTPException(status_code=409, detail="Chave NF-e já utilizada para liberação.")

    pending_total = money(sum(Decimal(str(e.amount)) for e in pending))
    declared = gross_amount if gross_amount is not None else sefaz.gross_amount or pending_total

    issue_tax_document(
        db,
        user,
        user,
        reference_month,
        declared,
        Decimal("0"),
        document_content,
    )

    evidence = FiscalEvidence(
        organization_id=user.organization_id,
        user_id=user.id,
        reference_month=reference_month,
        provider=sefaz.provider,
        status="VALID",
        document_hash=digest,
        access_key=key_used,
        sefaz_status=sefaz.status,
        gross_amount=float(declared),
        detail_json=json.dumps(
            {
                "mode": sefaz.mode,
                "issuer_document": sefaz.issuer_document,
                "issuer_name": sefaz.issuer_name,
                "issue_date": sefaz.issue_date,
                "commissions_released": len(pending),
                "pending_total": str(pending_total),
            },
            ensure_ascii=False,
        ),
        validated_at=datetime.now(UTC),
    )
    db.add(evidence)
    db.flush()

    from app.commission_wallet_service import auto_credit_commissions_to_partner_wallet

    wallet_credit = auto_credit_commissions_to_partner_wallet(
        db,
        user,
        pending,
        reference=reference_month,
        access_key=key_used,
    )
    evidence.detail_json = json.dumps(
        {
            **json.loads(evidence.detail_json),
            "wallet_credit": wallet_credit,
        },
        ensure_ascii=False,
    )

    return evidence


def available_commission_balance(db: Session, user: User) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(CommissionEntry.amount), 0)).where(
            CommissionEntry.beneficiary_id == user.id,
            CommissionEntry.status == "AVAILABLE",
        )
    )
    return money(Decimal(str(total or 0)))
