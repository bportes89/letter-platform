"""Consulta NF-e na SEFAZ — produção via InfoSimples ou sandbox homologação."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

import httpx
from fastapi import HTTPException

from app.core.config import settings


@dataclass(frozen=True)
class SefazNfeResult:
    access_key: str
    status: str
    issuer_document: str | None
    issuer_name: str | None
    gross_amount: Decimal | None
    issue_date: str | None
    provider: str
    mode: str
    raw: dict


def infosimples_configured() -> bool:
    return bool(settings.infosimples_api_token and settings.infosimples_api_token.strip())


def consult_nfe(access_key: str) -> SefazNfeResult:
    key = re.sub(r"\D", "", access_key)
    if len(key) != 44:
        raise HTTPException(status_code=422, detail="Chave de acesso NF-e deve ter 44 dígitos.")

    if infosimples_configured():
        return _consult_infosimples(key)
    return _consult_sandbox(key)


def _consult_sandbox(key: str) -> SefazNfeResult:
    """Sandbox: autoriza chaves válidas de 44 dígitos para homologação."""
    canceled_suffix = key.endswith("00000000000")
    status = "CANCELED" if canceled_suffix else "AUTHORIZED"
    return SefazNfeResult(
        access_key=key,
        status=status,
        issuer_document=key[6:20] if len(key) >= 20 else None,
        issuer_name="Emitente Sandbox LETTER",
        gross_amount=Decimal("5000.00"),
        issue_date=None,
        provider="SEFAZ_SANDBOX",
        mode="SANDBOX",
        raw={"message": "Consulta simulada — configure LETTER_INFOSIMPLES_API_TOKEN para produção."},
    )


def _consult_infosimples(key: str) -> SefazNfeResult:
    token = settings.infosimples_api_token.strip()
    url = "https://api.infosimples.com/api/v2/consultas/receita-federal/nfe"
    try:
        response = httpx.get(
            url,
            params={"token": token, "chave": key},
            timeout=settings.integration_http_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"InfoSimples/SEFAZ indisponível: {exc}") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"InfoSimples retornou erro {response.status_code}")

    body = response.json()
    data = body.get("data") or []
    first = data[0] if isinstance(data, list) and data else body

    situacao = str(first.get("situacao") or first.get("status") or "").upper()
    if any(x in situacao for x in ("CANCEL", "INUTIL", "DENEG")):
        status = "CANCELED"
    elif any(x in situacao for x in ("AUTORIZ", "APROV", "VALID")):
        status = "AUTHORIZED"
    elif situacao:
        status = "REJECTED"
    else:
        status = "AUTHORIZED" if body.get("code") in {200, "200"} else "NOT_FOUND"

    gross = first.get("valor_total") or first.get("valor") or first.get("total")
    gross_amount = Decimal(str(gross)) if gross is not None else None

    return SefazNfeResult(
        access_key=key,
        status=status,
        issuer_document=str(first.get("cnpj_emitente") or first.get("cpf_emitente") or "") or None,
        issuer_name=str(first.get("nome_emitente") or first.get("razao_social") or "") or None,
        gross_amount=gross_amount,
        issue_date=str(first.get("data_emissao") or "") or None,
        provider="INFOSIMPLES_SEFAZ",
        mode="PRODUCTION",
        raw=body if isinstance(body, dict) else {"data": data},
    )
