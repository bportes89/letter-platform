"""CMS — páginas e templates de e-mail (legado texts / z_text)."""

from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.legacy_export_service import DEFAULT_SQL
from app.legacy_sql_parser import load_table
from app.models import CmsText, User

DEFAULT_LEGACY_SQL = DEFAULT_SQL


def decode_z_text_value(raw: str | None) -> str:
    if not raw:
        return ""
    text = str(raw).strip()
    try:
        decoded = base64.b64decode(text, validate=True)
        return decoded.decode("utf-8", errors="replace")
    except Exception:
        pass
    return html.unescape(text)


def text_view(row: CmsText) -> dict[str, Any]:
    return {
        "id": row.id,
        "legacy_id": row.legacy_id,
        "active": row.active,
        "kind": row.kind,
        "name_main": row.name_main,
        "subject": row.subject,
        "slug": row.slug,
        "body_html": row.body_html,
        "whatsapp": row.whatsapp,
        "sms": row.sms,
        "footer_place": row.footer_place,
        "sort_order": row.sort_order,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_texts(db: Session, user: User, *, kind: str | None = None) -> list[CmsText]:
    q = (
        select(CmsText)
        .where(CmsText.organization_id == user.organization_id)
        .order_by(CmsText.kind.asc(), CmsText.sort_order.asc(), CmsText.name_main.asc())
    )
    if kind:
        q = q.where(CmsText.kind == kind.upper())
    return list(db.scalars(q))


def get_text(db: Session, user: User, text_id: str) -> CmsText:
    row = db.scalar(
        select(CmsText).where(CmsText.id == text_id, CmsText.organization_id == user.organization_id)
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Texto não encontrado")
    return row


def get_public_page(db: Session, organization_id: str, slug: str) -> CmsText:
    row = db.scalar(
        select(CmsText).where(
            CmsText.organization_id == organization_id,
            CmsText.slug == slug,
            CmsText.kind == "PAGE",
            CmsText.active.is_(True),
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Página não encontrada")
    return row


def create_text(db: Session, user: User, payload: dict[str, Any]) -> CmsText:
    kind = str(payload.get("kind") or "PAGE").upper()
    if kind not in {"PAGE", "EMAIL"}:
        raise HTTPException(status_code=422, detail="kind deve ser PAGE ou EMAIL")
    slug = (payload.get("slug") or None) or None
    if slug:
        slug = str(slug).strip().lower()[:80]
    row = CmsText(
        organization_id=user.organization_id,
        legacy_id=payload.get("legacy_id"),
        active=bool(payload.get("active", True)),
        kind=kind,
        name_main=str(payload["name_main"]).strip(),
        subject=(payload.get("subject") or None),
        slug=slug,
        body_html=str(payload.get("body_html") or ""),
        whatsapp=payload.get("whatsapp"),
        sms=payload.get("sms"),
        footer_place=int(payload.get("footer_place") or 0),
        sort_order=int(payload.get("sort_order") or 999),
    )
    db.add(row)
    db.flush()
    return row


def update_text(db: Session, user: User, text_id: str, payload: dict[str, Any]) -> CmsText:
    row = get_text(db, user, text_id)
    for field in (
        "active",
        "name_main",
        "subject",
        "body_html",
        "whatsapp",
        "sms",
        "footer_place",
        "sort_order",
    ):
        if field in payload and payload[field] is not None:
            setattr(row, field, payload[field])
    if "slug" in payload:
        slug = payload["slug"]
        row.slug = str(slug).strip().lower()[:80] if slug else None
    if "kind" in payload and payload["kind"]:
        kind = str(payload["kind"]).upper()
        if kind in {"PAGE", "EMAIL"}:
            row.kind = kind
    db.flush()
    return row


def import_legacy_texts(
    db: Session,
    organization_id: str,
    *,
    sql_path: Path | None = None,
) -> dict[str, int]:
    path = sql_path or DEFAULT_LEGACY_SQL
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"SQL legado não encontrado: {path}")
    texts_rows = load_table(path, "texts")
    z_rows = load_table(path, "z_text")
    editor_by_id: dict[int, str] = {}
    for z in z_rows:
        model_key = str(z.get("model_") or "").lower()
        if "texts" not in model_key:
            continue
        if str(z.get("fields") or "") != "editor":
            continue
        try:
            legacy_id = int(z.get("id_") or 0)
        except (TypeError, ValueError):
            continue
        editor_by_id[legacy_id] = decode_z_text_value(z.get("value"))

    created = updated = 0
    for row in texts_rows:
        try:
            legacy_id = int(row.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if legacy_id <= 0:
            continue
        legacy_type = str(row.get("type") or "text").lower()
        kind = "PAGE" if legacy_type == "text" else "EMAIL"
        slug_raw = str(row.get("url") or "").strip().lower() or None
        existing = db.scalar(
            select(CmsText).where(
                CmsText.organization_id == organization_id,
                CmsText.legacy_id == legacy_id,
            )
        )
        body = editor_by_id.get(legacy_id, "")
        payload = {
            "name_main": str(row.get("name_main") or f"Legado {legacy_id}"),
            "subject": row.get("name"),
            "slug": slug_raw,
            "body_html": body,
            "whatsapp": row.get("whatsapp"),
            "sms": row.get("sms"),
            "footer_place": int(row.get("place") or 0),
            "sort_order": int(row.get("order") or 999),
            "active": bool(int(row.get("active") or 0)),
            "kind": kind,
        }
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(
                CmsText(
                    organization_id=organization_id,
                    legacy_id=legacy_id,
                    **payload,
                )
            )
            created += 1
    db.flush()
    return {"created": created, "updated": updated, "total_legacy": len(texts_rows)}
