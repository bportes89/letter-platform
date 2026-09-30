"""Perfil marketplace das administradoras (legado: banco, correntista, nome sujo, alienações)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.administrator_service import normalize_admin_key, parse_rules
from app.models import Administrator, Quota

DIRTY_NAME_ADMIN_FALLBACK_KEYS = frozenset(
    {
        normalize_admin_key("HS Consórcios"),
        normalize_admin_key("HS"),
        normalize_admin_key("Caixa Consórcios"),
        normalize_admin_key("Itaú"),
    }
)


def parse_legacy_ano_max(value: Any) -> int | None:
    if value is None:
        return None
    raw = str(value).strip().lower()
    if not raw or raw in {"- - -", "---", "null"}:
        return None
    if raw in {"zero", "zerokm", "0km", "somente zero km"}:
        return 0
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def alienations_from_legacy_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        cat_ids = json.loads(row.get("cotas_categories") or "[]")
        anos = json.loads(row.get("ano_fabricacao_max") or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(cat_ids, list):
        return []
    if not isinstance(anos, list):
        anos = []
    out: list[dict[str, Any]] = []
    for idx, cat_id in enumerate(cat_ids):
        try:
            legacy_cat = int(cat_id)
        except (TypeError, ValueError):
            continue
        ano_raw = anos[idx] if idx < len(anos) else ""
        out.append(
            {
                "legacy_quota_category_id": legacy_cat,
                "max_vehicle_age_years": parse_legacy_ano_max(ano_raw),
            }
        )
    return out


def rules_patch_from_legacy_flags(flags: dict[str, Any], alienations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    patch: dict[str, Any] = {
        "is_bank": bool(int(flags.get("banco") or 0)),
        "requires_account_holder": bool(int(flags.get("correntista") or 0)),
        "accepts_dirty_name": bool(int(flags.get("nome_sujo") or 0)),
    }
    if alienations:
        patch["alienations"] = alienations
    return patch


def administrator_accepts_dirty_name(admin: Administrator | None) -> bool:
    if not admin:
        return False
    rules = parse_rules(admin.rules_json)
    if bool(rules.get("accepts_dirty_name")):
        return True
    return normalize_admin_key(admin.name) in DIRTY_NAME_ADMIN_FALLBACK_KEYS


def administrator_in_client_pool(
    admin: Administrator,
    *,
    client_bank_administrator_ids: set[str] | None,
    client_problem_bank_administrator_ids: set[str] | None,
) -> bool:
    problems = client_problem_bank_administrator_ids or set()
    if admin.id in problems:
        return False
    rules = parse_rules(admin.rules_json)
    accounts = client_bank_administrator_ids or set()
    if bool(rules.get("requires_account_holder")):
        return admin.id in accounts
    if admin.id in accounts:
        return True
    return True


def alienation_blockers(
    admin: Administrator | None,
    quota: Quota,
    *,
    category: str,
    asset_year: int,
    asset_is_zero_km: bool,
) -> list[str]:
    if not admin or not quota.quota_category_id:
        return []
    rules = parse_rules(admin.rules_json)
    alienations = rules.get("alienations") or []
    if not isinstance(alienations, list):
        return []
    row = next(
        (a for a in alienations if isinstance(a, dict) and a.get("quota_category_id") == quota.quota_category_id),
        None,
    )
    if not row:
        return []
    if category != "VEHICLE":
        return []
    max_age = row.get("max_vehicle_age_years")
    if max_age is None:
        return []
    if int(max_age) == 0:
        if not asset_is_zero_km:
            return [f"{admin.name} aceita somente zero km para esta subcategoria."]
        return []
    if asset_is_zero_km:
        return []
    age = datetime.now(UTC).year - int(asset_year)
    if age > int(max_age):
        return [
            f"Bem com {age} anos — {admin.name} limita esta subcategoria a até {max_age} ano(s) de fabricação."
        ]
    return []
