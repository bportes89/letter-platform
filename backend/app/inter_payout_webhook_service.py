"""Webhook Banco Inter — liquidação de PIX pagamento (saída)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.inter_payout_service import _extract_codigo, _extract_end_to_end, _status_liquidado
from app.models import PartnerWithdrawal, SupplierWithdrawal, User
from app.partner_legacy_wallet_service import (
    WD_FAILED,
    WD_PAID,
    WD_PROCESSING,
    _consume_available_entries,
    money,
)

logger = logging.getLogger(__name__)


def _normalize_items(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        if any(k in payload for k in ("codigoSolicitacao", "codigo_solicitacao", "endToEndId", "status", "situacao")):
            return [payload]
        nested = payload.get("data") or payload.get("items") or payload.get("eventos")
        if isinstance(nested, list):
            return [x for x in nested if isinstance(x, dict)]
    return []


def _find_partner_withdrawal(db: Session, codigo: str | None, e2e: str | None) -> PartnerWithdrawal | None:
    if codigo:
        row = db.scalar(
            select(PartnerWithdrawal).where(PartnerWithdrawal.inter_codigo_solicitacao == codigo).limit(1)
        )
        if row:
            return row
    if e2e:
        return db.scalar(
            select(PartnerWithdrawal).where(PartnerWithdrawal.inter_end_to_end_id == e2e).limit(1)
        )
    return None


def _find_supplier_withdrawal(db: Session, codigo: str | None, e2e: str | None) -> SupplierWithdrawal | None:
    if codigo:
        row = db.scalar(
            select(SupplierWithdrawal).where(SupplierWithdrawal.inter_codigo_solicitacao == codigo).limit(1)
        )
        if row:
            return row
    if e2e:
        return db.scalar(
            select(SupplierWithdrawal).where(SupplierWithdrawal.inter_end_to_end_id == e2e).limit(1)
        )
    return None


def _fail_partner(db: Session, wd: PartnerWithdrawal, message: str) -> dict:
    wd.status = WD_FAILED
    wd.payment_error = (message or "Falha PIX Inter")[:500]
    db.flush()
    return {"processed": True, "kind": "partner", "withdrawal_id": wd.id, "status": wd.status}


def complete_partner_withdrawal_paid(db: Session, wd: PartnerWithdrawal, body: dict) -> dict:
    if wd.status == WD_PAID:
        return {"processed": False, "reason": "ja_pago", "withdrawal_id": wd.id, "idempotent": True}
    situacao = str(body.get("status") or body.get("situacao") or "").upper()
    if situacao in {"REJEITADO", "CANCELADO", "ERRO", "FALHA"}:
        return _fail_partner(db, wd, situacao)
    if wd.status not in {WD_PROCESSING, "PENDING"} and not _status_liquidado(body):
        return {"processed": False, "reason": "status_ignorado", "withdrawal_id": wd.id, "situacao": situacao}
    if not _status_liquidado(body) and situacao not in {"", "PROCESSANDO", "EM_PROCESSAMENTO"}:
        return {"processed": False, "reason": "nao_liquidado", "withdrawal_id": wd.id}
    partner = db.get(User, wd.user_id)
    if not partner:
        return {"processed": False, "reason": "parceiro_ausente", "withdrawal_id": wd.id}
    amount = money(Decimal(str(wd.amount)))
    e2e = _extract_end_to_end(body)
    if e2e:
        wd.inter_end_to_end_id = e2e
    wd.inter_payment_json = json.dumps(body, ensure_ascii=False)
    wd.payment_error = None
    if wd.status != WD_PAID:
        _consume_available_entries(db, partner, amount)
        wd.status = WD_PAID
        wd.processed_at = datetime.now(UTC)
    db.flush()
    return {"processed": True, "kind": "partner", "withdrawal_id": wd.id, "status": WD_PAID}


def complete_supplier_withdrawal_paid(db: Session, wd: SupplierWithdrawal, body: dict) -> dict:
    if wd.status == "PAID":
        return {"processed": False, "reason": "ja_pago", "withdrawal_id": wd.id, "idempotent": True}
    situacao = str(body.get("status") or body.get("situacao") or "").upper()
    if situacao in {"REJEITADO", "CANCELADO", "ERRO", "FALHA"}:
        wd.status = "FAILED"
        wd.payment_error = situacao[:500]
        db.flush()
        return {"processed": True, "kind": "supplier", "withdrawal_id": wd.id, "status": wd.status}
    if not _status_liquidado(body):
        return {"processed": False, "reason": "nao_liquidado", "withdrawal_id": wd.id}
    e2e = _extract_end_to_end(body)
    if e2e:
        wd.inter_end_to_end_id = e2e
    wd.inter_payment_json = json.dumps(body, ensure_ascii=False)
    wd.status = "PAID"
    wd.processed_at = datetime.now(UTC)
    wd.payment_error = None
    db.flush()
    return {"processed": True, "kind": "supplier", "withdrawal_id": wd.id, "status": "PAID"}


def handle_inter_payout_webhook(db: Session, payload: object) -> dict:
    items = _normalize_items(payload)
    stats = {"total": len(items), "paid": 0, "skipped": 0, "results": []}
    for item in items:
        codigo = _extract_codigo(item) or str(item.get("codigoSolicitacao") or item.get("codigo_solicitacao") or "").strip()
        e2e = _extract_end_to_end(item) or str(item.get("endToEndId") or "").strip()
        if not codigo and not e2e:
            stats["skipped"] += 1
            stats["results"].append({"processed": False, "reason": "sem_identificador"})
            continue

        partner_wd = _find_partner_withdrawal(db, codigo or None, e2e or None)
        if partner_wd:
            result = complete_partner_withdrawal_paid(db, partner_wd, item)
            if result.get("processed") and result.get("status") == WD_PAID:
                stats["paid"] += 1
            else:
                stats["skipped"] += 1
            stats["results"].append(result)
            continue

        supplier_wd = _find_supplier_withdrawal(db, codigo or None, e2e or None)
        if supplier_wd:
            result = complete_supplier_withdrawal_paid(db, supplier_wd, item)
            if result.get("processed") and result.get("status") == "PAID":
                stats["paid"] += 1
            else:
                stats["skipped"] += 1
            stats["results"].append(result)
            continue

        stats["skipped"] += 1
        stats["results"].append(
            {"processed": False, "reason": "saque_nao_encontrado", "codigo_solicitacao": codigo or None}
        )
        logger.info("[InterPayoutWebhook] saque não encontrado codigo=%s e2e=%s", codigo, e2e)
    return stats
