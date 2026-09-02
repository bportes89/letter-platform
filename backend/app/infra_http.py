"""HTTP compartilhado para provedores do inventário NINA."""

from __future__ import annotations

import re
from typing import Any

import httpx

from app.core.config import settings

INFOSIMPLES_API_BASE = "https://api.infosimples.com/api/v2"
FIPE_PLATE_API_BASE = "https://placas.fipeapi.com.br"


class InfraHttpError(Exception):
    """Falha de rede ou resposta inválida de provedor externo."""


def normalize_plate(value: str | None) -> str:
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def infosimples_configured() -> bool:
    return bool(settings.infosimples_api_token and settings.infosimples_api_token.strip())


def infosimples_consult(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST em /api/v2/consultas/{path} — ex.: receita-federal/pgfn."""
    if not infosimples_configured():
        raise InfraHttpError("LETTER_INFOSIMPLES_API_TOKEN não configurado")
    token = settings.infosimples_api_token.strip()
    body = {"token": token, **payload}
    url = f"{INFOSIMPLES_API_BASE}/{path.lstrip('/')}"
    try:
        response = httpx.post(url, json=body, timeout=settings.integration_http_timeout_seconds)
    except httpx.HTTPError as exc:
        raise InfraHttpError(f"InfoSimples indisponível: {exc}") from exc
    if response.status_code >= 400:
        raise InfraHttpError(f"InfoSimples HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, dict):
        raise InfraHttpError("Resposta InfoSimples inválida")
    return data


def infosimples_ok(body: dict[str, Any]) -> bool:
    return body.get("code") in {200, "200"}


def infosimples_data(body: dict[str, Any]) -> dict[str, Any]:
    raw = body.get("data")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        return raw[0]
    return {}


def http_get_json(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        response = httpx.get(url, headers=headers or {}, timeout=settings.integration_http_timeout_seconds)
    except httpx.HTTPError as exc:
        raise InfraHttpError(f"GET indisponível: {exc}") from exc
    if response.status_code >= 400:
        raise InfraHttpError(f"GET HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, dict):
        raise InfraHttpError("Resposta JSON inválida")
    return data
