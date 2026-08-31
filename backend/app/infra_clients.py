"""Clientes do inventário infraestrutural — sandbox até homologação produtiva."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings


@dataclass(frozen=True)
class InfraQueryResult:
    provider_code: str
    status: str
    mode: str
    external_reference: str
    payload: dict[str, Any]
    estimated_cost_brl: str


class InfraProviderClient(ABC):
    code: str
    name: str
    estimated_cost_brl: str

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def query_sandbox(self, *, context: dict[str, Any]) -> InfraQueryResult: ...

    def query(self, *, context: dict[str, Any]) -> InfraQueryResult:
        if self.is_configured():
            return self.query_production(context=context)
        return self.query_sandbox(context=context)

    def query_production(self, *, context: dict[str, Any]) -> InfraQueryResult:
        return self.query_sandbox(context=context)


def _ref(provider: str, seed: str) -> str:
    digest = hashlib.sha256(f"{provider}:{seed}".encode()).hexdigest()[:16]
    return f"{provider.lower()}-{digest}"


class OnrSerpClient(InfraProviderClient):
    code = "ONR_SERP"
    name = "ONR / SERP"
    estimated_cost_brl = "60.00"

    def is_configured(self) -> bool:
        return bool(settings.onr_client_id and settings.onr_client_secret)

    def query_sandbox(self, *, context: dict[str, Any]) -> InfraQueryResult:
        registry = context.get("registry_number") or "SANDBOX-MATRICULA"
        return InfraQueryResult(
            provider_code=self.code,
            status="SANDBOX_OK",
            mode="SANDBOX",
            external_reference=_ref(self.code, registry),
            estimated_cost_brl=self.estimated_cost_brl,
            payload={
                "registry_number": registry,
                "encumbrances": [],
                "certificate_status": "CLEAR",
                "queried_at": datetime.now(UTC).isoformat(),
            },
        )


class DataZapClient(InfraProviderClient):
    code = "DATAZAP_AVM"
    name = "DataZap AVM"
    estimated_cost_brl = "10.00"

    def is_configured(self) -> bool:
        return bool(settings.datazap_api_token)

    def query_sandbox(self, *, context: dict[str, Any]) -> InfraQueryResult:
        avm = context.get("appraisal_value") or "1000000.00"
        return InfraQueryResult(
            provider_code=self.code,
            status="SANDBOX_OK",
            mode="SANDBOX",
            external_reference=_ref(self.code, str(avm)),
            estimated_cost_brl=self.estimated_cost_brl,
            payload={
                "avm_value_brl": avm,
                "ltv_max_percent": "40",
                "source": "DATAZAP_SANDBOX",
                "queried_at": datetime.now(UTC).isoformat(),
            },
        )


class SerasaQsaClient(InfraProviderClient):
    code = "SERASA_QSA"
    name = "Serasa Experian QSA"
    estimated_cost_brl = "40.00"

    def is_configured(self) -> bool:
        return bool(settings.serasa_api_key)

    def query_sandbox(self, *, context: dict[str, Any]) -> InfraQueryResult:
        doc = context.get("company_document") or "00000000000000"
        partners = context.get("partners") or [{"cpf": "00000000000", "role": "ADMIN"}]
        return InfraQueryResult(
            provider_code=self.code,
            status="SANDBOX_OK",
            mode="SANDBOX",
            external_reference=_ref(self.code, doc),
            estimated_cost_brl=self.estimated_cost_brl,
            payload={
                "company_document": doc,
                "partners_screened": len(partners),
                "restrictions_found": 0,
                "score_band": "LOW_RISK_SANDBOX",
                "queried_at": datetime.now(UTC).isoformat(),
            },
        )


class JudisTribunalsClient(InfraProviderClient):
    code = "JUDIS_TRIBUNALS"
    name = "Judis / Digivox"
    estimated_cost_brl = "30.00"

    def is_configured(self) -> bool:
        return bool(settings.judis_api_key)

    def query_sandbox(self, *, context: dict[str, Any]) -> InfraQueryResult:
        subject = context.get("company_document") or "SANDBOX-SUBJECT"
        return InfraQueryResult(
            provider_code=self.code,
            status="SANDBOX_OK",
            mode="SANDBOX",
            external_reference=_ref(self.code, subject),
            estimated_cost_brl=self.estimated_cost_brl,
            payload={
                "active_cases": 0,
                "risk_alert": False,
                "subjects": ["COMPANY", "PARTNERS", "COLLATERAL"],
                "queried_at": datetime.now(UTC).isoformat(),
            },
        )


class InfoSimplesCndClient(InfraProviderClient):
    code = "INFOSIMPLES_CND"
    name = "InfoSimples CNDs"
    estimated_cost_brl = "0.00"

    def is_configured(self) -> bool:
        return bool(settings.infosimples_api_token)

    def query_sandbox(self, *, context: dict[str, Any]) -> InfraQueryResult:
        return InfraQueryResult(
            provider_code=self.code,
            status="SANDBOX_OK",
            mode="SANDBOX",
            external_reference=_ref(self.code, "cnd-bundle"),
            estimated_cost_brl=self.estimated_cost_brl,
            payload={
                "cnds": [
                    {"type": "RFB_PGFN", "status": "NEGATIVA_SANDBOX"},
                    {"type": "FGTS_CRF", "status": "REGULAR_SANDBOX"},
                    {"type": "TST_BNDT", "status": "NEGATIVA_SANDBOX"},
                ],
                "queried_at": datetime.now(UTC).isoformat(),
            },
        )


class SerproDenatranClient(InfraProviderClient):
    code = "SERPRO_DENATRAN"
    name = "SERPRO Denatran/Vio"
    estimated_cost_brl = "0.00"

    def is_configured(self) -> bool:
        return bool(settings.serpro_api_key)

    def query_sandbox(self, *, context: dict[str, Any]) -> InfraQueryResult:
        plate = context.get("plate") or "ABC1D23"
        return InfraQueryResult(
            provider_code=self.code,
            status="SANDBOX_OK",
            mode="SANDBOX",
            external_reference=_ref(self.code, plate),
            estimated_cost_brl=self.estimated_cost_brl,
            payload={
                "plate": plate,
                "renajud": False,
                "lien": False,
                "theft_flag": False,
                "queried_at": datetime.now(UTC).isoformat(),
            },
        )


class FipeCloudClient(InfraProviderClient):
    code = "FIPE_CLOUD"
    name = "Fipe API Cloud"
    estimated_cost_brl = "0.00"

    def is_configured(self) -> bool:
        return bool(settings.fipe_api_token)

    def query_sandbox(self, *, context: dict[str, Any]) -> InfraQueryResult:
        plate = context.get("plate") or "ABC1D23"
        return InfraQueryResult(
            provider_code=self.code,
            status="SANDBOX_OK",
            mode="SANDBOX",
            external_reference=_ref(self.code, f"fipe-{plate}"),
            estimated_cost_brl=self.estimated_cost_brl,
            payload={
                "plate": plate,
                "fipe_value_brl": "85000.00",
                "reference_month": datetime.now(UTC).strftime("%Y-%m"),
                "queried_at": datetime.now(UTC).isoformat(),
            },
        )


class MolicarClient(InfraProviderClient):
    code = "MOLICAR"
    name = "Molicar B2B"
    estimated_cost_brl = "0.00"

    def is_configured(self) -> bool:
        return bool(settings.molicar_api_token)

    def query_sandbox(self, *, context: dict[str, Any]) -> InfraQueryResult:
        vehicle_class = context.get("vehicle_class") or "HEAVY"
        return InfraQueryResult(
            provider_code=self.code,
            status="SANDBOX_OK",
            mode="SANDBOX",
            external_reference=_ref(self.code, vehicle_class),
            estimated_cost_brl=self.estimated_cost_brl,
            payload={
                "vehicle_class": vehicle_class,
                "molicar_value_brl": "420000.00",
                "fallback_from_fipe": context.get("fipe_miss", False),
                "queried_at": datetime.now(UTC).isoformat(),
            },
        )


class IncraPigtClient(InfraProviderClient):
    code = "INCRA_PIGT"
    name = "INCRA PIGT / SNCR"
    estimated_cost_brl = "0.00"

    def is_configured(self) -> bool:
        return bool(settings.incra_api_key)

    def query_sandbox(self, *, context: dict[str, Any]) -> InfraQueryResult:
        snrc = context.get("sncr_code") or "SNCR-SANDBOX"
        return InfraQueryResult(
            provider_code=self.code,
            status="SANDBOX_OK",
            mode="SANDBOX",
            external_reference=_ref(self.code, snrc),
            estimated_cost_brl=self.estimated_cost_brl,
            payload={
                "sncr_code": snrc,
                "ccir_status": "REGULAR_SANDBOX",
                "queried_at": datetime.now(UTC).isoformat(),
            },
        )


INFRA_CLIENTS: dict[str, InfraProviderClient] = {
    cls.code: cls()  # type: ignore[misc]
    for cls in (
        OnrSerpClient,
        DataZapClient,
        SerasaQsaClient,
        JudisTribunalsClient,
        InfoSimplesCndClient,
        SerproDenatranClient,
        FipeCloudClient,
        MolicarClient,
        IncraPigtClient,
    )
}

DEFAULT_TAPAF_PROVIDERS = ("ONR_SERP", "DATAZAP_AVM", "SERASA_QSA", "JUDIS_TRIBUNALS", "INFOSIMPLES_CND")
VEHICLE_TAPAF_PROVIDERS = ("SERPRO_DENATRAN", "FIPE_CLOUD", "MOLICAR")
RURAL_TAPAF_PROVIDERS = ("INCRA_PIGT",)
