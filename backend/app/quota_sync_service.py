"""Sync de inventário de cotas a partir da API JSON dos fornecedores (porte Paulo).

Markup NÃO é embutido na entrada aqui — a Esteira 2 aplica markup/comissão na hora do match
via cadastro de Fornecedores (evita double-count vs Laravel, que somava 3% no sync).
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Administrator, Organization, Quota, QuotaSupplier, User
from app.quota_supplier_service import get_supplier, normalize_supplier_key
from app.services import money

SYNC_JSON = "JSON"
SYNC_SCRAPE = "SCRAPE"
SYNC_NONE = "NONE"
ORIGIN_JSON = "JSON"
ORIGIN_SCRAPE = "SCRAPE"
PROTECTED_STATUSES = {"RESERVED", "SOLD"}
HTTP_TIMEOUT = 30.0


def _slug(text: str | None) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", raw.lower())


def _api_price(raw: Any) -> Decimal:
    text = str(raw if raw is not None else "0").strip()
    if not text:
        return Decimal("0.00")
    if "," in text:
        cleaned = re.sub(r"[^0-9,]", "", text).replace(",", ".")
    else:
        cleaned = re.sub(r"[^0-9.\-]", "", text) or "0"
    try:
        return money(Decimal(cleaned))
    except InvalidOperation:
        return Decimal("0.00")


def _map_category(raw: Any) -> str:
    slug = _slug(str(raw or ""))
    if "veic" in slug or "auto" in slug or "moto" in slug or slug in {"vehicle", "veiculo"}:
        return "VEHICLE"
    return "REAL_ESTATE"


def _reserva_available(raw: Any) -> bool:
    return _slug(str(raw or "")) in {"reservar", "disponivel"}


_DUE_DATE_KEYS = ("date_vencimento", "data_vencimento", "installment_due_date")


def _due_date_keys_in_row(row: dict) -> bool:
    return any(key in row for key in _DUE_DATE_KEYS)


def _parse_due_date_value(raw: Any) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    iso = text[:10]
    try:
        return date.fromisoformat(iso)
    except ValueError:
        pass
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
    if match:
        day, month, year = (int(match.group(i)) for i in range(1, 4))
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def _installment_due_from_row(row: dict) -> date | None:
    for key in _DUE_DATE_KEYS:
        if key in row:
            return _parse_due_date_value(row.get(key))
    return None


def _default_administrator(db: Session) -> Administrator:
    admin = db.scalar(select(Administrator).order_by(Administrator.created_at).limit(1))
    if not admin:
        raise HTTPException(503, "Nenhuma administradora cadastrada para receber cotas sincronizadas.")
    return admin


def _resolve_administrator(db: Session, name: str | None, cache: dict[str, Administrator]) -> Administrator:
    key = _slug(name)
    if key and key in cache:
        return cache[key]
    if not cache:
        for row in db.scalars(select(Administrator)):
            cache[_slug(row.name)] = row
            cache[_slug(row.code)] = row
    if key and key in cache:
        return cache[key]
    if key:
        for slug, row in list(cache.items()):
            if key in slug or slug in key:
                return row
    return cache.get("_default") or _default_administrator(db)


def _fetch_json_payload(url: str) -> list[dict]:
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Falha ao consultar API do fornecedor: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(502, "Resposta JSON inválida da API do fornecedor.") from exc
    if isinstance(data, dict):
        for key in ("data", "cotas", "items", "results"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            raise HTTPException(502, "JSON do fornecedor não contém lista de cotas.")
    if not isinstance(data, list):
        raise HTTPException(502, "JSON do fornecedor deve ser uma lista de cotas.")
    return [row for row in data if isinstance(row, dict)]


def _group_code(source_key: str) -> str:
    return f"SYNC-{normalize_supplier_key(source_key)}"[:60]


def _apply_row(
    db: Session,
    *,
    organization_id: str,
    supplier: QuotaSupplier,
    row: dict,
    admin_cache: dict[str, Administrator],
    existing: dict[str, Quota],
    sync_origin: str = ORIGIN_JSON,
) -> str:
    external_ref = str(row.get("id") or row.get("external_id") or row.get("codigo") or "").strip()
    if not external_ref:
        return "skipped"

    credit = _api_price(row.get("valor_credito", row.get("credit_value", row.get("preco", 0))))
    entrada = _api_price(row.get("entrada", row.get("premium_value", row.get("preco_entrada", 0))))
    parcela = _api_price(row.get("valor_parcela", row.get("installment_value", row.get("preco_parcela", 0))))
    try:
        parcelas = int(row.get("parcelas") or row.get("remaining_installments") or 0)
    except (TypeError, ValueError):
        parcelas = 0
    adm_name = str(row.get("administradora") or row.get("administrator") or "").strip() or None
    category = _map_category(row.get("categoria") or row.get("category"))
    available = _reserva_available(row.get("reserva") or row.get("status") or "disponivel")
    administrator = _resolve_administrator(db, adm_name, admin_cache)
    now = datetime.now(UTC)
    due_date = _installment_due_from_row(row) if _due_date_keys_in_row(row) else None
    has_due_date = _due_date_keys_in_row(row)

    quota = existing.get(external_ref)
    if quota and quota.status in PROTECTED_STATUSES:
        return "protected"

    if quota:
        quota.administrator_id = administrator.id
        quota.category = category
        quota.credit_value = credit
        quota.outstanding_balance = credit
        quota.premium_value = entrada
        quota.installment_value = parcela
        quota.remaining_installments = parcelas or None
        quota.administrator_name_txt = adm_name
        quota.synced_at = now
        quota.sync_origin = sync_origin
        if has_due_date:
            quota.installment_due_date = due_date
        if quota.status not in PROTECTED_STATUSES:
            quota.status = "AVAILABLE" if available else "INACTIVE"
        return "updated"

    item = Quota(
        organization_id=organization_id,
        administrator_id=administrator.id,
        group_code=_group_code(supplier.source_key),
        quota_code=external_ref[:60],
        category=category,
        credit_value=credit,
        outstanding_balance=credit,
        premium_value=entrada,
        installment_value=parcela,
        remaining_installments=parcelas or None,
        installment_due_date=due_date if has_due_date else None,
        supplier_source=normalize_supplier_key(supplier.source_key),
        external_ref=external_ref,
        sync_origin=sync_origin,
        synced_at=now,
        administrator_name_txt=adm_name,
        status="AVAILABLE" if available else "INACTIVE",
    )
    db.add(item)
    existing[external_ref] = item
    return "created"


def sync_supplier_inventory(db: Session, user: User, supplier_id: str) -> dict:
    supplier = get_supplier(db, user, supplier_id)
    return _sync_one(db, organization_id=user.organization_id, supplier=supplier)


def sync_organization_inventory(db: Session, organization_id: str) -> dict:
    suppliers = list(
        db.scalars(
            select(QuotaSupplier).where(
                QuotaSupplier.organization_id == organization_id,
                QuotaSupplier.active.is_(True),
                QuotaSupplier.sync_mode.in_((SYNC_JSON, SYNC_SCRAPE)),
            ).order_by(QuotaSupplier.name)
        )
    )
    suppliers = [s for s in suppliers if (s.api_url or "").strip()]
    results: list[dict] = []
    totals = {"created": 0, "updated": 0, "deactivated": 0, "skipped": 0, "protected": 0, "failed": 0}
    for supplier in suppliers:
        try:
            row = _sync_one(db, organization_id=organization_id, supplier=supplier)
            results.append(row)
            for key in ("created", "updated", "deactivated", "skipped", "protected"):
                totals[key] += int(row.get(key) or 0)
            if row.get("status") == "ERROR":
                totals["failed"] += 1
        except HTTPException as exc:
            detail = {"supplier_id": supplier.id, "source_key": supplier.source_key, "status": "ERROR", "error": str(exc.detail)}
            _stamp_supplier(supplier, status="ERROR", detail=detail)
            results.append(detail)
            totals["failed"] += 1
    return {
        "organization_id": organization_id,
        "suppliers": len(suppliers),
        "results": results,
        **totals,
        "synced_at": datetime.now(UTC).isoformat(),
    }


def sync_organization_inventory_for_user(db: Session, user: User) -> dict:
    return sync_organization_inventory(db, user.organization_id)


def _stamp_supplier(supplier: QuotaSupplier, *, status: str, detail: dict) -> None:
    supplier.last_sync_at = datetime.now(UTC)
    supplier.last_sync_status = status
    supplier.last_sync_detail_json = json.dumps(detail, ensure_ascii=False)


def _sync_one(db: Session, *, organization_id: str, supplier: QuotaSupplier) -> dict:
    if supplier.sync_mode not in {SYNC_JSON, SYNC_SCRAPE}:
        raise HTTPException(422, "Fornecedor sem sync_mode=JSON ou SCRAPE.")
    url = (supplier.api_url or "").strip()
    if not url:
        raise HTTPException(422, "Configure api_url do fornecedor antes de sincronizar.")

    sync_origin = ORIGIN_SCRAPE if supplier.sync_mode == SYNC_SCRAPE else ORIGIN_JSON
    try:
        if supplier.sync_mode == SYNC_SCRAPE:
            from app.quota_scrape_service import fetch_scrape_payload

            payload = fetch_scrape_payload(supplier)
        else:
            payload = _fetch_json_payload(url)
    except HTTPException as exc:
        detail = {
            "supplier_id": supplier.id,
            "source_key": supplier.source_key,
            "status": "ERROR",
            "error": str(exc.detail),
            "created": 0,
            "updated": 0,
            "deactivated": 0,
        }
        _stamp_supplier(supplier, status="ERROR", detail=detail)
        db.flush()
        return detail

    source_key = normalize_supplier_key(supplier.source_key)
    existing_rows = list(
        db.scalars(
            select(Quota).where(
                Quota.organization_id == organization_id,
                Quota.supplier_source == source_key,
                Quota.sync_origin == sync_origin,
            )
        )
    )
    existing = {str(q.external_ref): q for q in existing_rows if q.external_ref}
    admin_cache: dict[str, Administrator] = {}
    seen: set[str] = set()
    created = updated = skipped = protected = 0

    for row in payload:
        external_ref = str(row.get("id") or row.get("external_id") or row.get("codigo") or "").strip()
        if external_ref:
            seen.add(external_ref)
        action = _apply_row(
            db,
            organization_id=organization_id,
            supplier=supplier,
            row=row,
            admin_cache=admin_cache,
            existing=existing,
            sync_origin=sync_origin,
        )
        if action == "created":
            created += 1
        elif action == "updated":
            updated += 1
        elif action == "protected":
            protected += 1
        else:
            skipped += 1

    deactivated = 0
    # Fail-safe: só desativa se a API devolveu itens (lista vazia não zera o estoque).
    if seen:
        for quota in existing_rows:
            if not quota.external_ref or quota.external_ref in seen:
                continue
            if quota.status in PROTECTED_STATUSES:
                protected += 1
                continue
            if quota.status != "INACTIVE":
                quota.status = "INACTIVE"
                quota.synced_at = datetime.now(UTC)
                deactivated += 1

    detail = {
        "supplier_id": supplier.id,
        "source_key": supplier.source_key,
        "status": "OK",
        "fetched": len(payload),
        "created": created,
        "updated": updated,
        "deactivated": deactivated,
        "skipped": skipped,
        "protected": protected,
    }
    _stamp_supplier(supplier, status="OK", detail=detail)
    db.flush()
    return detail


def default_sync_organization_id(db: Session) -> str:
    org = db.scalar(select(Organization).order_by(Organization.created_at).limit(1))
    if not org:
        raise HTTPException(503, "Nenhuma organização para sync de cotas.")
    return org.id
