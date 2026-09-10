"""Saldo, extrato e saque do fornecedor Marketplace."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Proposal, QuotaSupplier, SupplierLedgerEntry, SupplierWithdrawal, User
from app.quota_supplier_service import normalize_supplier_key, suppliers_index
from app.services import money

KIND_CREDIT = "CREDIT"
KIND_DEBIT = "DEBIT"
WD_PENDING = "PENDING"
WD_PAID = "PAID"
WD_CANCELLED = "CANCELLED"


def _supplier_by_source(db: Session, organization_id: str, source: str | None) -> QuotaSupplier | None:
    if not source:
        return None
    index = suppliers_index(db, organization_id)
    key = normalize_supplier_key(source)
    return index.get(key)


def credit_supplier_releases_from_snapshot(
    db: Session,
    proposal: Proposal,
    snapshot: dict,
) -> list[dict]:
    """Credita saldo do fornecedor a partir das linhas supplier_release (idempotente)."""
    reference = str(snapshot.get("reference") or "")
    if not reference:
        return []
    credited: list[dict] = []
    for line in snapshot.get("lines") or []:
        if not isinstance(line, dict) or line.get("type") != "supplier_release":
            continue
        amount = money(Decimal(str(line.get("amount") or 0)))
        if amount <= 0:
            continue
        source = line.get("supplier_source") or line.get("supplier_name")
        supplier = _supplier_by_source(db, proposal.organization_id, str(source) if source else None)
        if not supplier and line.get("supplier_id"):
            supplier = db.get(QuotaSupplier, str(line["supplier_id"]))
        if not supplier:
            # tenta source_key no índice pelo nome normalizado
            continue
        exists = db.scalar(
            select(SupplierLedgerEntry).where(
                SupplierLedgerEntry.supplier_id == supplier.id,
                SupplierLedgerEntry.reference == reference,
                SupplierLedgerEntry.kind == KIND_CREDIT,
            )
        )
        if exists:
            credited.append({"supplier_id": supplier.id, "amount": str(amount), "skipped": True})
            continue
        entry = SupplierLedgerEntry(
            organization_id=proposal.organization_id,
            supplier_id=supplier.id,
            kind=KIND_CREDIT,
            amount=amount,
            reference=reference,
            proposal_id=proposal.id,
            description=f"Liberação Marketplace — {reference}",
            meta_json=json.dumps(
                {
                    "quota_id": line.get("quota_id"),
                    "supplier_source": line.get("supplier_source"),
                    "platform_amount": line.get("platform_amount"),
                },
                ensure_ascii=False,
            ),
        )
        db.add(entry)
        supplier.balance_available = money(Decimal(str(supplier.balance_available or 0)) + amount)
        credited.append({"supplier_id": supplier.id, "amount": str(amount), "skipped": False})
    db.flush()
    return credited


def portal_wallet(supplier: QuotaSupplier) -> dict:
    return {
        "supplier_id": supplier.id,
        "balance_available": str(money(Decimal(str(supplier.balance_available or 0)))),
        "pix_key": supplier.pix_key,
    }


def list_ledger(db: Session, supplier: QuotaSupplier, *, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit or 100), 300))
    rows = list(
        db.scalars(
            select(SupplierLedgerEntry)
            .where(SupplierLedgerEntry.supplier_id == supplier.id)
            .order_by(SupplierLedgerEntry.created_at.desc())
            .limit(limit)
        )
    )
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "amount": str(money(Decimal(str(r.amount)))),
            "reference": r.reference,
            "proposal_id": r.proposal_id,
            "description": r.description,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def request_withdrawal(
    db: Session,
    supplier: QuotaSupplier,
    *,
    amount: Decimal | str | float,
    pix_key: str | None = None,
    notes: str | None = None,
) -> dict:
    value = money(Decimal(str(amount)))
    if value <= 0:
        raise HTTPException(422, "Informe um valor de saque válido.")
    balance = money(Decimal(str(supplier.balance_available or 0)))
    if value > balance:
        raise HTTPException(409, "Saldo insuficiente para o saque solicitado.")
    key = (pix_key or supplier.pix_key or "").strip()
    if len(key) < 5:
        raise HTTPException(422, "Cadastre uma chave PIX no fornecedor antes de sacar.")
    pending = db.scalar(
        select(SupplierWithdrawal).where(
            SupplierWithdrawal.supplier_id == supplier.id,
            SupplierWithdrawal.status == WD_PENDING,
        )
    )
    if pending:
        raise HTTPException(409, "Já existe um saque pendente. Aguarde o processamento.")

    # reserva: debita saldo e lança DEBIT no extrato
    reference = f"SUPPLIER_WITHDRAW:{supplier.id}:{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    entry = SupplierLedgerEntry(
        organization_id=supplier.organization_id,
        supplier_id=supplier.id,
        kind=KIND_DEBIT,
        amount=value,
        reference=reference,
        description="Saque solicitado (reservado)",
        meta_json=json.dumps({"pix_key": key}, ensure_ascii=False),
    )
    db.add(entry)
    db.flush()
    supplier.balance_available = money(balance - value)
    if not supplier.pix_key:
        supplier.pix_key = key
    wd = SupplierWithdrawal(
        organization_id=supplier.organization_id,
        supplier_id=supplier.id,
        amount=value,
        status=WD_PENDING,
        pix_key=key,
        notes=(notes or "").strip() or None,
        ledger_entry_id=entry.id,
    )
    db.add(wd)
    db.flush()
    return withdrawal_view(wd)


def list_withdrawals_for_supplier(db: Session, supplier: QuotaSupplier, *, limit: int = 50) -> list[dict]:
    limit = max(1, min(int(limit or 50), 200))
    rows = list(
        db.scalars(
            select(SupplierWithdrawal)
            .where(SupplierWithdrawal.supplier_id == supplier.id)
            .order_by(SupplierWithdrawal.created_at.desc())
            .limit(limit)
        )
    )
    return [withdrawal_view(r) for r in rows]


def list_withdrawals_admin(db: Session, user: User, *, status: str | None = None, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit or 100), 300))
    q = select(SupplierWithdrawal).where(SupplierWithdrawal.organization_id == user.organization_id)
    if status:
        q = q.where(SupplierWithdrawal.status == status.strip().upper())
    rows = list(db.scalars(q.order_by(SupplierWithdrawal.created_at.desc()).limit(limit)))
    out = []
    for row in rows:
        view = withdrawal_view(row)
        supplier = db.get(QuotaSupplier, row.supplier_id)
        view["supplier_name"] = supplier.name if supplier else None
        view["supplier_source_key"] = supplier.source_key if supplier else None
        out.append(view)
    return out


def process_withdrawal(
    db: Session,
    user: User,
    withdrawal_id: str,
    *,
    action: str,
    notes: str | None = None,
) -> dict:
    action = (action or "").strip().upper()
    if action not in {"PAID", "CANCELLED"}:
        raise HTTPException(422, "Ação inválida. Use PAID ou CANCELLED.")
    wd = db.scalar(
        select(SupplierWithdrawal).where(
            SupplierWithdrawal.id == withdrawal_id,
            SupplierWithdrawal.organization_id == user.organization_id,
        )
    )
    if not wd:
        raise HTTPException(404, "Saque não encontrado.")
    if wd.status != WD_PENDING:
        raise HTTPException(409, f"Saque já está {wd.status}.")
    supplier = db.get(QuotaSupplier, wd.supplier_id)
    if not supplier:
        raise HTTPException(404, "Fornecedor não encontrado.")

    if action == WD_CANCELLED:
        # devolve saldo
        amount = money(Decimal(str(wd.amount)))
        supplier.balance_available = money(Decimal(str(supplier.balance_available or 0)) + amount)
        credit = SupplierLedgerEntry(
            organization_id=supplier.organization_id,
            supplier_id=supplier.id,
            kind=KIND_CREDIT,
            amount=amount,
            reference=f"SUPPLIER_WITHDRAW_CANCEL:{wd.id}",
            description="Saque cancelado — saldo devolvido",
            meta_json=json.dumps({"withdrawal_id": wd.id}, ensure_ascii=False),
        )
        db.add(credit)
        wd.status = WD_CANCELLED
    else:
        wd.status = WD_PAID

    wd.processed_at = datetime.now(UTC)
    wd.processed_by_user_id = user.id
    if notes:
        wd.notes = ((wd.notes or "") + f"\n{notes}").strip()
    db.flush()
    return withdrawal_view(wd)


def withdrawal_view(wd: SupplierWithdrawal) -> dict:
    return {
        "id": wd.id,
        "supplier_id": wd.supplier_id,
        "amount": str(money(Decimal(str(wd.amount)))),
        "status": wd.status,
        "pix_key": wd.pix_key,
        "notes": wd.notes,
        "ledger_entry_id": wd.ledger_entry_id,
        "processed_at": wd.processed_at.isoformat() if wd.processed_at else None,
        "created_at": wd.created_at.isoformat() if wd.created_at else None,
    }
