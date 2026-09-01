"""Cadastro, homologação e regras versionadas de administradoras de consórcio."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Administrator, User

APPROVED_STATUSES = frozenset({
    "AUTHORIZED",
    "APPROVED",
    "ACTIVE",
    "APPROVED_MANUALLY",
})

DEFAULT_RULES = {
    "version": 1,
    "max_asset_age_years": 15,
    "allowed_categories": ["REAL_ESTATE", "VEHICLE"],
    "min_commitment_margin": 0.30,
    "bacen_scr_required": True,
    "products_enabled": ["SDC", "QUITCON", "MARKETPLACE"],
}


def normalize_admin_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def slug_code(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper()).strip("_")[:40]


def parse_rules(raw: str | None) -> dict:
    if not raw:
        return dict(DEFAULT_RULES)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return dict(DEFAULT_RULES)
    merged = dict(DEFAULT_RULES)
    merged.update(data if isinstance(data, dict) else {})
    return merged


def administrator_view(admin: Administrator) -> dict:
    rules = parse_rules(admin.rules_json)
    return {
        "id": admin.id,
        "code": admin.code,
        "name": admin.name,
        "document": admin.document,
        "authorization_status": admin.authorization_status,
        "rules": rules,
        "rules_version": admin.bacen_rules_version,
        "homologated_at": admin.homologated_at,
        "homologated_by_id": admin.homologated_by_id,
        "homologation_notes": admin.homologation_notes,
        "created_at": admin.created_at,
        "updated_at": admin.updated_at,
    }


def list_administrators(db: Session) -> list[Administrator]:
    return list(db.scalars(select(Administrator).order_by(Administrator.name)))


def homologated_administrators(db: Session) -> list[Administrator]:
    rows = list_administrators(db)
    return [a for a in rows if a.authorization_status in APPROVED_STATUSES]


def homologated_codes(db: Session) -> list[str]:
    codes: list[str] = []
    for admin in homologated_administrators(db):
        if admin.code:
            codes.append(admin.code.upper())
        else:
            codes.append(slug_code(admin.name))
    return codes


def homologated_name_keys(db: Session) -> list[str]:
    return [normalize_admin_key(a.name) for a in homologated_administrators(db)]


def create_administrator(db: Session, *, name: str, document: str, code: str | None = None) -> Administrator:
    normalized_code = (code or slug_code(name)).upper()
    if db.scalar(select(Administrator).where(Administrator.code == normalized_code)):
        raise HTTPException(status_code=409, detail="Código de administradora já cadastrado")
    if db.scalar(select(Administrator).where(Administrator.document == document)):
        raise HTTPException(status_code=409, detail="CNPJ já cadastrado")
    admin = Administrator(
        name=name.strip(),
        document=document.strip(),
        code=normalized_code,
        authorization_status="PENDING_REVIEW",
        rules_json=json.dumps(DEFAULT_RULES, ensure_ascii=False),
        bacen_rules_version=1,
    )
    db.add(admin)
    db.flush()
    return admin


def update_administrator_rules(
    db: Session,
    admin: Administrator,
    *,
    rules: dict,
    bump_version: bool = True,
) -> Administrator:
    current = parse_rules(admin.rules_json)
    current.update(rules)
    if bump_version:
        admin.bacen_rules_version = int(admin.bacen_rules_version or 1) + 1
        current["version"] = admin.bacen_rules_version
    admin.rules_json = json.dumps(current, ensure_ascii=False)
    return admin


def homologate_administrator(
    db: Session,
    actor: User,
    admin: Administrator,
    *,
    approved: bool,
    notes: str | None = None,
) -> Administrator:
    if approved:
        admin.authorization_status = "AUTHORIZED"
        admin.homologated_at = datetime.now(UTC)
        admin.homologated_by_id = actor.id
    else:
        admin.authorization_status = "REJECTED"
        admin.homologated_at = None
        admin.homologated_by_id = actor.id
    admin.homologation_notes = notes
    admin.bacen_rules_version = int(admin.bacen_rules_version or 1) + 1
    rules = parse_rules(admin.rules_json)
    rules["version"] = admin.bacen_rules_version
    rules["homologated_at"] = admin.homologated_at.isoformat() if admin.homologated_at else None
    admin.rules_json = json.dumps(rules, ensure_ascii=False)
    return admin


def is_administrator_approved(db: Session, administrator_name: str) -> bool:
    key = normalize_admin_key(administrator_name)
    for admin in homologated_administrators(db):
        if normalize_admin_key(admin.name) == key:
            return True
        if admin.code and normalize_admin_key(admin.code) == key:
            return True
    return False
