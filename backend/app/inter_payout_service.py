"""Orquestração PIX saída — saques parceiro/fornecedor via API Inter (doc 170)."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.inter_payout_client import InterPayoutClient
from app.inter_payout_common import inter_payout_auto_enabled, inter_payout_configured
from app.models import PartnerWithdrawal, SupplierWithdrawal, User
from app.partner_legacy_wallet_service import (
    WD_FAILED,
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
    if wd.status not in {WD_PENDING, WD_PROCESSING}:
        return wd
    amount = money(Decimal(str(wd.amount)))
    chave = normalize_pix_key(wd.pix_key)
    client = InterPayoutClient()
    try:
        saldo = client.saldo()
        if saldo < amount:
            wd.status = WD_PENDING
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
    if not inter_payout_configured():
        return wd
    if wd.status not in {"PENDING", "PROCESSING"}:
        return wd
    amount = money(Decimal(str(wd.amount)))
    chave = normalize_pix_key(wd.pix_key)
    client = InterPayoutClient()
    label = descricao or f"Saque fornecedor {wd.id[:8]}"
    body = client.incluir_pix(
        valor=amount,
        chave_pix=chave,
        descricao=label,
        idempotency_key=wd.id,
    )
    wd.inter_codigo_solicitacao = _extract_codigo(body)
    wd.inter_end_to_end_id = _extract_end_to_end(body)
    wd.inter_payment_json = json.dumps(body, ensure_ascii=False)
    wd.payment_error = None
    if _status_liquidado(body):
        wd.status = "PAID"
        from datetime import UTC, datetime

        wd.processed_at = datetime.now(UTC)
    else:
        wd.status = "PROCESSING"
    db.flush()
    return wd


def try_auto_partner_withdrawal(db: Session, wd: PartnerWithdrawal) -> dict:
    if inter_payout_auto_enabled():
        try:
            submit_partner_withdrawal_pix(db, wd)
        except HTTPException:
            pass
    return withdrawal_view(wd)
