"""Exportador letter_banco_new.sql → bundle JSON para migração v0.24."""

from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.legacy_sql_parser import load_table

DEFAULT_SQL = Path(__file__).resolve().parents[2] / "legacy" / "letter_banco_new.sql"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "legacy" / "export" / "bundle.json"

AFFILIATE_TYPE_ROLE = {
    "partners": "PARTNER",
    "sellers": "QUOTA_SELLER",
    "supervisors": "MANAGER",
    "managers": "MANAGER",
    "regionais": "MASTER_FRANCHISEE",
}

CUSTOMER_STATUS_TO_LEAD = {
    0: "NEW",
    1: "NEW",
    2: "QUALIFIED",
    10: "CONTACTED",
    11: "LOST",
}


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _slug_code(name: str, legacy_id: str, *, prefix: str = "") -> str:
    normalized = unicodedata.normalize("NFKD", name or "")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9]+", "_", ascii_name).strip("_").upper()
    base = base[:40] or f"{prefix}{legacy_id}".upper()
    return base


def _as_bool(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return int(value) != 0


def _as_decimal(value: Any) -> str:
    if value is None:
        return "0"
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _clean_email(value: Any, *, fallback: str) -> str:
    email = str(value or "").strip().lower()
    if email and "@" in email and "." in email.split("@")[-1]:
        return email
    return fallback


def _quota_category(category_id: Any, categories: dict[int, dict[str, Any]]) -> str:
    cat = categories.get(int(category_id or 0), {})
    title = str(cat.get("title_sub") or cat.get("name") or "").lower()
    parent = int(cat.get("subcategories") or cat.get("type") or 0)
    if parent == 1 or "im" in title or "imovel" in title:
        return "REAL_ESTATE"
    return "VEHICLE"


def _quota_status(row: dict[str, Any]) -> str:
    if not _as_bool(row.get("active")):
        return "INACTIVE"
    if int(row.get("status") or 0) == 1:
        return "AVAILABLE"
    return "UNAVAILABLE"


def _normalize_name(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_name).strip().lower()


def _build_administrator_lookup(rows: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in rows:
        legacy_id = str(row["id"])
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        keys = {_normalize_name(name)}
        first_token = _normalize_name(name).split(" ")[0]
        if first_token:
            keys.add(first_token)
        compact = re.sub(r"[^a-z0-9]", "", _normalize_name(name))
        if compact:
            keys.add(compact)
        for key in keys:
            lookup.setdefault(key, legacy_id)
    return lookup


def _resolve_administrator_legacy_id(
    row: dict[str, Any],
    *,
    admin_by_id: dict[str, str],
    admin_lookup: dict[str, str],
) -> str | None:
    admin_legacy = str(row.get("administrators") or "0")
    if admin_legacy not in {"0", "", "None"} and admin_legacy in admin_by_id:
        return admin_legacy
    txt = str(row.get("administrators_txt") or "").strip()
    if not txt:
        return None
    candidates = [
        _normalize_name(txt),
        re.sub(r"[^a-z0-9]", "", _normalize_name(txt)),
        _normalize_name(txt).split(" ")[0],
    ]
    for candidate in candidates:
        if candidate and candidate in admin_lookup:
            return admin_lookup[candidate]
    for key, legacy_id in admin_lookup.items():
        if key and (key in _normalize_name(txt) or _normalize_name(txt) in key):
            return legacy_id
    return None


def _group_and_quota_code(row: dict[str, Any]) -> tuple[str, str]:
    legacy_id = str(row["id"])
    api_ref = int(row.get("api") or 0)
    supplier_id = int(row.get("suppliers") or 0)
    if api_ref > 0:
        group_code = str(api_ref)
    elif supplier_id > 0:
        group_code = f"SUP{supplier_id}"
    else:
        group_code = f"LEG{legacy_id}"
    return group_code, legacy_id.zfill(4)


def export_legacy_bundle(
    sql_path: Path,
    *,
    legacy_source: str = "letter_v1",
    org_name: str = "FPS Consórcios / Letter",
    org_document: str | None = None,
    branch_name: str = "Matriz Legacy",
    branch_code: str = "LEG-MTZ",
    include_inactive: bool = False,
    limit: dict[str, int] | None = None,
) -> dict[str, Any]:
    sql = sql_path.read_text(encoding="utf-8", errors="replace")
    limits = limit or {}

    administrators_rows = load_table(sql, "administrators")
    affiliates_rows = load_table(sql, "affiliates")
    suppliers_rows = load_table(sql, "suppliers")
    customers_rows = load_table(sql, "customers")
    quotas_rows = load_table(sql, "quotas")
    staff_rows = load_table(sql, "users")
    categories_rows = load_table(sql, "quotas_categories")

    categories = {int(row["id"]): row for row in categories_rows}

    if limits.get("administrators"):
        administrators_rows = administrators_rows[: limits["administrators"]]
    if limits.get("affiliates"):
        affiliates_rows = affiliates_rows[: limits["affiliates"]]
    if limits.get("suppliers"):
        suppliers_rows = suppliers_rows[: limits["suppliers"]]
    if limits.get("customers"):
        customers_rows = customers_rows[: limits["customers"]]
    if limits.get("quotas"):
        quotas_rows = quotas_rows[: limits["quotas"]]
    if limits.get("users"):
        staff_rows = staff_rows[: limits["users"]]

    org_doc = org_document or _digits(
        next(
            (
                row.get("cnpj")
                for row in affiliates_rows
                if _digits(row.get("cnpj"))
            ),
            "",
        )
    ) or None

    bundle: dict[str, Any] = {
        "legacy_source": legacy_source,
        "entities": {
            "organizations": [
                {
                    "legacy_id": "org-main",
                    "name": org_name,
                    "document": org_doc,
                    "kind": "HEADQUARTERS",
                    "active": True,
                }
            ],
            "branches": [
                {
                    "legacy_id": "branch-main",
                    "organization_legacy_id": "org-main",
                    "name": branch_name,
                    "code": branch_code,
                    "region": "BR",
                    "active": True,
                }
            ],
            "administrators": [],
            "users": [],
            "network_nodes": [],
            "leads": [],
            "quotas": [],
            "proposals": [],
        },
        "meta": {
            "source_sql": str(sql_path),
            "exported_counts": {},
            "skipped": {},
        },
    }

    admin_by_id: dict[str, str] = {}
    admin_lookup = _build_administrator_lookup(administrators_rows)
    for row in administrators_rows:
        if not include_inactive and not _as_bool(row.get("active")):
            continue
        legacy_id = str(row["id"])
        admin_by_id[legacy_id] = legacy_id
        name = str(row.get("name") or "").strip()
        bundle["entities"]["administrators"].append(
            {
                "legacy_id": legacy_id,
                "name": name,
                "code": _slug_code(name, legacy_id, prefix="ADM_"),
                "document": f"99{int(legacy_id):012d}"[:14],
                "active": _as_bool(row.get("active")),
                "legacy_flags": {
                    "banco": int(row.get("banco") or 0),
                    "correntista": int(row.get("correntista") or 0),
                    "nome_sujo": int(row.get("nome_sujo") or 0),
                },
            }
        )

    user_legacy_ids: set[str] = set()

    for row in suppliers_rows:
        if not include_inactive and not _as_bool(row.get("active")):
            continue
        legacy_id = f"supplier-{row['id']}"
        user_legacy_ids.add(legacy_id)
        name = str(row.get("name") or row.get("fantasia") or "").strip()
        email = _clean_email(row.get("email"), fallback=f"supplier-{row['id']}@migration.letter.invalid")
        bundle["entities"]["users"].append(
            {
                "legacy_id": legacy_id,
                "name": name or f"Fornecedor {row['id']}",
                "email": email,
                "document": _digits(row.get("cpf") or row.get("cnpj")) or None,
                "phone": row.get("phone"),
                "role": "QUOTA_SELLER",
                "branch_legacy_id": "branch-main",
                "company_name": row.get("fantasia") or row.get("name"),
                "company_cnpj": _digits(row.get("cnpj")) or None,
                "legacy_source_table": "suppliers",
                "legacy_source_id": str(row["id"]),
            }
        )
        bundle["entities"]["network_nodes"].append(
            {
                "legacy_id": f"node-{legacy_id}",
                "user_legacy_id": legacy_id,
                "tree_type": "SALES",
                "referral_code": (str(row.get("url") or "").strip().upper() or None),
            }
        )

    for row in affiliates_rows:
        if not include_inactive and not _as_bool(row.get("active")):
            continue
        legacy_id = f"affiliate-{row['id']}"
        user_legacy_ids.add(legacy_id)
        aff_type = str(row.get("type") or "partners").strip().lower()
        role = AFFILIATE_TYPE_ROLE.get(aff_type, "PARTNER")
        name = str(row.get("name") or row.get("razao_social") or row.get("fantasia") or "").strip()
        email = _clean_email(row.get("email"), fallback=f"affiliate-{row['id']}@migration.letter.invalid")
        bundle["entities"]["users"].append(
            {
                "legacy_id": legacy_id,
                "name": name or f"Afiliado {row['id']}",
                "email": email,
                "document": _digits(row.get("cpf") or row.get("cnpj")) or None,
                "phone": row.get("phone"),
                "role": role,
                "branch_legacy_id": "branch-main",
                "company_name": row.get("razao_social") or row.get("fantasia"),
                "company_cnpj": _digits(row.get("cnpj")) or None,
                "legacy_affiliate_type": aff_type,
                "legacy_url_slug": row.get("url"),
                "legacy_source_table": "affiliates",
                "legacy_source_id": str(row["id"]),
            }
        )
        bundle["entities"]["network_nodes"].append(
            {
                "legacy_id": f"node-{legacy_id}",
                "user_legacy_id": legacy_id,
                "tree_type": "SALES",
                "legacy_qualification_id": row.get("affiliates_qualification"),
                "referral_code": (str(row.get("url") or "").strip().upper() or None),
            }
        )

    for row in staff_rows:
        if not include_inactive and not _as_bool(row.get("active")):
            continue
        legacy_id = f"staff-{row['id']}"
        user_legacy_ids.add(legacy_id)
        name = str(row.get("name") or "").strip()
        email = _clean_email(row.get("email"), fallback=f"staff-{row['id']}@migration.letter.invalid")
        role = "PLATFORM_ADMIN" if int(row.get("permissions_all") or 0) == 1 else "INTERNAL_STAFF"
        bundle["entities"]["users"].append(
            {
                "legacy_id": legacy_id,
                "name": name or f"Staff {row['id']}",
                "email": email,
                "phone": row.get("phone"),
                "role": role,
                "branch_legacy_id": "branch-main",
                "legacy_source_table": "users",
                "legacy_source_id": str(row["id"]),
            }
        )

    supplier_id_map = {str(row["id"]): f"supplier-{row['id']}" for row in suppliers_rows}

    for row in customers_rows:
        if not include_inactive and not _as_bool(row.get("active")):
            continue
        legacy_id = f"customer-{row['id']}"
        partner_raw = str(row.get("partners") or "").strip()
        owner_legacy_id = None
        if partner_raw and partner_raw not in {"0", "null", "None"}:
            owner_legacy_id = f"affiliate-{partner_raw}"
        status_code = int(row.get("status") or 0)
        product = "SDC" if int(row.get("sdc") or 0) else "MARKETPLACE"
        lead = {
            "legacy_id": legacy_id,
            "name": str(row.get("name") or "").strip() or f"Cliente {row['id']}",
            "phone": str(row.get("phone") or "").strip() or "00000000000",
            "email": _clean_email(row.get("email"), fallback=f"customer-{row['id']}@migration.letter.invalid"),
            "status": CUSTOMER_STATUS_TO_LEAD.get(status_code, "NEW"),
            "product_interest": product,
            "legacy_source_table": "customers",
            "legacy_source_id": str(row["id"]),
            "legacy_status_code": status_code,
            "legacy_document": _digits(row.get("cpf") or row.get("cnpj")) or None,
        }
        if owner_legacy_id:
            lead["owner_user_legacy_id"] = owner_legacy_id
        bundle["entities"]["leads"].append(lead)

        if row.get("quotas") and str(row.get("quotas")) not in {"NULL", "None", ""}:
            bundle["entities"]["proposals"].append(
                {
                    "legacy_id": f"proposal-{row['id']}",
                    "product": product,
                    "lead_legacy_id": legacy_id,
                    "requested_amount": _as_decimal(row.get("price")),
                    "legacy_status_code": status_code,
                }
            )

    for row in quotas_rows:
        if not include_inactive and not _as_bool(row.get("active")):
            continue
        admin_legacy = _resolve_administrator_legacy_id(
            row,
            admin_by_id=admin_by_id,
            admin_lookup=admin_lookup,
        )
        if not admin_legacy:
            bundle["meta"]["skipped"].setdefault("quotas_missing_administrator", 0)
            bundle["meta"]["skipped"]["quotas_missing_administrator"] += 1
            continue
        group_code, quota_code = _group_and_quota_code(row)
        outstanding = float(row.get("price_parcela") or 0) * float(row.get("parcelas") or 0)
        seller_legacy = supplier_id_map.get(str(row.get("suppliers") or ""))
        quota = {
            "legacy_id": f"quota-{row['id']}",
            "administrator_legacy_id": admin_legacy,
            "group_code": group_code,
            "quota_code": quota_code,
            "category": _quota_category(row.get("quotas_categories"), categories),
            "credit_value": _as_decimal(row.get("price")),
            "outstanding_balance": _as_decimal(outstanding),
            "premium_value": _as_decimal(row.get("price_entrada")),
            "installment_due_date": row.get("date_vencimento"),
            "status": _quota_status(row),
            "legacy_source_table": "quotas",
            "legacy_source_id": str(row["id"]),
            "legacy_api_ref": row.get("api"),
            "legacy_administrator_name": row.get("administrators_txt"),
        }
        if seller_legacy:
            quota["seller_user_legacy_id"] = seller_legacy
        bundle["entities"]["quotas"].append(quota)

    for key, rows in bundle["entities"].items():
        bundle["meta"]["exported_counts"][key] = len(rows)

    return bundle


def write_bundle(bundle: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
