"""Clientes do inventário infraestrutural — produção quando credenciado."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.onr_client import consult_registry, onr_production_ready
from app.serasa_client import consult_qsa, serasa_configured
from app.infra_http import (
    FIPE_PLATE_API_BASE,
    InfraHttpError,
    digits,
    http_get_json,
    infosimples_configured,
    infosimples_consult,
    infosimples_data,
    infosimples_ok,
    normalize_plate,
)


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
    production_ready: bool = False

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def query_sandbox(self, *, context: dict[str, Any]) -> InfraQueryResult: ...

    def query(self, *, context: dict[str, Any]) -> InfraQueryResult:
        try:
            if self.is_configured():
                return self.query_production(context=context)
            return self.query_sandbox(context=context)
        except InfraHttpError as exc:
            return InfraQueryResult(
                provider_code=self.code,
                status="PROVIDER_ERROR",
                mode="PRODUCTION" if self.is_configured() else "SANDBOX",
                external_reference=_ref(self.code, "error"),
                estimated_cost_brl=self.estimated_cost_brl,
                payload={"error": str(exc), "queried_at": datetime.now(UTC).isoformat()},
            )

    def query_production(self, *, context: dict[str, Any]) -> InfraQueryResult:
        sandbox = self.query_sandbox(context=context)
        return InfraQueryResult(
            provider_code=sandbox.provider_code,
            status="PRODUCTION_PENDING",
            mode="PRODUCTION_PENDING",
            external_reference=sandbox.external_reference,
            estimated_cost_brl=sandbox.estimated_cost_brl,
            payload={
                **sandbox.payload,
                "integration_status": "credential_present_http_pending",
                "provider": self.code,
            },
        )


def _ref(provider: str, seed: str) -> str:
    digest = hashlib.sha256(f"{provider}:{seed}".encode()).hexdigest()[:16]
    return f"{provider.lower()}-{digest}"


def _cnd_status(data: dict[str, Any], *, negative_keys: tuple[str, ...]) -> str:
    for key in negative_keys:
        value = data.get(key)
        if isinstance(value, bool):
            return "NEGATIVA" if value else "POSITIVA"
        if isinstance(value, str) and value.strip():
            normalized = value.upper()
            if any(token in normalized for token in ("NEGATIV", "REGULAR", "QUITE", "NADA CONSTA", "FAVOR")):
                return "NEGATIVA"
            if any(token in normalized for token in ("POSITIV", "DEBITO", "PENDENC", "CONSTA")):
                return "POSITIVA"
    situacao = str(data.get("situacao") or data.get("status") or "").upper()
    if situacao:
        if any(token in situacao for token in ("REGULAR", "NEGATIV", "QUITE", "FAVOR")):
            return "NEGATIVA"
        return "POSITIVA"
    return "UNKNOWN"


class OnrSerpClient(InfraProviderClient):
    code = "ONR_SERP"
    name = "ONR / SERP"
    estimated_cost_brl = "60.00"
    production_ready = True

    def is_configured(self) -> bool:
        return onr_production_ready()

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

    def query_production(self, *, context: dict[str, Any]) -> InfraQueryResult:
        data = consult_registry(context=context)
        registry = str(data.get("registry_number") or context.get("registry_number") or "unknown")
        return InfraQueryResult(
            provider_code=self.code,
            status="PRODUCTION_OK",
            mode="PRODUCTION",
            external_reference=_ref(self.code, registry),
            estimated_cost_brl=self.estimated_cost_brl,
            payload={
                **data,
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
    production_ready = True

    def is_configured(self) -> bool:
        return serasa_configured()

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

    def query_production(self, *, context: dict[str, Any]) -> InfraQueryResult:
        from app.company_profile_service import company_profile

        cnpj = digits(context.get("company_document")) or company_profile()["cnpj_digits"]
        data = consult_qsa(cnpj=cnpj)
        return InfraQueryResult(
            provider_code=self.code,
            status="PRODUCTION_OK",
            mode="PRODUCTION",
            external_reference=_ref(self.code, cnpj),
            estimated_cost_brl=self.estimated_cost_brl,
            payload={
                **data,
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
    production_ready = True

    def is_configured(self) -> bool:
        return infosimples_configured()

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

    def query_production(self, *, context: dict[str, Any]) -> InfraQueryResult:
        cnpj = digits(context.get("company_document"))
        cpf = digits(context.get("person_document"))
        partners = context.get("partners") or []
        partner_cpfs = [digits(p.get("cpf")) for p in partners if isinstance(p, dict)]
        partner_cpfs = [item for item in partner_cpfs if len(item) == 11]
        if not cnpj and not cpf and partner_cpfs:
            cpf = partner_cpfs[0]

        cnds: list[dict[str, Any]] = []
        subject = cnpj or cpf or "unknown"

        if len(cnpj) == 14:
            pgfn_body = infosimples_consult(
                "consultas/receita-federal/pgfn",
                {"cnpj": cnpj, "preferencia_emissao": "2via"},
            )
            pgfn_data = infosimples_data(pgfn_body)
            cnds.append({
                "type": "RFB_PGFN",
                "status": _cnd_status(pgfn_data, negative_keys=("conseguiu_emitir_certidao_negativa",)),
                "document": cnpj,
                "provider_code": pgfn_body.get("code"),
                "validade": pgfn_data.get("validade") or pgfn_data.get("validade_data"),
            })

            fgts_body = infosimples_consult(
                "consultas/caixa/regularidade",
                {"cnpj": cnpj, "preferencia_emissao": "2via"},
            )
            fgts_data = infosimples_data(fgts_body)
            cnds.append({
                "type": "FGTS_CRF",
                "status": _cnd_status(fgts_data, negative_keys=("situacao",)),
                "document": cnpj,
                "provider_code": fgts_body.get("code"),
                "validade_fim": fgts_data.get("validade_fim_data"),
            })

        tst_targets = partner_cpfs or ([cpf] if len(cpf) == 11 else [])
        if len(cnpj) == 14 and not tst_targets:
            tst_targets = [cnpj]
        for doc in tst_targets[:5]:
            tst_body = infosimples_consult(
                "consultas/tst/cndt",
                {"cpf": doc} if len(doc) == 11 else {"cnpj": doc},
            )
            tst_data = infosimples_data(tst_body)
            cnds.append({
                "type": "TST_BNDT",
                "status": _cnd_status(tst_data, negative_keys=("conseguiu_emitir_certidao_negativa", "consta")),
                "document": doc,
                "provider_code": tst_body.get("code"),
                "validade": tst_data.get("validade") or tst_data.get("validade_data"),
            })

        if not cnds:
            raise InfraHttpError("Informe company_document (CNPJ) ou partners com CPF para CNDs")

        all_ok = all(infosimples_ok({"code": item.get("provider_code")}) for item in cnds)
        return InfraQueryResult(
            provider_code=self.code,
            status="PRODUCTION_OK" if all_ok else "PRODUCTION_PARTIAL",
            mode="PRODUCTION",
            external_reference=_ref(self.code, subject),
            estimated_cost_brl=self.estimated_cost_brl,
            payload={
                "cnds": cnds,
                "queried_at": datetime.now(UTC).isoformat(),
                "provider": "INFOSIMPLES",
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
    production_ready = True

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

    def query_production(self, *, context: dict[str, Any]) -> InfraQueryResult:
        plate = normalize_plate(context.get("plate"))
        if len(plate) < 7:
            raise InfraHttpError("Placa obrigatória para consulta FIPE")
        token = (settings.fipe_api_token or "").strip()
        base = (settings.fipe_plate_api_base_url or FIPE_PLATE_API_BASE).rstrip("/")
        url = f"{base}/placas/{plate}?key={token}"
        body = http_get_json(url)
        fipe_value = (
            body.get("fipe")
            or body.get("valor")
            or body.get("valor_fipe")
            or (body.get("informacoes_veiculo") or {}).get("valor_fipe")
        )
        if fipe_value in (None, ""):
            raise InfraHttpError("FIPE não retornou valor para a placa informada")
        return InfraQueryResult(
            provider_code=self.code,
            status="PRODUCTION_OK",
            mode="PRODUCTION",
            external_reference=_ref(self.code, plate),
            estimated_cost_brl=self.estimated_cost_brl,
            payload={
                "plate": plate,
                "fipe_value_brl": str(fipe_value),
                "reference_month": datetime.now(UTC).strftime("%Y-%m"),
                "marca": body.get("marca") or (body.get("informacoes_veiculo") or {}).get("marca"),
                "modelo": body.get("modelo") or (body.get("informacoes_veiculo") or {}).get("modelo"),
                "provider": "FIPE_API_CLOUD",
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


def infra_provider_status() -> list[dict[str, Any]]:
    return [
        {
            "code": client.code,
            "name": client.name,
            "configured": client.is_configured(),
            "production_ready": client.production_ready,
        }
        for client in INFRA_CLIENTS.values()
    ]
