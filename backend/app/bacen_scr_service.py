"""Conector SCR / Registrato — Banco Central (sandbox até credenciamento produtivo)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings


@dataclass(frozen=True)
class ScrConsultationResult:
    status: str
    mode: str
    reference: str
    restrictions_found: bool
    risk_band: str
    consulted_at: str
    payload: dict[str, Any]


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _reference(seed: str) -> str:
    digest = hashlib.sha256(f"scr:{seed}".encode()).hexdigest()[:16].upper()
    return f"SCR-{digest}"


def _mask_document(document: str) -> str:
    digits = _digits(document)
    if len(digits) == 14:
        return f"{digits[:2]}.***.***/{digits[8:12]}-{digits[-2:]}"
    if len(digits) == 11:
        return f"***.{digits[3:6]}.{digits[6:9]}-**"
    return "***"


class BacenScrClient:
    provider = "BACEN_SCR_REGISTRATO"

    def is_configured(self) -> bool:
        return bool(
            settings.bacen_scr_api_url
            and settings.bacen_scr_institution_code
            and settings.bacen_scr_api_key
        )

    def status(self) -> dict:
        configured = self.is_configured()
        return {
            "provider": self.provider,
            "configured": configured,
            "mode": "PRODUCTION" if configured else "SANDBOX",
            "institution_code": settings.bacen_scr_institution_code,
            "message": (
                "Conector SCR/Registrato pronto para produção."
                if configured
                else "Modo sandbox — configure LETTER_BACEN_SCR_* para consulta produtiva."
            ),
        }

    def consult(
        self,
        *,
        company_name: str,
        document: str | None = None,
        authorization_accepted: bool = False,
    ) -> ScrConsultationResult:
        if not authorization_accepted:
            raise HTTPException(status_code=422, detail="Autorização SCR/Registrato é obrigatória")
        cnpj = _digits(document)
        if self.is_configured():
            return self._consult_production(company_name=company_name, cnpj=cnpj)
        return self._consult_sandbox(company_name=company_name, cnpj=cnpj)

    def _consult_sandbox(self, *, company_name: str, cnpj: str) -> ScrConsultationResult:
        seed = cnpj or company_name.lower().strip()
        restrictions = bool(len(seed) >= 8 and int(hashlib.md5(seed.encode()).hexdigest(), 16) % 17 == 0)
        now = datetime.now(UTC).isoformat()
        payload = {
            "company_name": company_name,
            "document_masked": _mask_document(cnpj) if cnpj else "CNPJ não informado",
            "subjects": [
                {
                    "role": "PJ",
                    "document_masked": _mask_document(cnpj) if cnpj else "—",
                    "total_exposure_brl": "0.00",
                    "overdue_exposure_brl": "0.00",
                }
            ],
            "restrictions_found": restrictions,
            "risk_band": "HIGH" if restrictions else "LOW",
            "registrato_checked": True,
            "scr_checked": True,
            "consulted_at": now,
        }
        return ScrConsultationResult(
            status="RESTRICTIONS_FOUND" if restrictions else "CLEAR",
            mode="SANDBOX",
            reference=_reference(seed),
            restrictions_found=restrictions,
            risk_band=payload["risk_band"],
            consulted_at=now,
            payload=payload,
        )

    def _consult_production(self, *, company_name: str, cnpj: str) -> ScrConsultationResult:
        if len(cnpj) != 14:
            raise HTTPException(status_code=422, detail="CNPJ de 14 dígitos é obrigatório para consulta SCR produtiva")
        url = settings.bacen_scr_api_url.rstrip("/") + "/scr/consulta"
        headers = {
            "Authorization": f"Bearer {settings.bacen_scr_api_key}",
            "X-Institution-Code": settings.bacen_scr_institution_code or "",
            "Content-Type": "application/json",
        }
        body = {
            "cnpj": cnpj,
            "razao_social": company_name,
            "canal": "REGISTRATO",
            "finalidade": "CREDITO_ESTRUTURADO",
        }
        try:
            with httpx.Client(timeout=settings.integration_http_timeout_seconds) as client:
                response = client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail=f"Falha na consulta SCR/Registrato: {exc}") from exc
        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"SCR/Registrato retornou {response.status_code}",
            )
        data = response.json()
        restrictions = bool(data.get("restricoes") or data.get("restrictions_found"))
        now = datetime.now(UTC).isoformat()
        return ScrConsultationResult(
            status="RESTRICTIONS_FOUND" if restrictions else "CLEAR",
            mode="PRODUCTION",
            reference=str(data.get("protocolo") or data.get("reference") or _reference(cnpj)),
            restrictions_found=restrictions,
            risk_band=str(data.get("faixa_risco") or ("HIGH" if restrictions else "LOW")),
            consulted_at=now,
            payload=data if isinstance(data, dict) else {"raw": data},
        )


def attach_scr_to_lead(lead, result: ScrConsultationResult) -> None:
    lead.scr_status = result.status
    lead.scr_reference = result.reference
    lead.scr_consulted_at = datetime.fromisoformat(result.consulted_at.replace("Z", "+00:00"))
    lead.scr_detail_json = json.dumps(
        {
            "mode": result.mode,
            "restrictions_found": result.restrictions_found,
            "risk_band": result.risk_band,
            "payload": result.payload,
        },
        ensure_ascii=False,
    )
    if result.restrictions_found and lead.status == "NEW":
        lead.status = "SCR_REVIEW"


bacen_scr_client = BacenScrClient()
