"""Migração de dados do sistema legado — validação dry-run e apply incremental."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Administrator,
    Branch,
    LegacyIdMap,
    LegacyMigrationRun,
    Organization,
    Role,
    User,
)

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
    for row in entities.get("proposals") or []:
        if row.get("lead_legacy_id"):
            require_ref("proposals", "lead_legacy_id", row)

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

    unsupported = [name for name in MIGRATION_ENTITY_ORDER if name not in {"organizations", "branches"} and entities.get(name)]
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

    cache: dict[str, str] = {}
    source = bundle["legacy_source"]
    entities = bundle["entities"]
    created: dict[str, int] = {}

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

        if any(entities.get(name) for name in MIGRATION_ENTITY_ORDER if name not in {"organizations", "branches"}):
            raise ValueError(
                "Apply parcial: apenas organizations e branches estão implementados nesta versão"
            )

        report.ready = True
        summary = report.to_dict()
        summary["created"] = created
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
