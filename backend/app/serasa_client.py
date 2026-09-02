"""Serasa Experian — IAM + Relatório Avançado PJ (QSA)."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.infra_http import InfraHttpError, digits
from app.provider_token_cache import get_cached_token, set_cached_token

SERASA_PROD_BASE = "https://api.serasaexperian.com.br"
SERASA_UAT_BASE = "https://uat-api.serasaexperian.com.br"


def serasa_configured() -> bool:
    return bool(settings.serasa_api_key and settings.serasa_api_key.strip())


def _base_url() -> str:
    custom = (settings.serasa_api_base_url or "").strip()
    if custom:
        return custom.rstrip("/")
    if settings.env.strip().lower() in {"development", "staging"}:
        return SERASA_UAT_BASE
    return SERASA_PROD_BASE


def _basic_authorization() -> str:
    raw = settings.serasa_api_key.strip()
    return raw if raw.lower().startswith("basic ") else f"Basic {raw}"


def fetch_bearer_token() -> str:
    cached = get_cached_token("serasa_iam")
    if cached:
        return cached
    url = f"{_base_url()}/security/iam/v1/client-identities/login"
    try:
        response = httpx.post(
            url,
            headers={
                "Authorization": _basic_authorization(),
                "Content-Type": "application/json",
            },
            json={},
            timeout=settings.integration_http_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise InfraHttpError(f"Serasa IAM indisponível: {exc}") from exc
    if response.status_code >= 400:
        raise InfraHttpError(f"Serasa IAM HTTP {response.status_code}")
    body = response.json()
    if not isinstance(body, dict):
        raise InfraHttpError("Resposta Serasa IAM inválida")
    token = body.get("accessToken") or body.get("access_token") or body.get("AccessToken")
    if not token:
        raise InfraHttpError("Serasa IAM não retornou access token")
    expires_in = int(body.get("expiresIn") or body.get("expires_in") or 3600)
    set_cached_token("serasa_iam", str(token), expires_in_seconds=expires_in)
    return str(token)


def consult_qsa(*, cnpj: str, partners_limit: int = 10) -> dict[str, Any]:
    doc = digits(cnpj)
    if len(doc) != 14:
        raise InfraHttpError("CNPJ de 14 dígitos obrigatório para consulta Serasa QSA")
    token = fetch_bearer_token()
    report = (settings.serasa_report_name or "RELATORIO_AVANCADO_PJ").strip()
    features = (settings.serasa_optional_features or "QSA_AVANCADO").strip()
    url = f"{_base_url()}/credit-services/business-information-report/v1/reports"
    params = {"reportName": report, "optionalFeatures": features}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Document-Id": doc,
    }
    retailer = (settings.serasa_retailer_document or "").strip()
    if retailer:
        headers["X-Retailer-Document-Id"] = digits(retailer) or retailer
    try:
        response = httpx.get(
            url,
            params=params,
            headers=headers,
            timeout=settings.integration_http_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise InfraHttpError(f"Serasa relatório indisponível: {exc}") from exc
    if response.status_code >= 400:
        raise InfraHttpError(f"Serasa relatório HTTP {response.status_code}")
    body = response.json()
    if not isinstance(body, dict):
        raise InfraHttpError("Resposta Serasa relatório inválida")

    partners = _extract_partners(body, limit=partners_limit)
    restrictions = _count_restrictions(body)
    return {
        "company_document": doc,
        "partners_screened": len(partners),
        "partners": partners,
        "restrictions_found": restrictions,
        "score_band": _score_band(body),
        "provider": "SERASA_EXPERIAN",
        "report_name": report,
        "optional_features": features,
        "raw_keys": list(body.keys())[:20],
    }


def _extract_partners(body: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    candidates: list[Any] = []
    for key in ("optionalFeatures", "reports", "report", "data"):
        block = body.get(key)
        if isinstance(block, dict):
            for subkey in ("qsa", "QSA", "partners", "administrativeBoard", "directors"):
                if subkey in block:
                    candidates.append(block[subkey])
        if isinstance(block, list):
            candidates.extend(block)

    flat: list[dict[str, Any]] = []
    for item in candidates:
        if isinstance(item, dict):
            for partner_key in ("partners", "partnerList", "members", "administrators"):
                nested = item.get(partner_key)
                if isinstance(nested, list):
                    flat.extend(x for x in nested if isinstance(x, dict))
            if any(k in item for k in ("document", "cpf", "cnpj", "name", "nome")):
                flat.append(item)
        elif isinstance(item, list):
            flat.extend(x for x in item if isinstance(x, dict))

    partners: list[dict[str, Any]] = []
    for row in flat[:limit]:
        partners.append({
            "name": row.get("name") or row.get("nome") or row.get("partnerName"),
            "document": row.get("document") or row.get("cpf") or row.get("cnpj"),
            "role": row.get("role") or row.get("qualification") or row.get("cargo"),
        })
    return partners


def _count_restrictions(body: dict[str, Any]) -> int:
    negative = body.get("negativeData") or body.get("negativeAnnotations") or body.get("annotations")
    if isinstance(negative, list):
        return len(negative)
    if isinstance(negative, dict):
        total = negative.get("total") or negative.get("count")
        if total is not None:
            return int(total)
        return len(negative.keys())
    return 0


def _score_band(body: dict[str, Any]) -> str:
    score_block = body.get("score") or body.get("positiveScore") or {}
    if isinstance(score_block, dict):
        score = score_block.get("score") or score_block.get("value")
        if score is not None:
            return f"SCORE_{score}"
    return "UNKNOWN"
