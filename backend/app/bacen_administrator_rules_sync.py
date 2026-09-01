"""Sincronização diária (24h) de regulamento por administradora via Bacen SCR/Registrato."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.administrator_service import DEFAULT_RULES, parse_rules, update_administrator_rules
from app.bacen_scr_service import bacen_scr_client
from app.core.config import settings
from app.models import Administrator, Organization


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _rules_changed(before: dict, after: dict) -> bool:
    keys = (
        "max_asset_age_years",
        "allowed_categories",
        "min_commitment_margin",
        "bacen_scr_required",
        "products_enabled",
        "approval_rules",
        "credit_utilization_rules",
    )
    for key in keys:
        if before.get(key) != after.get(key):
            return True
    return False


def _sandbox_regulamento(admin: Administrator) -> dict:
    """Simula regulamento publicado no Bacen até credenciamento produtivo."""
    seed = int(hashlib.sha256(f"bacen-reg:{admin.document}:{admin.code}".encode()).hexdigest(), 16)
    max_age = 8 + (seed % 8)
    categories = ["REAL_ESTATE", "VEHICLE"] if seed % 5 else ["REAL_ESTATE"]
    products = list(DEFAULT_RULES["products_enabled"])
    if seed % 7 == 0:
        products = [p for p in products if p != "QUITCON"]
    margin = round(0.25 + (seed % 6) * 0.01, 2)
    return {
        "max_asset_age_years": max_age,
        "allowed_categories": categories,
        "min_commitment_margin": margin,
        "bacen_scr_required": True,
        "products_enabled": products,
        "approval_rules": {
            "max_ltv_percent": 35 + (seed % 6),
            "min_income_margin": margin,
            "scr_clear_required": True,
            "homologation_required": True,
        },
        "credit_utilization_rules": {
            "max_combined_quotas": 2 + (seed % 2),
            "same_administrator_required": True,
            "max_credit_per_operation_brl": 500_000 + (seed % 5) * 100_000,
        },
        "bacen_source": "SANDBOX",
        "bacen_protocol": f"REG-{hashlib.md5(admin.document.encode()).hexdigest()[:12].upper()}",
    }


def _fetch_production_regulamento(admin: Administrator) -> dict:
    cnpj = _digits(admin.document)
    if len(cnpj) != 14:
        raise ValueError(f"CNPJ inválido para administradora {admin.name}")
    url = settings.bacen_scr_api_url.rstrip("/") + f"/scr/administradora/{cnpj}/regulamento"
    headers = {
        "Authorization": f"Bearer {settings.bacen_scr_api_key}",
        "X-Institution-Code": settings.bacen_scr_institution_code or "",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=settings.integration_http_timeout_seconds) as client:
        response = client.get(url, headers=headers)
    if response.status_code >= 400:
        raise RuntimeError(f"Bacen retornou {response.status_code} para regulamento de {admin.code}")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("Resposta Bacen inválida para regulamento")
    regulamento = data.get("regulamento") or data.get("rules") or data
    if not isinstance(regulamento, dict):
        raise RuntimeError("Payload de regulamento Bacen inválido")
    regulamento["bacen_source"] = "PRODUCTION"
    regulamento["bacen_protocol"] = str(data.get("protocolo") or data.get("reference") or "")
    return regulamento


def fetch_bacen_regulamento(admin: Administrator) -> dict:
    if bacen_scr_client.is_configured():
        return _fetch_production_regulamento(admin)
    return _sandbox_regulamento(admin)


def sync_administrator_rules(db: Session, admin: Administrator) -> dict[str, Any]:
    fetched = fetch_bacen_regulamento(admin)
    before = parse_rules(admin.rules_json)
    merged = dict(before)
    for key, value in fetched.items():
        if key.startswith("bacen_") and key not in {"bacen_scr_required"}:
            merged[key] = value
        elif key in DEFAULT_RULES or key.endswith("_rules"):
            merged[key] = value
    changed = _rules_changed(before, merged)
    now = datetime.now(UTC)
    if changed:
        update_administrator_rules(db, admin, rules=merged, bump_version=True)
    merged["bacen_last_sync_at"] = now.isoformat()
    merged["bacen_sync_mode"] = "PRODUCTION" if bacen_scr_client.is_configured() else "SANDBOX"
    admin.rules_json = json.dumps(merged, ensure_ascii=False)
    admin.bacen_rules_synced_at = now
    return {
        "administrator_id": admin.id,
        "code": admin.code,
        "name": admin.name,
        "changed": changed,
        "rules_version": admin.bacen_rules_version,
        "synced_at": now.isoformat(),
        "mode": merged["bacen_sync_mode"],
        "protocol": merged.get("bacen_protocol"),
    }


def sync_all_administrator_rules(db: Session) -> dict[str, Any]:
    admins = list(db.scalars(select(Administrator).order_by(Administrator.name)))
    results = [sync_administrator_rules(db, admin) for admin in admins]
    changed_count = sum(1 for item in results if item["changed"])
    return {
        "total": len(results),
        "changed": changed_count,
        "mode": "PRODUCTION" if bacen_scr_client.is_configured() else "SANDBOX",
        "synced_at": datetime.now(UTC).isoformat(),
        "administrators": results,
    }


def rules_sync_due(admin: Administrator) -> bool:
    if not admin.bacen_rules_synced_at:
        return True
    synced = admin.bacen_rules_synced_at
    if synced.tzinfo is None:
        synced = synced.replace(tzinfo=UTC)
    return synced <= datetime.now(UTC) - timedelta(hours=settings.bacen_admin_rules_sync_hours)


def any_rules_sync_due(db: Session) -> bool:
    admins = list(db.scalars(select(Administrator)))
    return any(rules_sync_due(admin) for admin in admins)


def run_bacen_rules_sync_job(db: Session, *, organization_id: str | None = None) -> dict[str, Any]:
    result = sync_all_administrator_rules(db)
    result["organization_id"] = organization_id
    return result


def default_sync_organization_id(db: Session) -> str | None:
    org = db.scalar(select(Organization).order_by(Organization.created_at))
    return org.id if org else None
