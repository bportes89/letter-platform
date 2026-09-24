"""Consultas Prismafy (Valid-Stamp) — API documentada em docs/source/integracao-letter.html."""

from __future__ import annotations

import logging
import re
import time
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import settings
from app.prismafy_templates import PRISMAFY_API_BASE_DEFAULT, TEMPLATE_ALIASES, TEMPLATE_BY_SLUG

logger = logging.getLogger("letter.valid_stamp_consult")

DEFAULT_TIMEOUT = settings.integration_http_timeout_seconds
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)
_TERMINAL = frozenset({"success", "partial", "failed", "invalid", "timeout", "insufficient_balance"})


def valid_stamp_consult_configured() -> bool:
    return bool((settings.valid_stamp_api_key or "").strip())


def _api_base() -> str:
    raw = (settings.valid_stamp_api_base_url or PRISMAFY_API_BASE_DEFAULT).strip()
    return raw.rstrip("/")


def _headers(idempotency_key: str | None = None) -> dict[str, str]:
    key = (settings.valid_stamp_api_key or "").strip()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def resolve_template_id(path: str) -> str | None:
    """Resolve slug, alias ou UUID para template_id Prismafy."""
    raw = (path or "").strip().strip("/")
    if not raw:
        return None
    if _UUID_RE.match(raw):
        return raw
    if raw in TEMPLATE_BY_SLUG:
        return TEMPLATE_BY_SLUG[raw]
    if raw in TEMPLATE_ALIASES:
        return TEMPLATE_ALIASES[raw]
    # último segmento de path legado
    tail = raw.split("/")[-1]
    if tail in TEMPLATE_BY_SLUG:
        return TEMPLATE_BY_SLUG[tail]
    if tail in TEMPLATE_ALIASES:
        return TEMPLATE_ALIASES[tail]
    return None


def _parse_json(response: httpx.Response) -> dict[str, Any]:
    if not response.content:
        return {}
    try:
        parsed = response.json()
        return parsed if isinstance(parsed, dict) else {"data": parsed}
    except Exception:
        return {"raw": response.text[:2000]}


def _poll_execution(
    client: httpx.Client,
    execution_id: str,
    *,
    poll_seconds: float,
    max_polls: int,
) -> tuple[int, dict[str, Any]]:
    url = f"{_api_base()}/api/v1/executions/{execution_id}/result/"
    last_body: dict[str, Any] = {}
    for _ in range(max_polls):
        response = client.get(url, headers=_headers())
        body = _parse_json(response)
        last_body = body
        status = str(body.get("status") or "").lower()
        if response.status_code in {200, 202} and status in _TERMINAL:
            return response.status_code, body
        if response.status_code >= 400 and response.status_code not in {202}:
            return response.status_code, body
        time.sleep(poll_seconds)
    return 202, {**last_body, "error": "POLL_TIMEOUT", "execution_id": execution_id}


def run_template(
    template_id: str,
    payload: dict[str, Any],
    *,
    idempotency_key: str | None = None,
    poll_seconds: float = 2.0,
    max_polls: int = 45,
) -> tuple[bool, dict[str, Any]]:
    """POST /api/v1/executions/<template_id>/run/ — com polling se assíncrono."""
    if not valid_stamp_consult_configured():
        return False, {"error": "VALID_STAMP_API_NOT_CONFIGURED"}
    url = f"{_api_base()}/api/v1/executions/{template_id}/run/"
    idem = idempotency_key or str(uuid4())
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.post(url, headers=_headers(idem), json=payload)
            body = _parse_json(response)
            if response.status_code >= 400:
                logger.warning(
                    "prismafy_run_http_error",
                    extra={"status": response.status_code, "template_id": template_id, "body": str(body)[:500]},
                )
                return False, {"error": "PROVIDER_HTTP_ERROR", "status": response.status_code, **body}
            status = str(body.get("status") or "").lower()
            execution_id = body.get("id")
            if response.status_code == 202 or status == "running":
                if not execution_id:
                    return False, {"error": "MISSING_EXECUTION_ID", **body}
                code, polled = _poll_execution(
                    client,
                    str(execution_id),
                    poll_seconds=poll_seconds,
                    max_polls=max_polls,
                )
                if code >= 400 and polled.get("error") == "POLL_TIMEOUT":
                    return False, polled
                if str(polled.get("status") or "").lower() in {"failed", "invalid", "timeout", "insufficient_balance"}:
                    return False, polled
                return True, polled
            if status in {"failed", "invalid", "timeout", "insufficient_balance"}:
                return False, body
            return True, body
    except Exception as exc:
        logger.warning("prismafy_run_exception", extra={"error": str(exc), "template_id": template_id})
        return False, {"error": "PROVIDER_EXCEPTION", "detail": str(exc)}


def consult(
    path: str,
    payload: dict[str, Any],
    *,
    method: str = "POST",
    idempotency_key: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    """
    Compatível com chamadas antigas:
    - slug/alias/uuid → execução Prismafy por template;
    - path relativo legado → HTTP direto na base configurada.
    """
    template_id = resolve_template_id(path)
    if template_id and method.upper() == "POST":
        return run_template(template_id, payload, idempotency_key=idempotency_key)

    if not valid_stamp_consult_configured():
        return False, {"error": "VALID_STAMP_API_NOT_CONFIGURED"}
    base = _api_base()
    url = f"{base}/{path.lstrip('/')}"
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=_headers(), params=payload)
            else:
                response = client.post(url, headers=_headers(idempotency_key), json=payload)
        body = _parse_json(response)
        if response.status_code >= 400:
            return False, {"error": "PROVIDER_HTTP_ERROR", "status": response.status_code, **body}
        return True, body
    except Exception as exc:
        logger.warning("valid_stamp_consult_exception", extra={"error": str(exc), "url": url})
        return False, {"error": "PROVIDER_EXCEPTION", "detail": str(exc)}
