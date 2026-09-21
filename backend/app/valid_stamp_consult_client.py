"""Consultas externas para evidências do Valid-Stamp (fornecedor LETTER / Paulo).

Credenciais somente via LETTER_VALID_STAMP_API_KEY e LETTER_VALID_STAMP_API_BASE_URL.
Nunca commitar a chave no repositório.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("letter.valid_stamp_consult")

DEFAULT_TIMEOUT = settings.integration_http_timeout_seconds


def valid_stamp_consult_configured() -> bool:
    key = (settings.valid_stamp_api_key or "").strip()
    base = (settings.valid_stamp_api_base_url or "").strip()
    return bool(key and base)


def _headers() -> dict[str, str]:
    key = (settings.valid_stamp_api_key or "").strip()
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def consult(
    path: str,
    payload: dict[str, Any],
    *,
    method: str = "POST",
) -> tuple[bool, dict[str, Any]]:
    """Chama o provedor de consultas. `path` é relativo à base (ex.: /v1/consultas/bacen)."""
    if not valid_stamp_consult_configured():
        return False, {"error": "VALID_STAMP_API_NOT_CONFIGURED"}
    base = (settings.valid_stamp_api_base_url or "").rstrip("/")
    url = f"{base}/{path.lstrip('/')}"
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=_headers(), params=payload)
            else:
                response = client.post(url, headers=_headers(), json=payload)
        body: dict[str, Any] = {}
        if response.content:
            try:
                parsed = response.json()
                body = parsed if isinstance(parsed, dict) else {"data": parsed}
            except Exception:
                body = {"raw": response.text[:2000]}
        if response.status_code >= 400:
            logger.warning(
                "valid_stamp_consult_http_error",
                extra={"status": response.status_code, "url": url, "body": str(body)[:500]},
            )
            return False, {"error": "PROVIDER_HTTP_ERROR", "status": response.status_code, **body}
        return True, body
    except Exception as exc:
        logger.warning("valid_stamp_consult_exception", extra={"error": str(exc), "url": url})
        return False, {"error": "PROVIDER_EXCEPTION", "detail": str(exc)}
