"""Orquestração do inventário infraestrutural pós-TAPAF."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra_clients import (
    DEFAULT_TAPAF_PROVIDERS,
    INFRA_CLIENTS,
    RURAL_TAPAF_PROVIDERS,
    VEHICLE_TAPAF_PROVIDERS,
    InfraQueryResult,
)
from app.models import TapafSettlement, User
from app.tapaf_constants import INFRA_PROVIDER_CATALOG, TAPAF_ESTIMATED_TOTAL_API_COST


def catalog() -> list[dict]:
    configured = {code: INFRA_CLIENTS[code].is_configured() for code in INFRA_CLIENTS}
    production_ready = {code: INFRA_CLIENTS[code].production_ready for code in INFRA_CLIENTS}
    return [
        {
            **item,
            "configured": configured.get(item["code"], False),
            "production_ready": production_ready.get(item["code"], False),
        }
        for item in INFRA_PROVIDER_CATALOG
    ]


def _providers_for_track(track: str) -> tuple[str, ...]:
    track = track.upper()
    if track == "VEHICLE":
        return DEFAULT_TAPAF_PROVIDERS + VEHICLE_TAPAF_PROVIDERS
    if track == "RURAL":
        return DEFAULT_TAPAF_PROVIDERS + RURAL_TAPAF_PROVIDERS
    return DEFAULT_TAPAF_PROVIDERS


def run_inventory(
    *,
    track: str,
    context: dict[str, Any],
) -> dict:
    provider_codes = _providers_for_track(track)
    results: list[InfraQueryResult] = []
    for code in provider_codes:
        client = INFRA_CLIENTS.get(code)
        if not client:
            continue
        results.append(client.query(context=context))

    total_estimated = sum(Decimal(r.estimated_cost_brl) for r in results)
    production_modes = sum(1 for r in results if r.mode == "PRODUCTION")
    return {
        "track": track,
        "providers": [
            {
                "code": r.provider_code,
                "status": r.status,
                "mode": r.mode,
                "external_reference": r.external_reference,
                "estimated_cost_brl": r.estimated_cost_brl,
                "payload": r.payload,
            }
            for r in results
        ],
        "estimated_total_cost_brl": str(total_estimated),
        "policy_estimated_cost_brl": str(TAPAF_ESTIMATED_TOTAL_API_COST),
        "execution": "PRODUCTION" if production_modes else "SANDBOX",
        "production_provider_count": production_modes,
    }


def attach_inventory_to_settlement(
    db: Session,
    settlement: TapafSettlement,
    *,
    track: str,
    context: dict[str, Any],
) -> dict:
    inventory = run_inventory(track=track, context=context)
    settlement.inventory_json = json.dumps(inventory, ensure_ascii=False)
    db.flush()
    return inventory


def settlement_view(item: TapafSettlement) -> dict:
    inventory = json.loads(item.inventory_json or "{}")
    return {
        "id": item.id,
        "track": item.track,
        "entity_type": item.entity_type,
        "entity_id": item.entity_id,
        "payment_event_id": item.payment_event_id,
        "total_brl": str(item.total_amount),
        "lote_a_api_reserve_brl": str(item.lote_a_amount),
        "lote_b_franchise_spread_brl": str(item.lote_b_amount),
        "ledger_reference": item.ledger_reference,
        "inventory": inventory,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def get_settlement(
    db: Session,
    organization_id: str,
    *,
    entity_type: str,
    entity_id: str,
) -> TapafSettlement | None:
    return db.scalar(
        select(TapafSettlement).where(
            TapafSettlement.organization_id == organization_id,
            TapafSettlement.entity_type == entity_type,
            TapafSettlement.entity_id == entity_id,
        )
    )


def list_settlements(db: Session, user: User, limit: int = 50) -> list[dict]:
    rows = list(
        db.scalars(
            select(TapafSettlement)
            .where(TapafSettlement.organization_id == user.organization_id)
            .order_by(TapafSettlement.created_at.desc())
            .limit(limit)
        )
    )
    return [settlement_view(row) for row in rows]
