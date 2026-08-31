"""Consulta NF-e na SEFAZ — produção via InfoSimples (SEFAZ/NFE unificada)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings

INFOSIMPLES_SEFAZ_NFE_URL = "https://api.infosimples.com/api/v2/consultas/sefaz-nfe"


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


def sefaz_production_required() -> bool:
    return settings.env.strip().lower() in {"staging", "production"}


def consult_nfe(access_key: str) -> SefazNfeResult:
    key = re.sub(r"\D", "", access_key)
    if len(key) != 44:
        raise HTTPException(status_code=422, detail="Chave de acesso NF-e deve ter 44 dígitos.")

    if sefaz_production_required() and not infosimples_configured():
        raise HTTPException(
            status_code=503,
            detail="Robô SEFAZ em produção requer LETTER_INFOSIMPLES_API_TOKEN configurado no servidor.",
        )

    if infosimples_configured():
        return _consult_infosimples(key)
    return _consult_sandbox(key)


def _consult_sandbox(key: str) -> SefazNfeResult:
    """Sandbox local apenas em development — nunca em staging/production."""
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
        raw={"message": "Consulta simulada — disponível somente em LETTER_ENV=development."},
    )


def _first_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return {}


def _parse_infosimples_status(situacao: str, code: Any) -> str:
    normalized = (situacao or "").upper()
    if any(token in normalized for token in ("CANCEL", "INUTIL", "DENEG")):
        return "CANCELED"
    if any(token in normalized for token in ("AUTORIZ", "APROV", "VALID", "REGULAR")):
        return "AUTHORIZED"
    if normalized:
        return "REJECTED"
    if code in {200, "200"}:
        return "AUTHORIZED"
    return "NOT_FOUND"


def _parse_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _extract_nfe_block(body: dict[str, Any]) -> dict[str, Any]:
    data = _first_dict(body.get("data"))
    if not data:
        return {}

    nfe = data.get("nfe")
    if isinstance(nfe, dict):
        merged = dict(nfe)
        merged.setdefault("chave_acesso", data.get("chave_acesso") or data.get("normalizado_chave_acesso"))
        emitente = merged.get("emitente")
        if isinstance(emitente, dict):
            merged.setdefault("cnpj_emitente", emitente.get("cnpj"))
            merged.setdefault("cpf_emitente", emitente.get("cpf"))
            merged.setdefault("nome_emitente", emitente.get("nome") or emitente.get("nome_razao_social"))
        return merged

    return data


def _consult_infosimples(key: str) -> SefazNfeResult:
    token = settings.infosimples_api_token.strip()
    payload = {"token": token, "nfe": key}
    try:
        response = httpx.post(
            INFOSIMPLES_SEFAZ_NFE_URL,
            json=payload,
            timeout=settings.integration_http_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"InfoSimples/SEFAZ indisponível: {exc}") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"InfoSimples retornou erro HTTP {response.status_code}")

    body = response.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=502, detail="Resposta inválida da InfoSimples.")

    code = body.get("code")
    if code not in {200, "200"}:
        message = str(body.get("code_message") or body.get("errors") or "Consulta NF-e não concluída.")
        raise HTTPException(status_code=422, detail=f"SEFAZ/InfoSimples: {message}")

    nfe = _extract_nfe_block(body)
    if not nfe:
        raise HTTPException(status_code=422, detail="NF-e não encontrada na SEFAZ para a chave informada.")

    situacao = str(nfe.get("situacao") or nfe.get("status") or "")
    status = _parse_infosimples_status(situacao, code)

    gross = (
        nfe.get("valor_total")
        or nfe.get("normalizado_valor_total")
        or nfe.get("valor_nfe")
        or nfe.get("normalizado_valor_nfe")
    )
    gross_amount = _parse_decimal(gross)

    emitente = nfe.get("emitente") if isinstance(nfe.get("emitente"), dict) else {}
    issuer_document = str(
        nfe.get("cnpj_emitente")
        or nfe.get("cpf_emitente")
        or emitente.get("cnpj")
        or emitente.get("cpf")
        or ""
    ) or None
    issuer_name = str(
        nfe.get("nome_emitente")
        or nfe.get("razao_social")
        or emitente.get("nome")
        or emitente.get("nome_razao_social")
        or ""
    ) or None

    return SefazNfeResult(
        access_key=str(nfe.get("chave_acesso") or nfe.get("normalizado_chave_acesso") or key),
        status=status,
        issuer_document=issuer_document,
        issuer_name=issuer_name,
        gross_amount=gross_amount,
        issue_date=str(nfe.get("data_emissao") or "") or None,
        provider="INFOSIMPLES_SEFAZ",
        mode="PRODUCTION",
        raw=body,
    )
