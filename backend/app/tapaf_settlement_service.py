"""Split contábil TAPAF (Lote A / Lote B) e registro no ledger."""

from __future__ import annotations

import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.finops_engine import ingest_event
from app.infra_inventory_service import attach_inventory_to_settlement
from app.models import TapafSettlement, User
from app.services import audit, post_double_entry
from app.tapaf_constants import (
    LEDGER_API_PREPAID,
    LEDGER_BAAS_CLEARING,
    LEDGER_FRANCHISE_UPFRONT,
    LEDGER_TAPAF_POOL,
    compute_tapaf_split,
)


def settle_tapaf_payment(
    db: Session,
    user: User,
    *,
    track: str,
    entity_type: str,
    entity_id: str,
    payment_event_id: str,
    total_amount: Decimal,
    inventory_context: dict | None = None,
) -> TapafSettlement:
    existing = db.scalar(
        select(TapafSettlement).where(
            TapafSettlement.organization_id == user.organization_id,
            TapafSettlement.payment_event_id == payment_event_id,
        )
    )
    if existing:
        return existing

    split = compute_tapaf_split(total_amount)
    lote_a = Decimal(split["lote_a_api_reserve_brl"])
    lote_b = Decimal(split["lote_b_franchise_spread_brl"])
    ledger_ref = f"tapaf-settlement-{payment_event_id}"

    settlement = TapafSettlement(
        organization_id=user.organization_id,
        track=track.upper(),
        entity_type=entity_type,
        entity_id=entity_id,
        payment_event_id=payment_event_id,
        total_amount=total_amount,
        lote_a_amount=lote_a,
        lote_b_amount=lote_b,
        ledger_reference=ledger_ref,
        inventory_json="{}",
    )
    db.add(settlement)
    db.flush()

    post_double_entry(
        db,
        user,
        reference=ledger_ref,
        event_type="TAPAF_RECEIVED",
        description=f"TAPAF recebida — {entity_type}:{entity_id}",
        debit_account=LEDGER_BAAS_CLEARING,
        credit_account=LEDGER_TAPAF_POOL,
        amount=total_amount,
    )
    post_double_entry(
        db,
        user,
        reference=f"{ledger_ref}-lote-a",
        event_type="TAPAF_LOTE_A",
        description="Reserva Lote A — custos de consulta APIs",
        debit_account=LEDGER_TAPAF_POOL,
        credit_account=LEDGER_API_PREPAID,
        amount=lote_a,
    )
    post_double_entry(
        db,
        user,
        reference=f"{ledger_ref}-lote-b",
        event_type="TAPAF_LOTE_B",
        description="Spread Lote B — franqueadora upfront",
        debit_account=LEDGER_TAPAF_POOL,
        credit_account=LEDGER_FRANCHISE_UPFRONT,
        amount=lote_b,
    )

    payload = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "track": track,
        **split,
        "ledger_reference": ledger_ref,
    }
    ingest_event(
        db,
        user,
        event_id=f"tapaf-settled-{payment_event_id}",
        event_type="tapaf.payment.settled",
        aggregate_id=entity_id,
        payload=payload,
    )

    attach_inventory_to_settlement(
        db,
        settlement,
        track=track,
        context=inventory_context or {"entity_id": entity_id},
    )

    audit(
        db,
        user,
        "finops.tapaf.settled",
        entity_type,
        entity_id,
        {
            "payment_event_id": payment_event_id,
            "split": split,
            "ledger_reference": ledger_ref,
        },
    )
    db.flush()
    return settlement
