"""Migração de dados do sistema legado — validação dry-run e apply incremental."""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Administrator,
    Branch,
    Lead,
    LegacyIdMap,
    LegacyMigrationRun,
    Organization,
    Proposal,
    Quota,
    Role,
    User,
)

IMPLEMENTED_APPLY_ENTITIES = frozenset(
    {"organizations", "branches", "administrators", "users", "leads", "quotas", "proposals"}
)
MIGRATION_APPLY_BATCH_SIZE = 500

LEGACY_STATUS_TO_PROPOSAL = {
    2: "SUBMITTED",
    10: "DRAFT",
    11: "CANCELLED",
}

MIGRATION_ENTITY_ORDER: tuple[str, ...] = (
    "organizations",
    "branches",
    "administrators",
    "users",
    "network_nodes",
    "leads",
    "quotas",
    "proposals",
)

ENTITY_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "organizations": ("legacy_id", "name"),
    "branches": ("legacy_id", "name", "code"),
    "administrators": ("legacy_id", "name", "code", "document"),
    "users": ("legacy_id", "name", "email", "role"),
    "network_nodes": ("legacy_id", "user_legacy_id"),
    "leads": ("legacy_id", "name", "phone"),
    "quotas": ("legacy_id", "administrator_legacy_id", "group_code", "quota_code"),
    "proposals": ("legacy_id", "product"),
}

ROLE_VALUES = {item.value for item in Role}

REF_FIELD_TO_ENTITY: dict[str, str] = {
    "organization_legacy_id": "organizations",
    "branch_legacy_id": "branches",
    "sponsor_legacy_id": "users",
    "user_legacy_id": "users",
    "sponsor_user_legacy_id": "users",
    "administrator_legacy_id": "administrators",
    "lead_legacy_id": "leads",
    "owner_user_legacy_id": "users",
    "seller_user_legacy_id": "users",
}


@dataclass
class MigrationIssue:
    level: str
    entity_type: str
    legacy_id: str | None
    message: str


@dataclass
class MigrationReport:
    legacy_source: str
    mode: str
    ready: bool
    entity_counts: dict[str, int] = field(default_factory=dict)
    issues: list[MigrationIssue] = field(default_factory=list)
    warnings: list[MigrationIssue] = field(default_factory=list)
    planned_order: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        blockers = [i for i in self.issues if i.level == "ERROR"]
        return {
            "legacy_source": self.legacy_source,
            "mode": self.mode,
            "ready": self.ready and not blockers,
            "entity_counts": self.entity_counts,
            "planned_order": self.planned_order,
            "issue_count": len(self.issues),
            "warning_count": len(self.warnings),
            "issues": [issue.__dict__ for issue in self.issues],
            "warnings": [issue.__dict__ for issue in self.warnings],
        }


def normalize_bundle(raw: dict[str, Any]) -> dict[str, Any]:
    if "entities" not in raw:
        raise ValueError("Payload deve conter a chave 'entities'")
    source = str(raw.get("legacy_source") or raw.get("source_label") or "legacy").strip()
    if not source:
        raise ValueError("legacy_source é obrigatório")
    entities = raw["entities"]
    if not isinstance(entities, dict):
        raise ValueError("entities deve ser um objeto")
    normalized: dict[str, list[dict[str, Any]]] = {}
    for key, rows in entities.items():
        if rows is None:
            normalized[key] = []
            continue
        if not isinstance(rows, list):
            raise ValueError(f"entities.{key} deve ser uma lista")
        normalized[key] = [row for row in rows if isinstance(row, dict)]
    return {"legacy_source": source, "entities": normalized}


def _legacy_key(entity_type: str, legacy_id: str) -> str:
    return f"{entity_type}:{legacy_id}"


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def validate_bundle(db: Session, organization_id: str, bundle: dict[str, Any]) -> MigrationReport:
    source = bundle["legacy_source"]
    entities = bundle["entities"]
    report = MigrationReport(
        legacy_source=source,
        mode="DRY_RUN",
        ready=True,
        planned_order=[name for name in MIGRATION_ENTITY_ORDER if entities.get(name)],
    )

    for entity_type in MIGRATION_ENTITY_ORDER:
        rows = entities.get(entity_type) or []
        report.entity_counts[entity_type] = len(rows)
        required = ENTITY_REQUIRED_FIELDS.get(entity_type, ("legacy_id",))
        seen: set[str] = set()
        for row in rows:
            legacy_id = str(row.get("legacy_id") or "").strip()
            if not legacy_id:
                report.issues.append(MigrationIssue("ERROR", entity_type, None, "legacy_id ausente"))
                report.ready = False
                continue
            if legacy_id in seen:
                report.issues.append(
                    MigrationIssue("ERROR", entity_type, legacy_id, "legacy_id duplicado no lote")
                )
                report.ready = False
            seen.add(legacy_id)
            for field_name in required:
                if not str(row.get(field_name) or "").strip():
                    report.issues.append(
                        MigrationIssue("ERROR", entity_type, legacy_id, f"Campo obrigatório ausente: {field_name}")
                    )
                    report.ready = False
            if entity_type == "users":
                role = str(row.get("role") or "").strip().upper()
                if role not in ROLE_VALUES:
                    report.issues.append(
                        MigrationIssue("ERROR", entity_type, legacy_id, f"Role inválida: {role or '(vazia)'}")
                    )
                    report.ready = False
                email = str(row.get("email") or "").strip().lower()
                if email and db.scalar(select(User.id).where(User.email == email)):
                    report.issues.append(
                        MigrationIssue("ERROR", entity_type, legacy_id, f"E-mail já existe na plataforma: {email}")
                    )
                    report.ready = False
                document = _digits(row.get("document"))
                if document and db.scalar(select(User.id).where(User.document == document)):
                    report.issues.append(
                        MigrationIssue(
                            "ERROR",
                            entity_type,
                            legacy_id,
                            f"Documento já existe na plataforma: {document}",
                        )
                    )
                    report.ready = False
            if entity_type == "organizations":
                document = _digits(row.get("document"))
                if document and db.scalar(select(Organization.id).where(Organization.document == document)):
                    report.warnings.append(
                        MigrationIssue(
                            "WARNING",
                            entity_type,
                            legacy_id,
                            f"CNPJ já cadastrado — será reutilizado via legacy_id_map: {document}",
                        )
                    )
            if entity_type == "administrators":
                code = str(row.get("code") or "").strip().upper()
                if code and db.scalar(select(Administrator.id).where(Administrator.code == code)):
                    report.warnings.append(
                        MigrationIssue(
                            "WARNING",
                            entity_type,
                            legacy_id,
                            f"Código de administradora já existe: {code}",
                        )
                    )

    index: set[str] = set()
    for entity_type, rows in entities.items():
        for row in rows:
            legacy_id = str(row.get("legacy_id") or "").strip()
            if legacy_id:
                index.add(_legacy_key(entity_type, legacy_id))

    existing_maps = list(
        db.scalars(
            select(LegacyIdMap).where(
                LegacyIdMap.organization_id == organization_id,
                LegacyIdMap.legacy_source == source,
            )
        )
    )
    mapped_keys = {_legacy_key(item.entity_type, item.legacy_id) for item in existing_maps}

    def require_ref(entity_type: str, ref_field: str, row: dict[str, Any]) -> None:
        legacy_id = str(row.get("legacy_id") or "")
        ref = str(row.get(ref_field) or "").strip()
        if not ref:
            report.issues.append(
                MigrationIssue("ERROR", entity_type, legacy_id, f"Referência ausente: {ref_field}")
            )
            report.ready = False
            return
        bucket = REF_FIELD_TO_ENTITY.get(ref_field)
        if not bucket:
            return
        key = _legacy_key(bucket, ref)
        if key not in index and key not in mapped_keys:
            report.issues.append(
                MigrationIssue(
                    "ERROR",
                    entity_type,
                    legacy_id,
                    f"Referência legada não encontrada: {ref_field}={ref}",
                )
            )
            report.ready = False

    for row in entities.get("branches") or []:
        if row.get("organization_legacy_id"):
            require_ref("branches", "organization_legacy_id", row)
    for row in entities.get("users") or []:
        if row.get("branch_legacy_id"):
            require_ref("users", "branch_legacy_id", row)
        if row.get("sponsor_legacy_id"):
            require_ref("users", "sponsor_legacy_id", row)
    for row in entities.get("network_nodes") or []:
        require_ref("network_nodes", "user_legacy_id", row)
        if row.get("sponsor_user_legacy_id"):
            require_ref("network_nodes", "sponsor_user_legacy_id", row)
    for row in entities.get("quotas") or []:
        require_ref("quotas", "administrator_legacy_id", row)
        seller_legacy = str(row.get("seller_user_legacy_id") or "").strip()
        if seller_legacy:
            key = _legacy_key("users", seller_legacy)
            if key not in index and key not in mapped_keys:
                report.warnings.append(
                    MigrationIssue(
                        "WARNING",
                        "quotas",
                        str(row.get("legacy_id") or ""),
                        f"Fornecedor legado não exportado — cota sem seller: {seller_legacy}",
                    )
                )
        try:
            if Decimal(str(row.get("credit_value") or "0")) <= 0:
                report.warnings.append(
                    MigrationIssue(
                        "WARNING",
                        "quotas",
                        str(row.get("legacy_id") or ""),
                        "credit_value inválido — será ajustado para 1.00 na carga",
                    )
                )
        except (InvalidOperation, ValueError):
            report.warnings.append(
                MigrationIssue(
                    "WARNING",
                    "quotas",
                    str(row.get("legacy_id") or ""),
                    "credit_value inválido — será ajustado para 1.00 na carga",
                )
            )
    for row in entities.get("leads") or []:
        owner_legacy = str(row.get("owner_user_legacy_id") or "").strip()
        if owner_legacy:
            key = _legacy_key("users", owner_legacy)
            if key not in index and key not in mapped_keys:
                report.warnings.append(
                    MigrationIssue(
                        "WARNING",
                        "leads",
                        str(row.get("legacy_id") or ""),
                        f"Parceiro legado não exportado — owner será o admin migrador: {owner_legacy}",
                    )
                )
    for row in entities.get("proposals") or []:
        if row.get("lead_legacy_id"):
            require_ref("proposals", "lead_legacy_id", row)
        try:
            if Decimal(str(row.get("requested_amount") or "0")) <= 0:
                report.warnings.append(
                    MigrationIssue(
                        "WARNING",
                        "proposals",
                        str(row.get("legacy_id") or ""),
                        "requested_amount inválido — será ajustado para 1.00 na carga",
                    )
                )
        except (InvalidOperation, ValueError):
            report.warnings.append(
                MigrationIssue(
                    "WARNING",
                    "proposals",
                    str(row.get("legacy_id") or ""),
                    "requested_amount inválido — será ajustado para 1.00 na carga",
                )
            )

    for entity_type in entities:
        if entity_type not in MIGRATION_ENTITY_ORDER:
            report.warnings.append(
                MigrationIssue(
                    "WARNING",
                    entity_type,
                    None,
                    "Tipo de entidade desconhecido — será ignorado na carga inicial",
                )
            )

    unsupported = [
        name
        for name in MIGRATION_ENTITY_ORDER
        if name not in IMPLEMENTED_APPLY_ENTITIES and entities.get(name)
    ]
    if unsupported:
        report.warnings.append(
            MigrationIssue(
                "WARNING",
                "migration",
                None,
                f"Apply ainda não implementado para: {', '.join(unsupported)} — use dry-run para validar",
            )
        )

    return report


def _resolve_mapped_id(
    db: Session,
    *,
    organization_id: str,
    legacy_source: str,
    entity_type: str,
    legacy_id: str,
    cache: dict[str, str],
) -> str | None:
    key = _legacy_key(entity_type, legacy_id)
    if key in cache:
        return cache[key]
    mapped = db.scalar(
        select(LegacyIdMap).where(
            LegacyIdMap.organization_id == organization_id,
            LegacyIdMap.legacy_source == legacy_source,
            LegacyIdMap.entity_type == entity_type,
            LegacyIdMap.legacy_id == legacy_id,
        )
    )
    if mapped:
        cache[key] = mapped.new_id
        return mapped.new_id
    return None


def _remember_map(
    db: Session,
    *,
    organization_id: str,
    legacy_source: str,
    entity_type: str,
    legacy_id: str,
    new_id: str,
    migration_run_id: str,
    payload: dict[str, Any] | None,
    cache: dict[str, str],
) -> None:
    item = LegacyIdMap(
        organization_id=organization_id,
        migration_run_id=migration_run_id,
        legacy_source=legacy_source,
        entity_type=entity_type,
        legacy_id=legacy_id,
        new_id=new_id,
        payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
    )
    db.add(item)
    cache[_legacy_key(entity_type, legacy_id)] = new_id


def _migration_password_hash() -> str:
    return hash_password(secrets.token_urlsafe(24))


def _resolve_branch_id(
    db: Session,
    *,
    actor: User,
    row: dict[str, Any],
    organization_id: str,
    legacy_source: str,
    cache: dict[str, str],
) -> str | None:
    branch_legacy = str(row.get("branch_legacy_id") or "").strip()
    if branch_legacy:
        resolved = _resolve_mapped_id(
            db,
            organization_id=organization_id,
            legacy_source=legacy_source,
            entity_type="branches",
            legacy_id=branch_legacy,
            cache=cache,
        )
        if resolved:
            return resolved
    return actor.branch_id


def _apply_administrators(
    db: Session,
    *,
    actor: User,
    rows: list[dict[str, Any]],
    legacy_source: str,
    migration_run_id: str,
    cache: dict[str, str],
    created: dict[str, int],
    reused: dict[str, int],
) -> None:
    for row in rows:
        legacy_id = str(row["legacy_id"])
        if _resolve_mapped_id(
            db,
            organization_id=actor.organization_id,
            legacy_source=legacy_source,
            entity_type="administrators",
            legacy_id=legacy_id,
            cache=cache,
        ):
            reused["administrators"] = reused.get("administrators", 0) + 1
            continue

        code = str(row.get("code") or "").strip().upper() or None
        name = str(row.get("name") or "").strip()
        document = _digits(row.get("document")) or f"99{int(legacy_id):012d}"[:14]

        existing = None
        if code:
            existing = db.scalar(select(Administrator).where(Administrator.code == code))
        if not existing:
            existing = db.scalar(select(Administrator).where(Administrator.document == document))
        if not existing:
            existing = db.scalar(select(Administrator).where(Administrator.name == name))

        if existing:
            reused["administrators"] = reused.get("administrators", 0) + 1
            target = existing
        else:
            target = Administrator(
                name=name,
                code=code,
                document=document,
                authorization_status="AUTHORIZED",
            )
            db.add(target)
            db.flush()
            created["administrators"] = created.get("administrators", 0) + 1

        _remember_map(
            db,
            organization_id=actor.organization_id,
            legacy_source=legacy_source,
            entity_type="administrators",
            legacy_id=legacy_id,
            new_id=target.id,
            migration_run_id=migration_run_id,
            payload=row,
            cache=cache,
        )


def _apply_users(
    db: Session,
    *,
    actor: User,
    rows: list[dict[str, Any]],
    legacy_source: str,
    migration_run_id: str,
    cache: dict[str, str],
    created: dict[str, int],
    reused: dict[str, int],
) -> None:
    pending_sponsors: list[tuple[str, str]] = []

    for row in rows:
        legacy_id = str(row["legacy_id"])
        if _resolve_mapped_id(
            db,
            organization_id=actor.organization_id,
            legacy_source=legacy_source,
            entity_type="users",
            legacy_id=legacy_id,
            cache=cache,
        ):
            reused["users"] = reused.get("users", 0) + 1
            continue

        email = str(row.get("email") or "").strip().lower()
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            reused["users"] = reused.get("users", 0) + 1
            _remember_map(
                db,
                organization_id=actor.organization_id,
                legacy_source=legacy_source,
                entity_type="users",
                legacy_id=legacy_id,
                new_id=existing.id,
                migration_run_id=migration_run_id,
                payload=row,
                cache=cache,
            )
            continue

        document = _digits(row.get("document")) or None
        if document and db.scalar(select(User.id).where(User.document == document)):
            document = None

        role = Role[str(row.get("role")).strip().upper()]
        item = User(
            organization_id=actor.organization_id,
            branch_id=_resolve_branch_id(
                db,
                actor=actor,
                row=row,
                organization_id=actor.organization_id,
                legacy_source=legacy_source,
                cache=cache,
            ),
            name=str(row.get("name") or "").strip(),
            email=email,
            document=document,
            phone=(str(row.get("phone")).strip() if row.get("phone") else None),
            company_name=(str(row.get("company_name")).strip() if row.get("company_name") else None),
            company_cnpj=_digits(row.get("company_cnpj")) or None,
            password_hash=_migration_password_hash(),
            role=role,
            active=bool(row.get("active", True)),
        )
        db.add(item)
        db.flush()
        _remember_map(
            db,
            organization_id=actor.organization_id,
            legacy_source=legacy_source,
            entity_type="users",
            legacy_id=legacy_id,
            new_id=item.id,
            migration_run_id=migration_run_id,
            payload=row,
            cache=cache,
        )
        created["users"] = created.get("users", 0) + 1

        sponsor_legacy = str(row.get("sponsor_legacy_id") or "").strip()
        if sponsor_legacy:
            pending_sponsors.append((item.id, sponsor_legacy))

    for user_id, sponsor_legacy in pending_sponsors:
        sponsor_id = _resolve_mapped_id(
            db,
            organization_id=actor.organization_id,
            legacy_source=legacy_source,
            entity_type="users",
            legacy_id=sponsor_legacy,
            cache=cache,
        )
        if not sponsor_id:
            continue
        target = db.get(User, user_id)
        if target and target.referred_by_user_id is None:
            target.referred_by_user_id = sponsor_id


def _normalize_phone(value: Any) -> str:
    phone = _digits(value)
    return (phone or "00000000000")[:30]


def _apply_leads(
    db: Session,
    *,
    actor: User,
    rows: list[dict[str, Any]],
    legacy_source: str,
    migration_run_id: str,
    cache: dict[str, str],
    created: dict[str, int],
    reused: dict[str, int],
    skipped: dict[str, int],
) -> None:
    pending: list[tuple[str, dict[str, Any], Lead]] = []

    def flush_batch() -> None:
        nonlocal pending
        if not pending:
            return
        db.flush()
        for legacy_id, row, item in pending:
            _remember_map(
                db,
                organization_id=actor.organization_id,
                legacy_source=legacy_source,
                entity_type="leads",
                legacy_id=legacy_id,
                new_id=item.id,
                migration_run_id=migration_run_id,
                payload=row,
                cache=cache,
            )
            created["leads"] = created.get("leads", 0) + 1
        pending.clear()

    for row in rows:
        legacy_id = str(row["legacy_id"])
        if _resolve_mapped_id(
            db,
            organization_id=actor.organization_id,
            legacy_source=legacy_source,
            entity_type="leads",
            legacy_id=legacy_id,
            cache=cache,
        ):
            reused["leads"] = reused.get("leads", 0) + 1
            continue

        owner_id = actor.id
        owner_legacy = str(row.get("owner_user_legacy_id") or "").strip()
        if owner_legacy:
            resolved_owner = _resolve_mapped_id(
                db,
                organization_id=actor.organization_id,
                legacy_source=legacy_source,
                entity_type="users",
                legacy_id=owner_legacy,
                cache=cache,
            )
            if resolved_owner:
                owner_id = resolved_owner
            else:
                skipped["leads_missing_owner"] = skipped.get("leads_missing_owner", 0) + 1

        status = str(row.get("status") or "NEW").strip().upper() or "NEW"
        product = str(row.get("product_interest") or "MARKETPLACE").strip().upper() or "MARKETPLACE"
        document = _digits(row.get("legacy_document") or row.get("document")) or None

        item = Lead(
            organization_id=actor.organization_id,
            owner_id=owner_id,
            name=str(row.get("name") or "").strip() or f"Lead {legacy_id}",
            document=document,
            phone=_normalize_phone(row.get("phone")),
            product_interest=product,
            status=status,
            source="LEGACY_MIGRATION",
        )
        db.add(item)
        pending.append((legacy_id, row, item))
        if len(pending) >= MIGRATION_APPLY_BATCH_SIZE:
            flush_batch()

    flush_batch()


def _parse_decimal(value: Any, *, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _parse_date_value(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _apply_quotas(
    db: Session,
    *,
    actor: User,
    rows: list[dict[str, Any]],
    legacy_source: str,
    migration_run_id: str,
    cache: dict[str, str],
    created: dict[str, int],
    reused: dict[str, int],
    skipped: dict[str, int],
) -> None:
    pending: list[tuple[str, dict[str, Any], Quota]] = []

    def flush_batch() -> None:
        nonlocal pending
        if not pending:
            return
        db.flush()
        for legacy_id, row, item in pending:
            _remember_map(
                db,
                organization_id=actor.organization_id,
                legacy_source=legacy_source,
                entity_type="quotas",
                legacy_id=legacy_id,
                new_id=item.id,
                migration_run_id=migration_run_id,
                payload=row,
                cache=cache,
            )
            created["quotas"] = created.get("quotas", 0) + 1
        pending.clear()

    for row in rows:
        legacy_id = str(row["legacy_id"])
        if _resolve_mapped_id(
            db,
            organization_id=actor.organization_id,
            legacy_source=legacy_source,
            entity_type="quotas",
            legacy_id=legacy_id,
            cache=cache,
        ):
            reused["quotas"] = reused.get("quotas", 0) + 1
            continue

        admin_legacy = str(row.get("administrator_legacy_id") or "").strip()
        admin_id = _resolve_mapped_id(
            db,
            organization_id=actor.organization_id,
            legacy_source=legacy_source,
            entity_type="administrators",
            legacy_id=admin_legacy,
            cache=cache,
        )
        if not admin_id:
            skipped["quotas_missing_administrator"] = skipped.get("quotas_missing_administrator", 0) + 1
            continue

        group_code = str(row.get("group_code") or "").strip()[:60]
        quota_code = str(row.get("quota_code") or "").strip()[:60]
        if not group_code or not quota_code:
            skipped["quotas_missing_codes"] = skipped.get("quotas_missing_codes", 0) + 1
            continue

        existing_quota = db.scalar(
            select(Quota).where(
                Quota.administrator_id == admin_id,
                Quota.group_code == group_code,
                Quota.quota_code == quota_code,
            )
        )
        if existing_quota:
            reused["quotas"] = reused.get("quotas", 0) + 1
            _remember_map(
                db,
                organization_id=actor.organization_id,
                legacy_source=legacy_source,
                entity_type="quotas",
                legacy_id=legacy_id,
                new_id=existing_quota.id,
                migration_run_id=migration_run_id,
                payload=row,
                cache=cache,
            )
            continue

        seller_id = None
        seller_legacy = str(row.get("seller_user_legacy_id") or "").strip()
        if seller_legacy:
            seller_id = _resolve_mapped_id(
                db,
                organization_id=actor.organization_id,
                legacy_source=legacy_source,
                entity_type="users",
                legacy_id=seller_legacy,
                cache=cache,
            )
            if not seller_id:
                skipped["quotas_missing_seller"] = skipped.get("quotas_missing_seller", 0) + 1

        credit_value = _parse_decimal(row.get("credit_value"))
        if credit_value <= 0:
            credit_value = Decimal("1")

        category = str(row.get("category") or "VEHICLE").strip().upper()
        if category not in {"REAL_ESTATE", "VEHICLE"}:
            category = "VEHICLE"

        status = str(row.get("status") or "AVAILABLE").strip().upper() or "AVAILABLE"

        item = Quota(
            organization_id=actor.organization_id,
            administrator_id=admin_id,
            seller_id=seller_id,
            group_code=group_code,
            quota_code=quota_code,
            category=category,
            credit_value=credit_value,
            outstanding_balance=_parse_decimal(row.get("outstanding_balance")),
            premium_value=_parse_decimal(row.get("premium_value")),
            installment_due_date=_parse_date_value(row.get("installment_due_date")),
            status=status,
        )
        db.add(item)
        pending.append((legacy_id, row, item))
        if len(pending) >= MIGRATION_APPLY_BATCH_SIZE:
            flush_batch()

    flush_batch()


def _proposal_status_from_legacy(row: dict[str, Any]) -> str:
    status_code = row.get("legacy_status_code")
    if status_code is not None:
        try:
            mapped = LEGACY_STATUS_TO_PROPOSAL.get(int(status_code))
            if mapped:
                return mapped
        except (TypeError, ValueError):
            pass
    explicit = str(row.get("status") or "").strip().upper()
    return explicit or "DRAFT"


def _apply_proposals(
    db: Session,
    *,
    actor: User,
    rows: list[dict[str, Any]],
    legacy_source: str,
    migration_run_id: str,
    cache: dict[str, str],
    created: dict[str, int],
    reused: dict[str, int],
    skipped: dict[str, int],
) -> None:
    pending: list[tuple[str, dict[str, Any], Proposal]] = []

    def flush_batch() -> None:
        nonlocal pending
        if not pending:
            return
        db.flush()
        for legacy_id, row, item in pending:
            _remember_map(
                db,
                organization_id=actor.organization_id,
                legacy_source=legacy_source,
                entity_type="proposals",
                legacy_id=legacy_id,
                new_id=item.id,
                migration_run_id=migration_run_id,
                payload=row,
                cache=cache,
            )
            created["proposals"] = created.get("proposals", 0) + 1
        pending.clear()

    for row in rows:
        legacy_id = str(row["legacy_id"])
        if _resolve_mapped_id(
            db,
            organization_id=actor.organization_id,
            legacy_source=legacy_source,
            entity_type="proposals",
            legacy_id=legacy_id,
            cache=cache,
        ):
            reused["proposals"] = reused.get("proposals", 0) + 1
            continue

        lead_legacy = str(row.get("lead_legacy_id") or "").strip()
        if not lead_legacy:
            skipped["proposals_missing_lead"] = skipped.get("proposals_missing_lead", 0) + 1
            continue

        lead_id = _resolve_mapped_id(
            db,
            organization_id=actor.organization_id,
            legacy_source=legacy_source,
            entity_type="leads",
            legacy_id=lead_legacy,
            cache=cache,
        )
        if not lead_id:
            skipped["proposals_missing_lead"] = skipped.get("proposals_missing_lead", 0) + 1
            continue

        requested_amount = _parse_decimal(row.get("requested_amount"))
        if requested_amount <= 0:
            requested_amount = Decimal("1")

        product = str(row.get("product") or "MARKETPLACE").strip().upper() or "MARKETPLACE"
        terms = {
            "legacy_migration": True,
            "legacy_id": legacy_id,
            "legacy_status_code": row.get("legacy_status_code"),
        }

        item = Proposal(
            organization_id=actor.organization_id,
            lead_id=lead_id,
            product=product,
            requested_amount=requested_amount,
            status=_proposal_status_from_legacy(row),
            terms_json=json.dumps(terms, ensure_ascii=False),
        )
        db.add(item)
        pending.append((legacy_id, row, item))
        if len(pending) >= MIGRATION_APPLY_BATCH_SIZE:
            flush_batch()

    flush_batch()


def apply_bundle(
    db: Session,
    user,
    bundle: dict[str, Any],
    *,
    dry_run: bool = True,
) -> tuple[LegacyMigrationRun, MigrationReport]:
    bundle = normalize_bundle(bundle)
    report = validate_bundle(db, user.organization_id, bundle)
    blockers = [issue for issue in report.issues if issue.level == "ERROR"]
    mode = "DRY_RUN" if dry_run else "APPLY"
    run = LegacyMigrationRun(
        organization_id=user.organization_id,
        legacy_source=bundle["legacy_source"],
        mode=mode,
        status="RUNNING",
        started_by_id=user.id,
        summary_json="{}",
    )
    db.add(run)
    db.flush()

    if blockers:
        run.status = "FAILED"
        run.error_message = blockers[0].message
        run.summary_json = json.dumps(report.to_dict(), ensure_ascii=False)
        run.finished_at = datetime.now(UTC)
        db.flush()
        return run, report

    if dry_run:
        run.status = "COMPLETED"
        run.summary_json = json.dumps(report.to_dict(), ensure_ascii=False)
        run.finished_at = datetime.now(UTC)
        db.flush()
        return run, report

    report.mode = "APPLY"
    cache: dict[str, str] = {}
    source = bundle["legacy_source"]
    entities = bundle["entities"]
    created: dict[str, int] = {}
    reused: dict[str, int] = {}
    skipped: dict[str, int] = {}

    try:
        for row in entities.get("organizations") or []:
            legacy_id = str(row["legacy_id"])
            existing = _resolve_mapped_id(
                db,
                organization_id=user.organization_id,
                legacy_source=source,
                entity_type="organizations",
                legacy_id=legacy_id,
                cache=cache,
            )
            if existing:
                continue
            document = _digits(row.get("document")) or None
            org = db.scalar(select(Organization).where(Organization.document == document)) if document else None
            if not org:
                org = Organization(
                    name=str(row["name"]).strip(),
                    document=document,
                    kind=str(row.get("kind") or "HEADQUARTERS"),
                    active=bool(row.get("active", True)),
                )
                db.add(org)
                db.flush()
            _remember_map(
                db,
                organization_id=user.organization_id,
                legacy_source=source,
                entity_type="organizations",
                legacy_id=legacy_id,
                new_id=org.id,
                migration_run_id=run.id,
                payload=row,
                cache=cache,
            )
            created["organizations"] = created.get("organizations", 0) + 1

        for row in entities.get("branches") or []:
            legacy_id = str(row["legacy_id"])
            if _resolve_mapped_id(
                db,
                organization_id=user.organization_id,
                legacy_source=source,
                entity_type="branches",
                legacy_id=legacy_id,
                cache=cache,
            ):
                continue
            org_legacy = str(row.get("organization_legacy_id") or "").strip()
            org_id = user.organization_id
            if org_legacy:
                resolved = _resolve_mapped_id(
                    db,
                    organization_id=user.organization_id,
                    legacy_source=source,
                    entity_type="organizations",
                    legacy_id=org_legacy,
                    cache=cache,
                )
                if resolved:
                    org_id = resolved
            branch = Branch(
                organization_id=org_id,
                name=str(row["name"]).strip(),
                code=str(row["code"]).strip(),
                region=(str(row["region"]).strip() if row.get("region") else None),
                active=bool(row.get("active", True)),
            )
            db.add(branch)
            db.flush()
            _remember_map(
                db,
                organization_id=user.organization_id,
                legacy_source=source,
                entity_type="branches",
                legacy_id=legacy_id,
                new_id=branch.id,
                migration_run_id=run.id,
                payload=row,
                cache=cache,
            )
            created["branches"] = created.get("branches", 0) + 1

        _apply_administrators(
            db,
            actor=user,
            rows=entities.get("administrators") or [],
            legacy_source=source,
            migration_run_id=run.id,
            cache=cache,
            created=created,
            reused=reused,
        )
        _apply_users(
            db,
            actor=user,
            rows=entities.get("users") or [],
            legacy_source=source,
            migration_run_id=run.id,
            cache=cache,
            created=created,
            reused=reused,
        )
        _apply_leads(
            db,
            actor=user,
            rows=entities.get("leads") or [],
            legacy_source=source,
            migration_run_id=run.id,
            cache=cache,
            created=created,
            reused=reused,
            skipped=skipped,
        )
        _apply_quotas(
            db,
            actor=user,
            rows=entities.get("quotas") or [],
            legacy_source=source,
            migration_run_id=run.id,
            cache=cache,
            created=created,
            reused=reused,
            skipped=skipped,
        )
        _apply_proposals(
            db,
            actor=user,
            rows=entities.get("proposals") or [],
            legacy_source=source,
            migration_run_id=run.id,
            cache=cache,
            created=created,
            reused=reused,
            skipped=skipped,
        )

        remaining = [
            name
            for name in MIGRATION_ENTITY_ORDER
            if name not in IMPLEMENTED_APPLY_ENTITIES and entities.get(name)
        ]
        if remaining:
            report.warnings.append(
                MigrationIssue(
                    "WARNING",
                    "migration",
                    None,
                    f"Carga parcial concluída; pendente apply para: {', '.join(remaining)}",
                )
            )

        report.ready = True
        summary = report.to_dict()
        summary["created"] = created
        summary["reused"] = reused
        summary["skipped"] = skipped
        summary["password_policy"] = "Migrated users receive a random password hash; reset required on first login."
        run.status = "COMPLETED"
        run.summary_json = json.dumps(summary, ensure_ascii=False)
        run.finished_at = datetime.now(UTC)
        db.flush()
        return run, report
    except Exception as exc:
        run.status = "FAILED"
        run.error_message = str(exc)[:500]
        run.summary_json = json.dumps(report.to_dict(), ensure_ascii=False)
        run.finished_at = datetime.now(UTC)
        db.flush()
        raise


def list_migration_runs(db: Session, organization_id: str, *, limit: int = 30) -> list[LegacyMigrationRun]:
    return list(
        db.scalars(
            select(LegacyMigrationRun)
            .where(LegacyMigrationRun.organization_id == organization_id)
            .order_by(LegacyMigrationRun.started_at.desc())
            .limit(limit)
        )
    )


def lookup_legacy_map(
    db: Session,
    organization_id: str,
    *,
    legacy_source: str | None = None,
    entity_type: str | None = None,
    legacy_id: str | None = None,
    limit: int = 100,
) -> list[LegacyIdMap]:
    stmt = select(LegacyIdMap).where(LegacyIdMap.organization_id == organization_id)
    if legacy_source:
        stmt = stmt.where(LegacyIdMap.legacy_source == legacy_source)
    if entity_type:
        stmt = stmt.where(LegacyIdMap.entity_type == entity_type)
    if legacy_id:
        stmt = stmt.where(LegacyIdMap.legacy_id == legacy_id)
    return list(db.scalars(stmt.order_by(LegacyIdMap.created_at.desc()).limit(limit)))


def migration_run_view(item: LegacyMigrationRun) -> dict[str, Any]:
    try:
        summary = json.loads(item.summary_json or "{}")
    except json.JSONDecodeError:
        summary = {}
    return {
        "id": item.id,
        "legacy_source": item.legacy_source,
        "mode": item.mode,
        "status": item.status,
        "error_message": item.error_message,
        "summary": summary,
        "started_by_id": item.started_by_id,
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
    }


def legacy_id_map_view(item: LegacyIdMap) -> dict[str, Any]:
    return {
        "id": item.id,
        "legacy_source": item.legacy_source,
        "entity_type": item.entity_type,
        "legacy_id": item.legacy_id,
        "new_id": item.new_id,
        "migration_run_id": item.migration_run_id,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
