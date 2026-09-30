"""CRUD de categorias/subcategorias de cotas (gestão legado quotas_categories)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.legacy_export_service import DEFAULT_SQL
from app.legacy_sql_parser import load_table
from app.models import QuotaCategory, User

DEFAULT_LEGACY_SQL = DEFAULT_SQL


def _asset_class_for_row(row: dict[str, Any], categories: dict[int, dict[str, Any]]) -> str | None:
    legacy_type = int(row.get("type") or 0)
    if legacy_type == 0:
        title = str(row.get("title_sub") or row.get("name") or "").lower()
        if "im" in title or "imovel" in title:
            return "REAL_ESTATE"
        if "ve" in title or "veiculo" in title:
            return "VEHICLE"
        if int(row.get("id") or 0) == 27:
            return "OTHER"
        return "OTHER"
    parent_id = int(row.get("subcategories") or 0)
    parent = categories.get(parent_id, {})
    return _asset_class_for_row(parent, categories) if parent else None


def asset_class_for_category(db: Session, category: QuotaCategory) -> str | None:
    if category.asset_class in {"REAL_ESTATE", "VEHICLE", "OTHER"}:
        return category.asset_class
    if category.legacy_type == 1 and category.parent_id:
        parent = db.get(QuotaCategory, category.parent_id)
        if parent and parent.asset_class:
            return parent.asset_class
    return None


def resolve_quota_asset_class(db: Session, organization_id: str, quota_category_id: str | None) -> str | None:
    if not quota_category_id:
        return None
    row = db.scalar(
        select(QuotaCategory).where(
            QuotaCategory.id == quota_category_id,
            QuotaCategory.organization_id == organization_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Subcategoria/categoria de cota não encontrada")
    asset = asset_class_for_category(db, row)
    if asset in {"REAL_ESTATE", "VEHICLE"}:
        return asset
    return None


def category_view(row: QuotaCategory) -> dict[str, Any]:
    return {
        "id": row.id,
        "legacy_id": row.legacy_id,
        "active": row.active,
        "name": row.name,
        "title_sub": row.title_sub,
        "legacy_type": row.legacy_type,
        "parent_id": row.parent_id,
        "sort_order": row.sort_order,
        "asset_class": row.asset_class,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_categories(db: Session, user: User, *, parents_only: bool = False) -> list[QuotaCategory]:
    q = (
        select(QuotaCategory)
        .where(QuotaCategory.organization_id == user.organization_id)
        .order_by(QuotaCategory.legacy_type.asc(), QuotaCategory.sort_order.asc(), QuotaCategory.name.asc())
    )
    if parents_only:
        q = q.where(QuotaCategory.legacy_type == 0)
    return list(db.scalars(q))


def get_category(db: Session, user: User, category_id: str) -> QuotaCategory:
    row = db.scalar(
        select(QuotaCategory).where(
            QuotaCategory.id == category_id,
            QuotaCategory.organization_id == user.organization_id,
        )
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")
    return row


def create_category(db: Session, user: User, payload: dict[str, Any]) -> QuotaCategory:
    legacy_type = int(payload.get("legacy_type", 0))
    parent_id = payload.get("parent_id")
    if legacy_type == 1 and not parent_id:
        raise HTTPException(status_code=400, detail="Subcategoria exige categoria pai")
    if legacy_type == 0:
        parent_id = None
    if parent_id:
        get_category(db, user, str(parent_id))
    row = QuotaCategory(
        organization_id=user.organization_id,
        legacy_id=payload.get("legacy_id"),
        active=bool(payload.get("active", True)),
        name=str(payload["name"]).strip(),
        title_sub=(payload.get("title_sub") or None),
        legacy_type=legacy_type,
        parent_id=parent_id,
        sort_order=int(payload.get("sort_order", 999)),
        asset_class=payload.get("asset_class"),
    )
    db.add(row)
    db.flush()
    return row


def update_category(db: Session, user: User, category_id: str, payload: dict[str, Any]) -> QuotaCategory:
    row = get_category(db, user, category_id)
    if "name" in payload and payload["name"] is not None:
        row.name = str(payload["name"]).strip()
    if "title_sub" in payload:
        row.title_sub = payload["title_sub"]
    if "active" in payload and payload["active"] is not None:
        row.active = bool(payload["active"])
    if "sort_order" in payload and payload["sort_order"] is not None:
        row.sort_order = int(payload["sort_order"])
    if "asset_class" in payload:
        row.asset_class = payload["asset_class"]
    if "parent_id" in payload:
        row.parent_id = payload["parent_id"]
    if "legacy_type" in payload and payload["legacy_type"] is not None:
        row.legacy_type = int(payload["legacy_type"])
    db.flush()
    return row


def import_legacy_categories(
    db: Session,
    organization_id: str,
    *,
    sql_path: Path | None = None,
) -> dict[str, int]:
    """Importa quotas_categories do dump SQL (idempotente por legacy_id)."""
    path = sql_path or DEFAULT_LEGACY_SQL
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Dump legado não encontrado: {path}")
    rows = load_table(path, "quotas_categories")
    by_id = {int(r["id"]): r for r in rows}
    existing = {
        int(r.legacy_id): r
        for r in db.scalars(
            select(QuotaCategory).where(
                QuotaCategory.organization_id == organization_id,
                QuotaCategory.legacy_id.isnot(None),
            )
        )
        if r.legacy_id is not None
    }
    legacy_to_uuid: dict[int, str] = {lid: row.id for lid, row in existing.items()}
    created = updated = 0

    parents = sorted([r for r in rows if int(r.get("type") or 0) == 0], key=lambda r: int(r.get("order") or 999))
    for row in parents:
        lid = int(row["id"])
        asset = _asset_class_for_row(row, by_id)
        if lid in existing:
            item = existing[lid]
            item.name = str(row.get("name") or item.name)
            item.title_sub = row.get("title_sub") or item.title_sub
            item.active = bool(int(row.get("active") or 0))
            item.sort_order = int(row.get("order") or item.sort_order)
            item.asset_class = asset
            updated += 1
        else:
            item = QuotaCategory(
                organization_id=organization_id,
                legacy_id=lid,
                active=bool(int(row.get("active") or 0)),
                name=str(row.get("name") or ""),
                title_sub=row.get("title_sub"),
                legacy_type=0,
                parent_id=None,
                sort_order=int(row.get("order") or 999),
                asset_class=asset,
            )
            db.add(item)
            db.flush()
            legacy_to_uuid[lid] = item.id
            existing[lid] = item
            created += 1

    children = sorted(
        [r for r in rows if int(r.get("type") or 0) == 1],
        key=lambda r: (int(r.get("subcategories") or 0), int(r.get("order") or 999)),
    )
    for row in children:
        lid = int(row["id"])
        parent_legacy = int(row.get("subcategories") or 0)
        parent_uuid = legacy_to_uuid.get(parent_legacy)
        asset = _asset_class_for_row(row, by_id)
        if lid in existing:
            item = existing[lid]
            item.name = str(row.get("name") or item.name)
            item.active = bool(int(row.get("active") or 0))
            item.sort_order = int(row.get("order") or item.sort_order)
            item.parent_id = parent_uuid
            item.asset_class = asset
            updated += 1
        else:
            item = QuotaCategory(
                organization_id=organization_id,
                legacy_id=lid,
                active=bool(int(row.get("active") or 0)),
                name=str(row.get("name") or ""),
                title_sub=None,
                legacy_type=1,
                parent_id=parent_uuid,
                sort_order=int(row.get("order") or 999),
                asset_class=asset,
            )
            db.add(item)
            db.flush()
            legacy_to_uuid[lid] = item.id
            existing[lid] = item
            created += 1

    return {"created": created, "updated": updated, "total_legacy": len(rows)}
