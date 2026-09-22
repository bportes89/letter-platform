"""Visão de cotas/marketplace para parceiros — sem expor fornecedor ou códigos de sync."""

from __future__ import annotations

from app.models import Role, User


def user_sees_supplier_quota_identity(user: User) -> bool:
    """Admin/ops e inventário veem códigos reais; parceiro comercial não."""
    if user.role in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF, Role.AUDITOR}:
        return True
    from app.models import ROLE_SCOPES

    role_scopes = ROLE_SCOPES.get(user.role, [])
    return "*" in role_scopes or "inventory:write" in role_scopes


def partner_quota_ref(quota_id: str) -> str:
    clean = quota_id.replace("-", "").upper()
    return clean[-6:] if len(clean) >= 6 else clean


def mask_quota_fields(payload: dict, *, quota_id: str) -> dict:
    ref = partner_quota_ref(quota_id)
    out = {**payload}
    out["group_code"] = "Letter"
    out["quota_code"] = f"Ref {ref}"
    out["supplier_source"] = None
    return out


def mask_quota_brief(brief: dict) -> dict:
    qid = str(brief.get("quota_id") or "")
    if not qid:
        return brief
    ref = partner_quota_ref(qid)
    out = {**brief}
    out["group_code"] = "Letter"
    out["quota_code"] = f"Ref {ref}"
    out["supplier_source"] = None
    out["markup_percent"] = None
    return out


def mask_marketplace_match_item(item: dict) -> dict:
    out = {**item}
    if "quotas" in out and isinstance(out["quotas"], list):
        out["quotas"] = [mask_quota_brief(q) for q in out["quotas"]]
    return out


def mask_esteira_result(result: dict, user: User) -> dict:
    if user_sees_supplier_quota_identity(user):
        return result
    out = {**result}
    if "quota" in out and isinstance(out["quota"], dict):
        out["quota"] = mask_quota_brief(out["quota"])
    for key in ("alternatives", "matches", "credit_matches", "entrada_matches"):
        if key in out and isinstance(out[key], list):
            out[key] = [mask_marketplace_match_item(x) for x in out[key]]
    return out
