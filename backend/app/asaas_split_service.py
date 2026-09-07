"""Split nativo Asaas — grade MMN na fonte do pagamento."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.asaas_client import AsaasClient
from app.asaas_common import asaas_configured
from app.core.config import settings
from app.models import CommissionEntry, EscrowAccount, PaymentSplitInstruction, User
from app.network_service import money
from app.universal_mmn_service import plan_universal_mmn_allocations

SPLIT_STATUSES = {"PLANNED", "SUBMITTED", "SETTLED", "SKIPPED", "FAILED"}
PAYMENT_SPLIT_DONE = "PAYMENT_SPLIT_DONE"


def asaas_split_live() -> bool:
    return bool(settings.asaas_split_enabled and asaas_configured())


def wallet_id_for_user(db: Session, organization_id: str, user_id: str) -> str | None:
    account = db.scalar(
        select(EscrowAccount).where(
            EscrowAccount.organization_id == organization_id,
            EscrowAccount.user_id == user_id,
        )
    )
    if not account:
        return None
    wallet_id = (account.external_account_id or "").strip()
    if not wallet_id or wallet_id.startswith("mock_"):
        return None
    issuer_wallet = (settings.asaas_wallet_id or "").strip()
    if issuer_wallet and wallet_id == issuer_wallet:
        return None
    return wallet_id


def plan_mmn_payment_splits(
    db: Session,
    organization_id: str,
    originator_id: str,
    pool_amount: Decimal,
    *,
    reference: str,
) -> dict:
    """Monta plano de split Asaas a partir da grade universal MMN."""
    layers = plan_universal_mmn_allocations(db, organization_id, originator_id, pool_amount)
    issuer_wallet = (settings.asaas_wallet_id or "").strip()
    splits: list[dict] = []
    skipped: list[dict] = []
    wallet_totals: dict[str, Decimal] = {}

    for layer in layers:
        beneficiary_id = layer["beneficiary_id"]
        wallet_id = wallet_id_for_user(db, organization_id, beneficiary_id)
        amount = layer["amount"]
        if not wallet_id:
            skipped.append(
                {
                    "layer_name": layer["layer_name"],
                    "level": layer["level"],
                    "beneficiary_id": beneficiary_id,
                    "amount": str(amount),
                    "reason": "SUBACCOUNT_WALLET_MISSING",
                }
            )
            continue
        wallet_totals[wallet_id] = money(wallet_totals.get(wallet_id, Decimal("0")) + amount)

    for wallet_id, amount in wallet_totals.items():
        if amount <= 0:
            continue
        splits.append(
            {
                "walletId": wallet_id,
                "fixedValue": float(amount),
                "externalReference": f"{reference}:{wallet_id[:8]}",
                "description": f"MMN {reference}",
            }
        )

    split_total = money(sum(Decimal(str(item["fixedValue"])) for item in splits))
    return {
        "reference": reference,
        "originator_id": originator_id,
        "pool_amount": str(money(pool_amount)),
        "split_total": str(split_total),
        "issuer_wallet_id": issuer_wallet or None,
        "splits": splits,
        "skipped": skipped,
        "execution": "ASAAS_SPLIT" if asaas_split_live() and splits else "PREVIEW_ONLY",
    }


def persist_split_instructions(
    db: Session,
    actor: User,
    *,
    reference: str,
    plan: dict,
    asaas_payment_id: str | None = None,
    status: str = "PLANNED",
) -> list[PaymentSplitInstruction]:
    existing = list(
        db.scalars(
            select(PaymentSplitInstruction).where(
                PaymentSplitInstruction.organization_id == actor.organization_id,
                PaymentSplitInstruction.reference == reference,
            )
        )
    )
    if existing:
        return existing

    layers = plan_universal_mmn_allocations(
        db,
        actor.organization_id,
        plan["originator_id"],
        Decimal(str(plan["pool_amount"])),
    )
    split_by_wallet = {row["walletId"]: row for row in plan.get("splits", [])}
    skipped_levels = {row["level"] for row in plan.get("skipped", [])}
    rows: list[PaymentSplitInstruction] = []

    for layer in layers:
        wallet_id = wallet_id_for_user(db, actor.organization_id, layer["beneficiary_id"])
        layer_status = status
        if layer["level"] in skipped_levels or not wallet_id:
            layer_status = "SKIPPED"
            wallet_id = None
        item = PaymentSplitInstruction(
            organization_id=actor.organization_id,
            reference=reference,
            asaas_payment_id=asaas_payment_id,
            beneficiary_id=layer["beneficiary_id"],
            layer_name=layer["layer_name"],
            level=layer["level"],
            wallet_id=wallet_id,
            amount=float(layer["amount"]),
            status=layer_status,
            detail_json=json.dumps(
                {
                    "share_percent": str(layer["share_percent"]),
                    "asaas_external_reference": split_by_wallet.get(wallet_id or "", {}).get("externalReference"),
                },
                ensure_ascii=False,
            ),
        )
        db.add(item)
        rows.append(item)
    db.flush()
    return rows


def asaas_split_payload(plan: dict) -> list[dict]:
    return [
        {
            "walletId": row["walletId"],
            "fixedValue": row["fixedValue"],
            "externalReference": row.get("externalReference"),
            "description": row.get("description"),
        }
        for row in plan.get("splits", [])
    ]


def create_payment_with_mmn_split(
    db: Session,
    actor: User,
    *,
    customer_id: str,
    billing_type: str,
    value: Decimal,
    due_date: str,
    description: str,
    originator_id: str,
    pool_amount: Decimal,
    reference: str,
) -> dict:
    if value <= 0 or pool_amount <= 0:
        raise HTTPException(status_code=422, detail="Valor da cobrança e pool MMN devem ser positivos")
    if pool_amount > value:
        raise HTTPException(status_code=422, detail="Pool MMN não pode exceder o valor bruto da cobrança")

    plan = plan_mmn_payment_splits(
        db,
        actor.organization_id,
        originator_id,
        pool_amount,
        reference=reference,
    )
    if not plan["splits"]:
        raise HTTPException(
            status_code=422,
            detail="Nenhum beneficiário com carteira Asaas elegível para split",
        )

    if not asaas_split_live():
        rows = persist_split_instructions(db, actor, reference=reference, plan=plan, status="PLANNED")
        return {
            **plan,
            "payment_id": None,
            "status": "PREVIEW_ONLY",
            "instructions": [_instruction_view(row) for row in rows],
        }

    payload = {
        "customer": customer_id,
        "billingType": billing_type.upper(),
        "value": float(money(value)),
        "dueDate": due_date,
        "description": description,
        "externalReference": reference,
        "split": asaas_split_payload(plan),
    }
    with AsaasClient() as client:
        payment = client.create_payment(payload)

    payment_id = str(payment.get("id") or "").strip() or None
    rows = persist_split_instructions(
        db,
        actor,
        reference=reference,
        plan=plan,
        asaas_payment_id=payment_id,
        status="SUBMITTED",
    )
    return {
        **plan,
        "payment_id": payment_id,
        "status": str(payment.get("status") or "PENDING"),
        "checkout_url": payment.get("invoiceUrl") or payment.get("bankSlipUrl"),
        "instructions": [_instruction_view(row) for row in rows],
    }


def link_split_instructions_to_commissions(
    db: Session,
    organization_id: str,
    reference: str,
) -> int:
    entries = list(
        db.scalars(
            select(CommissionEntry).where(
                CommissionEntry.organization_id == organization_id,
                CommissionEntry.reference == reference,
            )
        )
    )
    if not entries:
        return 0
    instructions = list(
        db.scalars(
            select(PaymentSplitInstruction).where(
                PaymentSplitInstruction.organization_id == organization_id,
                PaymentSplitInstruction.reference == reference,
            )
        )
    )
    linked = 0
    by_level = {row.level: row for row in instructions}
    for entry in entries:
        instruction = by_level.get(entry.level)
        if instruction and not instruction.commission_entry_id:
            instruction.commission_entry_id = entry.id
            linked += 1
    db.flush()
    return linked


def handle_payment_split_done(db: Session, payload: dict) -> dict:
    payment = payload.get("payment") if isinstance(payload.get("payment"), dict) else {}
    additional = payload.get("additionalInfo") if isinstance(payload.get("additionalInfo"), dict) else {}
    split_id = str(additional.get("splitId") or payload.get("splitId") or "").strip() or None
    payment_id = str(payment.get("id") or payload.get("paymentId") or "").strip() or None
    external_ref = str(additional.get("externalReference") or "").strip() or None

    query = select(PaymentSplitInstruction)
    if split_id:
        row = db.scalar(query.where(PaymentSplitInstruction.asaas_split_id == split_id))
    elif payment_id and external_ref:
        row = db.scalar(
            query.where(
                PaymentSplitInstruction.asaas_payment_id == payment_id,
                PaymentSplitInstruction.detail_json.contains(external_ref),
            )
        )
    elif payment_id:
        rows = list(db.scalars(query.where(PaymentSplitInstruction.asaas_payment_id == payment_id)))
        row = rows[0] if len(rows) == 1 else None
    else:
        row = None

    if not row and external_ref and ":" in external_ref:
        reference = external_ref.split(":", 1)[0]
        wallet_hint = external_ref.split(":", 1)[1][:8]
        candidates = list(
            db.scalars(
                select(PaymentSplitInstruction).where(
                    PaymentSplitInstruction.reference == reference,
                    PaymentSplitInstruction.wallet_id.is_not(None),
                )
            )
        )
        row = next((item for item in candidates if (item.wallet_id or "").startswith(wallet_hint)), None)

    if not row:
        return {"processed": False, "reason": "SPLIT_INSTRUCTION_NOT_FOUND", "split_id": split_id}

    if split_id:
        row.asaas_split_id = split_id
    if payment_id and not row.asaas_payment_id:
        row.asaas_payment_id = payment_id
    row.status = "SETTLED"
    row.settled_at = datetime.now(UTC)
    db.flush()

    if row.commission_entry_id:
        entry = db.get(CommissionEntry, row.commission_entry_id)
        if entry and entry.status in {"PENDING_FISCAL", "PENDING_RECEIPT"}:
            pass
    return {
        "processed": True,
        "instruction_id": row.id,
        "reference": row.reference,
        "split_id": split_id,
        "status": row.status,
    }


def list_split_instructions(
    db: Session,
    actor: User,
    *,
    reference: str | None = None,
) -> list[dict]:
    stmt = select(PaymentSplitInstruction).where(
        PaymentSplitInstruction.organization_id == actor.organization_id,
    )
    if reference:
        stmt = stmt.where(PaymentSplitInstruction.reference == reference)
    rows = list(db.scalars(stmt.order_by(PaymentSplitInstruction.created_at.desc())))
    return [_instruction_view(row) for row in rows]


def _instruction_view(row: PaymentSplitInstruction) -> dict:
    return {
        "id": row.id,
        "reference": row.reference,
        "asaas_payment_id": row.asaas_payment_id,
        "beneficiary_id": row.beneficiary_id,
        "commission_entry_id": row.commission_entry_id,
        "layer_name": row.layer_name,
        "level": row.level,
        "wallet_id": row.wallet_id,
        "amount": str(money(Decimal(str(row.amount)))),
        "asaas_split_id": row.asaas_split_id,
        "status": row.status,
        "settled_at": row.settled_at.isoformat() if row.settled_at else None,
    }


def mock_create_payment_with_split(
    db: Session,
    actor: User,
    *,
    customer_id: str,
    billing_type: str,
    value: Decimal,
    due_date: str,
    description: str,
    originator_id: str,
    pool_amount: Decimal,
    reference: str | None = None,
) -> dict:
    """Sandbox local sem API Asaas — gera payment_id fictício para testes."""
    ref = reference or f"MMN-SPLIT-{uuid4().hex[:12]}"
    plan = plan_mmn_payment_splits(db, actor.organization_id, originator_id, pool_amount, reference=ref)
    payment_id = f"pay_mock_{uuid4().hex[:10]}"
    rows = persist_split_instructions(
        db,
        actor,
        reference=ref,
        plan=plan,
        asaas_payment_id=payment_id,
        status="SUBMITTED",
    )
    return {
        **plan,
        "payment_id": payment_id,
        "status": "PENDING",
        "checkout_url": None,
        "instructions": [_instruction_view(row) for row in rows],
        "mock": True,
    }
