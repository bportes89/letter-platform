"""Orquestração PIX saída — saques parceiro/fornecedor via API Inter (doc 170)."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.inter_payout_client import InterPayoutClient
from app.inter_payout_common import inter_payout_auto_enabled, inter_payout_configured
from app.models import PartnerWithdrawal, SupplierWithdrawal, User
from app.partner_legacy_wallet_service import (
    WD_AWAITING_BALANCE,
    WD_FAILED,
    WD_OPEN_STATUSES,
    WD_PAID,
    WD_PENDING,
    WD_PROCESSING,
    _consume_available_entries,
    money,
    withdrawal_view,
)

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_EVP = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


def normalize_pix_key(raw: str) -> str:
    key = (raw or "").strip()
    if len(key) < 5:
        raise HTTPException(status_code=422, detail="Chave PIX inválida.")
    digits = re.sub(r"\D+", "", key)
    if len(digits) in {11, 14}:
        return digits
    if _EMAIL.match(key):
        return key
    if _EVP.match(key):
        return key.lower()
    if key.startswith("+") and len(digits) >= 10:
        return key
    if len(digits) >= 10:
        return f"+{digits}" if not key.startswith("+") else key
    raise HTTPException(status_code=422, detail="Formato de chave PIX não reconhecido.")


def _extract_codigo(body: dict) -> str | None:
    for key in ("codigoSolicitacao", "codigo_solicitacao", "id"):
        if body.get(key):
            return str(body[key])
    return None


def _extract_end_to_end(body: dict) -> str | None:
    for key in ("endToEndId", "end_to_end_id", "e2eId"):
        if body.get(key):
            return str(body[key])
    return None


def _status_liquidado(body: dict) -> bool:
    situacao = str(body.get("status") or body.get("situacao") or "").upper()
    return situacao in {"PAGO", "LIQUIDADO", "REALIZADO", "EFETIVADO", "CONCLUIDO", "CONCLUIDA"}


def submit_partner_withdrawal_pix(db: Session, wd: PartnerWithdrawal, *, descricao: str | None = None) -> PartnerWithdrawal:
    if not inter_payout_configured():
        return wd
    if wd.status not in WD_OPEN_STATUSES:
        return wd
    amount = money(Decimal(str(wd.amount)))
    chave = normalize_pix_key(wd.pix_key)
    client = InterPayoutClient()
    try:
        saldo = client.saldo()
        if saldo < amount:
            wd.status = WD_AWAITING_BALANCE
            wd.payment_error = f"Saldo Inter insuficiente (disponível R$ {saldo})."
            db.flush()
            return wd
    except HTTPException:
        pass
    label = descricao or f"Saque parceiro {wd.id[:8]}"
    try:
        body = client.incluir_pix(
            valor=amount,
            chave_pix=chave,
            descricao=label,
            idempotency_key=wd.id,
        )
    except HTTPException as exc:
        wd.status = WD_FAILED
        wd.payment_error = str(exc.detail)[:500]
        db.flush()
        raise
    wd.inter_codigo_solicitacao = _extract_codigo(body)
    wd.inter_end_to_end_id = _extract_end_to_end(body)
    wd.inter_payment_json = json.dumps(body, ensure_ascii=False)
    wd.payment_error = None
    if _status_liquidado(body):
        partner = db.get(User, wd.user_id)
        if partner:
            _consume_available_entries(db, partner, amount)
        wd.status = WD_PAID
        from datetime import UTC, datetime

        wd.processed_at = datetime.now(UTC)
    else:
        wd.status = WD_PROCESSING
    db.flush()
    return wd


def submit_supplier_withdrawal_pix(db: Session, wd: SupplierWithdrawal, *, descricao: str | None = None) -> SupplierWithdrawal:
    from app.supplier_wallet_service import (
        WD_AWAITING_BALANCE,
        WD_FAILED,
        WD_PAYOUT_OPEN_STATUSES,
        WD_PAID,
        WD_PROCESSING,
    )

    if not inter_payout_configured():
        return wd
    if wd.status not in WD_PAYOUT_OPEN_STATUSES:
        return wd
    if wd.status == WD_PROCESSING and (wd.inter_codigo_solicitacao or "").strip():
        return wd
    amount = money(Decimal(str(wd.amount)))
    chave = normalize_pix_key(wd.pix_key)
    client = InterPayoutClient()
    try:
        saldo = client.saldo()
        if saldo < amount:
            wd.status = WD_AWAITING_BALANCE
            wd.payment_error = f"Saldo Inter insuficiente (disponível R$ {saldo})."
            db.flush()
            return wd
    except HTTPException:
        pass
    label = descricao or f"Saque fornecedor {wd.id[:8]}"
    try:
        body = client.incluir_pix(
            valor=amount,
            chave_pix=chave,
            descricao=label,
            idempotency_key=wd.id,
        )
    except HTTPException as exc:
        wd.status = WD_FAILED
        wd.payment_error = str(exc.detail)[:500]
        db.flush()
        raise
    wd.inter_codigo_solicitacao = _extract_codigo(body)
    wd.inter_end_to_end_id = _extract_end_to_end(body)
    wd.inter_payment_json = json.dumps(body, ensure_ascii=False)
    wd.payment_error = None
    if _status_liquidado(body):
        from datetime import UTC, datetime

        wd.status = WD_PAID
        wd.processed_at = datetime.now(UTC)
    else:
        wd.status = WD_PROCESSING
    db.flush()
    return wd


def retry_supplier_withdrawal_pix(db: Session, wd: SupplierWithdrawal) -> SupplierWithdrawal:
    from app.supplier_wallet_service import WD_AWAITING_BALANCE, WD_FAILED, WD_PENDING, WD_PROCESSING

    if wd.status not in {WD_PENDING, WD_FAILED, WD_AWAITING_BALANCE, WD_PROCESSING}:
        raise HTTPException(status_code=409, detail="Saque não elegível para reenvio PIX.")
    if wd.status in {WD_FAILED, WD_AWAITING_BALANCE}:
        wd.status = WD_PENDING
        wd.payment_error = None
        db.flush()
    return submit_supplier_withdrawal_pix(db, wd)


def try_auto_partner_withdrawal(db: Session, wd: PartnerWithdrawal) -> dict:
    if inter_payout_auto_enabled():
        try:
            submit_partner_withdrawal_pix(db, wd)
        except HTTPException:
            pass
    return withdrawal_view(wd)


def resolve_partner_pix_key(db: Session, user: User) -> str | None:
    last = db.scalar(
        select(PartnerWithdrawal)
        .where(PartnerWithdrawal.user_id == user.id, PartnerWithdrawal.pix_key.isnot(None))
        .order_by(PartnerWithdrawal.created_at.desc())
        .limit(1)
    )
    if last and (last.pix_key or "").strip():
        return last.pix_key.strip()
    doc = (user.document or "").strip()
    if len(re.sub(r"\D+", "", doc)) in {11, 14}:
        return re.sub(r"\D+", "", doc)
    return None


def retry_partner_withdrawal_pix(db: Session, wd: PartnerWithdrawal) -> PartnerWithdrawal:
    if wd.status not in {WD_PENDING, WD_FAILED, WD_AWAITING_BALANCE, WD_PROCESSING}:
        raise HTTPException(status_code=409, detail="Saque não elegível para reenvio PIX.")
    if wd.status in {WD_FAILED, WD_AWAITING_BALANCE}:
        wd.status = WD_PENDING
        wd.payment_error = None
        db.flush()
    return submit_partner_withdrawal_pix(db, wd)


def payout_partner_after_fiscal_release(
    db: Session,
    user: User,
    amount: Decimal,
    *,
    nf_access_key: str | None = None,
) -> dict | None:
    from app.core.config import settings

    if not settings.inter_payout_on_fiscal_release or not inter_payout_configured():
        return None
    value = money(amount)
    if value <= 0:
        return None
    open_wd = db.scalar(
        select(PartnerWithdrawal).where(
            PartnerWithdrawal.user_id == user.id,
            PartnerWithdrawal.status.in_(list(WD_OPEN_STATUSES)),
        )
    )
    if open_wd:
        return {"skipped": True, "reason": "saque_aberto", "withdrawal_id": open_wd.id}
    pix = resolve_partner_pix_key(db, user)
    if not pix:
        return {"skipped": True, "reason": "sem_chave_pix"}
    desc = f"NF-e {nf_access_key[:12]}..." if nf_access_key else "Comissão NF validada"
    wd = PartnerWithdrawal(
        organization_id=user.organization_id,
        user_id=user.id,
        amount=value,
        status=WD_PENDING,
        pix_key=pix,
        notes=desc,
    )
    db.add(wd)
    db.flush()
    submit_partner_withdrawal_pix(db, wd, descricao=desc[:140])
    return {"withdrawal_id": wd.id, "status": wd.status}


def _poll_partner_rows(db: Session, client: InterPayoutClient, *, limit: int) -> tuple[int, int]:
    from app.inter_payout_webhook_service import complete_partner_withdrawal_paid

    rows = list(
        db.scalars(
            select(PartnerWithdrawal)
            .where(
                PartnerWithdrawal.status.in_([WD_PROCESSING, WD_AWAITING_BALANCE]),
            )
            .order_by(PartnerWithdrawal.created_at.asc())
            .limit(max(1, min(limit, 200)))
        )
    )
    updated = 0
    for wd in rows:
        codigo = (wd.inter_codigo_solicitacao or "").strip()
        if not codigo:
            if wd.status == WD_AWAITING_BALANCE:
                try:
                    retry_partner_withdrawal_pix(db, wd)
                    updated += 1
                except HTTPException:
                    pass
            continue
        try:
            detail = client.consultar_pix(codigo)
        except HTTPException:
            continue
        result = complete_partner_withdrawal_paid(db, wd, detail)
        if result.get("processed"):
            updated += 1
    return len(rows), updated


def _poll_supplier_rows(db: Session, client: InterPayoutClient, *, limit: int) -> tuple[int, int]:
    from app.inter_payout_webhook_service import complete_supplier_withdrawal_paid
    from app.supplier_wallet_service import WD_AWAITING_BALANCE, WD_PROCESSING

    rows = list(
        db.scalars(
            select(SupplierWithdrawal)
            .where(SupplierWithdrawal.status.in_([WD_PROCESSING, WD_AWAITING_BALANCE]))
            .order_by(SupplierWithdrawal.created_at.asc())
            .limit(max(1, min(limit, 200)))
        )
    )
    updated = 0
    for wd in rows:
        codigo = (wd.inter_codigo_solicitacao or "").strip()
        if not codigo:
            if wd.status == WD_AWAITING_BALANCE:
                try:
                    retry_supplier_withdrawal_pix(db, wd)
                    updated += 1
                except HTTPException:
                    pass
            continue
        try:
            detail = client.consultar_pix(codigo)
        except HTTPException:
            continue
        result = complete_supplier_withdrawal_paid(db, wd, detail)
        if result.get("processed"):
            updated += 1
    return len(rows), updated


def poll_processing_partner_withdrawals(db: Session, *, limit: int = 50) -> dict:
    if not inter_payout_configured():
        return {"polled": 0, "updated": 0, "partner": {"polled": 0, "updated": 0}, "supplier": {"polled": 0, "updated": 0}}
    client = InterPayoutClient()
    p_polled, p_updated = _poll_partner_rows(db, client, limit=limit)
    s_polled, s_updated = _poll_supplier_rows(db, client, limit=limit)
    return {
        "polled": p_polled + s_polled,
        "updated": p_updated + s_updated,
        "partner": {"polled": p_polled, "updated": p_updated},
        "supplier": {"polled": s_polled, "updated": s_updated},
    }
