"""Proxy do robô de atendimento externo (letter.app.br) para o site público LETTER."""

import httpx
from fastapi import HTTPException

LEGACY_CHAT_BASE = "https://letter.app.br/api/home"


def proxy_legacy_chat(step: str | None, payload: dict | None = None) -> dict:
    url = LEGACY_CHAT_BASE if not step else f"{LEGACY_CHAT_BASE}/{step}"
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.post(url, json=payload or {})
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Robô de atendimento temporariamente indisponível.") from exc
    if not isinstance(data, dict):
        raise HTTPException(502, "Resposta inválida do atendimento externo.")
    return data
