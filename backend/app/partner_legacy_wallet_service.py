"""Bank legado do parceiro — saldo em CommissionEntry (AVAILABLE) e saques PIX."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CommissionEntry, PartnerWithdrawal, User
from app.org_settings_service import get_setting
from app.services import money

WD_PENDING = "PENDING"
WD_PAID = "PAID"
WD_CANCELLED = "CANCELLED"
WITHDRAWN_STATUS = "WITHDRAWN"
HELD_STATUSES = frozenset({"PENDING_FISCAL", "PENDING_RECEIPT"})

_COMMISSION_STATUS_LABELS = {
    "AVAILABLE": "Liberada para saque",
    "PENDING_FISCAL": "Aguardando NF-e",
    "PENDING_RECEIPT": "Aguardando comprovante",
    "WITHDRAWN": "Sacada",
}
_WITHDRAWAL_STATUS_LABELS = {
    WD_PENDING: "Em análise",
    WD_PAID: "Pago",
    WD_CANCELLED: "Cancelado",
}


def commission_status_label(status: str | None) -> str:
    key = (status or "").strip().upper()
    return _COMMISSION_STATUS_LABELS.get(key, key or "—")


def withdrawal_status_label(status: str | None) -> str:
    key = (status or "").strip().upper()
    return _WITHDRAWAL_STATUS_LABELS.get(key, key or "—")


def _held_commission_total(db: Session, user: User) -> tuple[Decimal, Decimal, Decimal]:
    """Totais retidos (NF / comprovante) — saque legado só após liberação fiscal."""
    fiscal = db.scalar(
        select(func.coalesce(func.sum(CommissionEntry.amount), 0)).where(
            CommissionEntry.organization_id == user.organization_id,
            CommissionEntry.beneficiary_id == user.id,
            CommissionEntry.status == "PENDING_FISCAL",
        )
    )
    receipt = db.scalar(
        select(func.coalesce(func.sum(CommissionEntry.amount), 0)).where(
            CommissionEntry.organization_id == user.organization_id,
            CommissionEntry.beneficiary_id == user.id,
            CommissionEntry.status == "PENDING_RECEIPT",
        )
    )
    fiscal_m = money(Decimal(str(fiscal or 0)))
    receipt_m = money(Decimal(str(receipt or 0)))
    return fiscal_m, receipt_m, money(fiscal_m + receipt_m)


def withdrawal_blocked_reason(
    *,
    pending_fiscal: Decimal,
    pending_receipt: Decimal,
    withdrawable: Decimal,
    amount: Decimal,
) -> str | None:
    held = money(pending_fiscal + pending_receipt)
    if held > 0:
        parts: list[str] = []
        if pending_fiscal > 0:
            parts.append(f"NF-e (R$ {pending_fiscal})")
        if pending_receipt > 0:
            parts.append(f"comprovante (R$ {pending_receipt})")
        detail = " e ".join(parts)
        return (
            f"Há comissões aguardando liberação fiscal: {detail}. "
            "Valide a NF-e em Rede e comissões → Liberação fiscal SEFAZ antes de sacar."
        )
    if amount > withdrawable:
        return "Saldo disponível insuficiente (aguarde processamento de saque pendente ou libere comissões)."
    return None


def bank_display_mode(db: Session, organization_id: str) -> str:
    mode = (get_setting(db, organization_id, "bank_display_mode", "legacy") or "legacy").strip().lower()
    if mode in {"asaas", "conta", "digital"}:
        return "asaas"
    return "legacy"


def _pending_withdrawal_total(db: Session, user_id: str) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(PartnerWithdrawal.amount), 0)).where(
            PartnerWithdrawal.user_id == user_id,
            PartnerWithdrawal.status.in_([WD_PENDING, WD_PAID]),
        )
    )
    return money(Decimal(str(total or 0)))


def _available_commission_total(db: Session, user: User) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(CommissionEntry.amount), 0)).where(
            CommissionEntry.organization_id == user.organization_id,
            CommissionEntry.beneficiary_id == user.id,
            CommissionEntry.status == "AVAILABLE",
        )
    )
    return money(Decimal(str(total or 0)))


def _total_earned(db: Session, user: User) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(CommissionEntry.amount), 0)).where(
            CommissionEntry.organization_id == user.organization_id,
            CommissionEntry.beneficiary_id == user.id,
        )
    )
    return money(Decimal(str(total or 0)))


def _withdrawn_paid_total(db: Session, user_id: str) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(PartnerWithdrawal.amount), 0)).where(
            PartnerWithdrawal.user_id == user_id,
            PartnerWithdrawal.status == WD_PAID,
        )
    )
    return money(Decimal(str(total or 0)))


def partner_earnings_summary(db: Session, user: User) -> dict:
    available_entries = _available_commission_total(db, user)
    total_earned = _total_earned(db, user)
    withdrawn_total = _withdrawn_paid_total(db, user.id)
    pending_fiscal, pending_receipt, held_total = _held_commission_total(db, user)
    reserved = db.scalar(
        select(func.coalesce(func.sum(PartnerWithdrawal.amount), 0)).where(
            PartnerWithdrawal.user_id == user.id,
            PartnerWithdrawal.status == WD_PENDING,
        )
    )
    reserved = money(Decimal(str(reserved or 0)))
    withdrawable = money(max(Decimal("0.00"), available_entries - reserved))
    if held_total > 0:
        withdrawable = Decimal("0.00")
    min_raw = get_setting(db, user.organization_id, "min_withdrawal_amount", "0").strip().replace(",", ".")
    try:
        min_withdrawal = money(Decimal(min_raw or "0"))
    except Exception:
        min_withdrawal = Decimal("0.00")
    if held_total > 0:
        block_reason = withdrawal_blocked_reason(
            pending_fiscal=pending_fiscal,
            pending_receipt=pending_receipt,
            withdrawable=withdrawable,
            amount=Decimal("0.01"),
        )
    elif withdrawable <= 0:
        block_reason = "Não há saldo liberado para saque."
    elif min_withdrawal > 0 and withdrawable < min_withdrawal:
        block_reason = f"Valor mínimo para saque: R$ {min_withdrawal}."
    else:
        block_reason = None
    can_withdraw = block_reason is None
    pending_wd = db.scalar(
        select(PartnerWithdrawal).where(
            PartnerWithdrawal.user_id == user.id,
            PartnerWithdrawal.status == WD_PENDING,
        )
    )
    pending_withdrawal = withdrawal_view(pending_wd) if pending_wd else None
    if pending_wd and can_withdraw:
        can_withdraw = False
        block_reason = block_reason or "Já existe um saque em análise. Aguarde o processamento."
    return {
        "mode": "legacy",
        "total_earned": str(total_earned),
        "withdrawn_total": str(withdrawn_total),
        "available_total": str(available_entries),
        "pending_fiscal_total": str(pending_fiscal),
        "pending_receipt_total": str(pending_receipt),
        "held_commission_total": str(held_total),
        "withdrawable": str(withdrawable),
        "reserved_pending_withdrawal": str(reserved),
        "min_withdrawal_amount": str(min_withdrawal),
        "can_withdraw": can_withdraw,
        "withdrawal_blocked_reason": block_reason,
        "pending_withdrawal": pending_withdrawal,
    }


def list_partner_statement(db: Session, user: User, *, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit or 100), 300))
    rows: list[dict] = []
    entries = list(
        db.scalars(
            select(CommissionEntry)
            .where(
                CommissionEntry.organization_id == user.organization_id,
                CommissionEntry.beneficiary_id == user.id,
            )
            .order_by(CommissionEntry.created_at.desc())
            .limit(limit)
        )
    )
    for entry in entries:
        product = (entry.product or "rede").replace("_", " ")
        rows.append(
            {
                "id": entry.id,
                "kind": "commission",
                "direction": "CREDIT",
                "amount": str(money(Decimal(str(entry.amount)))),
                "status": entry.status,
                "status_label": commission_status_label(entry.status),
                "product": entry.product,
                "reference": entry.reference,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "label": f"Comissão · {product} (nível {entry.level})",
            }
        )
    withdrawals = list(
        db.scalars(
            select(PartnerWithdrawal)
            .where(PartnerWithdrawal.user_id == user.id)
            .order_by(PartnerWithdrawal.created_at.desc())
            .limit(limit)
        )
    )
    for wd in withdrawals:
        rows.append(
            {
                "id": wd.id,
                "kind": "withdrawal",
                "direction": "DEBIT",
                "amount": str(money(Decimal(str(wd.amount)))),
                "status": wd.status,
                "status_label": withdrawal_status_label(wd.status),
                "product": None,
                "reference": wd.id,
                "created_at": wd.created_at.isoformat() if wd.created_at else None,
                "label": "Saque via PIX",
            }
        )
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows[:limit]


def request_partner_withdrawal(
    db: Session,
    user: User,
    *,
    amount: Decimal | str | float,
    pix_key: str,
    notes: str | None = None,
) -> dict:
    value = money(Decimal(str(amount)))
    if value <= 0:
        raise HTTPException(422, "Informe um valor de saque válido.")
    summary = partner_earnings_summary(db, user)
    withdrawable = money(Decimal(str(summary["withdrawable"])))
    min_wd = money(Decimal(str(summary["min_withdrawal_amount"])))
    if min_wd > 0 and value < min_wd:
        raise HTTPException(422, f"Valor mínimo para saque: R$ {min_wd}.")
    pending_fiscal, pending_receipt, _held = _held_commission_total(db, user)
    block = withdrawal_blocked_reason(
        pending_fiscal=pending_fiscal,
        pending_receipt=pending_receipt,
        withdrawable=withdrawable,
        amount=value,
    )
    if block:
        raise HTTPException(409, block)
    key = (pix_key or "").strip()
    if len(key) < 5:
        raise HTTPException(422, "Informe uma chave PIX válida.")
    pending = db.scalar(
        select(PartnerWithdrawal).where(
            PartnerWithdrawal.user_id == user.id,
            PartnerWithdrawal.status == WD_PENDING,
        )
    )
    if pending:
        raise HTTPException(409, "Já existe um saque pendente. Aguarde o processamento.")

    wd = PartnerWithdrawal(
        organization_id=user.organization_id,
        user_id=user.id,
        amount=value,
        status=WD_PENDING,
        pix_key=key,
        notes=(notes or "").strip() or None,
    )
    db.add(wd)
    db.flush()
    return withdrawal_view(wd)


def withdrawal_view(wd: PartnerWithdrawal) -> dict:
    return {
        "id": wd.id,
        "user_id": wd.user_id,
        "amount": str(money(Decimal(str(wd.amount)))),
        "status": wd.status,
        "status_label": withdrawal_status_label(wd.status),
        "pix_key": wd.pix_key,
        "notes": wd.notes,
        "processed_at": wd.processed_at.isoformat() if wd.processed_at else None,
        "created_at": wd.created_at.isoformat() if wd.created_at else None,
    }


def list_partner_withdrawals(db: Session, user: User, *, limit: int = 30) -> list[dict]:
    limit = max(1, min(int(limit or 30), 100))
    rows = list(
        db.scalars(
            select(PartnerWithdrawal)
            .where(PartnerWithdrawal.user_id == user.id)
            .order_by(PartnerWithdrawal.created_at.desc())
            .limit(limit)
        )
    )
    return [withdrawal_view(wd) for wd in rows]


def _consume_available_entries(db: Session, user: User, amount: Decimal) -> None:
    remaining = money(amount)
    entries = list(
        db.scalars(
            select(CommissionEntry)
            .where(
                CommissionEntry.beneficiary_id == user.id,
                CommissionEntry.status == "AVAILABLE",
            )
            .order_by(CommissionEntry.created_at.asc())
        )
    )
    for entry in entries:
        if remaining <= 0:
            break
        entry_amount = money(Decimal(str(entry.amount)))
        if entry_amount <= remaining:
            entry.status = WITHDRAWN_STATUS
            remaining = money(remaining - entry_amount)
        else:
            raise HTTPException(
                409,
                "Não foi possível alocar o saque nas comissões disponíveis — contate o suporte.",
            )
    if remaining > 0:
        raise HTTPException(409, "Saldo de comissões AVAILABLE insuficiente para concluir o saque.")


def list_withdrawals_admin(db: Session, user: User, *, status: str | None = None, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit or 100), 300))
    q = select(PartnerWithdrawal).where(PartnerWithdrawal.organization_id == user.organization_id)
    if status:
        q = q.where(PartnerWithdrawal.status == status.strip().upper())
    rows = list(db.scalars(q.order_by(PartnerWithdrawal.created_at.desc()).limit(limit)))
    out = []
    for row in rows:
        view = withdrawal_view(row)
        partner = db.get(User, row.user_id)
        view["partner_name"] = partner.name if partner else None
        view["partner_email"] = partner.email if partner else None
        out.append(view)
    return out


def process_partner_withdrawal(
    db: Session,
    admin: User,
    withdrawal_id: str,
    *,
    action: str,
    notes: str | None = None,
) -> dict:
    action = (action or "").strip().upper()
    if action not in {WD_PAID, WD_CANCELLED}:
        raise HTTPException(422, "Ação inválida. Use PAID ou CANCELLED.")
    wd = db.scalar(
        select(PartnerWithdrawal).where(
            PartnerWithdrawal.id == withdrawal_id,
            PartnerWithdrawal.organization_id == admin.organization_id,
        )
    )
    if not wd:
        raise HTTPException(404, "Saque não encontrado.")
    if wd.status != WD_PENDING:
        raise HTTPException(409, "Saque já processado.")
    partner = db.get(User, wd.user_id)
    if not partner:
        raise HTTPException(404, "Parceiro não encontrado.")
    now = datetime.now(UTC)
    if action == WD_PAID:
        _consume_available_entries(db, partner, money(Decimal(str(wd.amount))))
        wd.status = WD_PAID
    else:
        wd.status = WD_CANCELLED
    wd.processed_at = now
    wd.processed_by_user_id = admin.id
    if notes:
        wd.notes = ((wd.notes or "") + f"\n{notes.strip()}").strip() or None
    db.flush()
    view = withdrawal_view(wd)
    view["partner_name"] = partner.name
    view["partner_email"] = partner.email
    return view
