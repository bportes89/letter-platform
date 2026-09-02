"""ONR / SERP — OAuth direto (quando configurado) ou bridge InfoSimples."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.infra_http import (
    InfraHttpError,
    digits,
    infosimples_configured,
    infosimples_consult,
    infosimples_data,
    infosimples_ok,
)
from app.provider_token_cache import get_cached_token, set_cached_token


def onr_direct_configured() -> bool:
    return bool(settings.onr_client_id and settings.onr_client_secret)


def onr_production_ready() -> bool:
    if onr_direct_configured() and (settings.onr_registry_api_url or "").strip():
        return True
    return infosimples_configured()


def fetch_onr_bearer_token() -> str:
    cached = get_cached_token("onr_oauth")
    if cached:
        return cached
    token_url = (settings.onr_token_url or "https://id.onr.org.br/connect/token").strip()
    scope = (settings.onr_api_scope or "api").strip()
    payload = {
        "grant_type": "client_credentials",
        "client_id": settings.onr_client_id,
        "client_secret": settings.onr_client_secret,
        "scope": scope,
    }
    try:
        response = httpx.post(
            token_url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=settings.integration_http_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise InfraHttpError(f"ONR OAuth indisponível: {exc}") from exc
    if response.status_code >= 400:
        raise InfraHttpError(f"ONR OAuth HTTP {response.status_code}")
    body = response.json()
    if not isinstance(body, dict):
        raise InfraHttpError("Resposta ONR OAuth inválida")
    token = body.get("access_token") or body.get("accessToken")
    if not token:
        raise InfraHttpError("ONR OAuth não retornou access token")
    expires_in = int(body.get("expires_in") or body.get("expiresIn") or 3600)
    set_cached_token("onr_oauth", str(token), expires_in_seconds=expires_in)
    return str(token)


def consult_registry_direct(*, context: dict[str, Any]) -> dict[str, Any]:
    registry = str(context.get("registry_number") or context.get("matricula") or "").strip()
    cnm = str(context.get("cnm") or "").strip()
    if not registry and not cnm:
        raise InfraHttpError("registry_number ou cnm obrigatório para consulta ONR")
    api_url = (settings.onr_registry_api_url or "").strip().rstrip("/")
    if not api_url:
        raise InfraHttpError("LETTER_ONR_REGISTRY_API_URL não configurada")
    token = fetch_onr_bearer_token()
    payload = {"matricula": registry, "cnm": cnm, "registry_number": registry}
    payload = {key: value for key, value in payload.items() if value}
    try:
        response = httpx.post(
            api_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=settings.integration_http_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise InfraHttpError(f"ONR registry API indisponível: {exc}") from exc
    if response.status_code >= 400:
        raise InfraHttpError(f"ONR registry API HTTP {response.status_code}")
    body = response.json()
    if not isinstance(body, dict):
        raise InfraHttpError("Resposta ONR registry inválida")
    encumbrances = body.get("encumbrances") or body.get("onus") or body.get("restrictions") or []
    if not isinstance(encumbrances, list):
        encumbrances = []
    return {
        "registry_number": registry or cnm,
        "encumbrances": encumbrances,
        "certificate_status": body.get("certificate_status") or body.get("status") or "UNKNOWN",
        "provider": "ONR_DIRECT",
        "external_reference": body.get("protocol") or body.get("id"),
        "payload": body,
    }


def consult_registry_infosimples(*, context: dict[str, Any]) -> dict[str, Any]:
    registry = str(context.get("registry_number") or context.get("matricula") or "").strip()
    camada = str(context.get("onr_camada") or settings.onr_infosimples_camada or "matriculas").strip()
    payload: dict[str, Any] = {"camada": camada}
    if registry:
        payload["matriculas"] = registry
    car = context.get("car")
    if car:
        payload["car"] = car
    hash_endereco = context.get("hash_endereco") or context.get("address_hash")
    if hash_endereco:
        payload["hash_endereco"] = hash_endereco

    body = infosimples_consult("consultas/onr/mapa-registro-imoveis", payload)
    if not infosimples_ok(body):
        message = str(body.get("code_message") or body.get("errors") or "Consulta ONR InfoSimples falhou")
        raise InfraHttpError(message)
    data = infosimples_data(body)
    matriculas = data.get("matriculas") or registry
    encumbrances: list[Any] = []
    if isinstance(matriculas, list) and matriculas:
        encumbrances = [{"type": "MATRICULA_REF", "value": item} for item in matriculas[:10]]
    return {
        "registry_number": registry or str(matriculas),
        "encumbrances": encumbrances,
        "certificate_status": data.get("ind_status") or "CLEAR",
        "provider": "INFOSIMPLES_ONR",
        "municipio": data.get("municipio") or data.get("cidade"),
        "estado": data.get("estado"),
        "area_hectares": data.get("area_hectares"),
        "matriculas": matriculas,
        "payload": data,
    }


def consult_registry(*, context: dict[str, Any]) -> dict[str, Any]:
    if onr_direct_configured() and (settings.onr_registry_api_url or "").strip():
        return consult_registry_direct(context=context)
    if infosimples_configured():
        return consult_registry_infosimples(context=context)
    raise InfraHttpError("Configure ONR OAuth + LETTER_ONR_REGISTRY_API_URL ou LETTER_INFOSIMPLES_API_TOKEN")
