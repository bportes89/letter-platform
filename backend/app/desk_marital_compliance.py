"""Estado civil e dados de cônjuge — compliance TAPAF (SDC / Flash Capital)."""

from __future__ import annotations

import re

MARITAL_REQUIRES_SPOUSE = frozenset({"CASADO", "UNIAO_ESTAVEL"})


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def validate_pf_marital(data: dict) -> list[str]:
    person = str(data.get("person_type") or "PF").strip().upper()
    if person != "PF":
        return []
    status = str(data.get("marital_status") or "").strip().upper()
    if not status:
        return ["Informe o estado civil do cliente (PF)."]
    if status not in MARITAL_REQUIRES_SPOUSE:
        return []
    motivos: list[str] = []
    if not str(data.get("spouse_name") or "").strip():
        motivos.append("Informe o nome completo do cônjuge.")
    spouse_doc = _digits(str(data.get("spouse_document") or ""))
    if len(spouse_doc) != 11:
        motivos.append("Informe o CPF do cônjuge (11 dígitos).")
    return motivos


def validate_partners_marital(partners: list | None, *, context: str = "sócio") -> list[str]:
    if not isinstance(partners, list):
        return []
    motivos: list[str] = []
    for idx, row in enumerate(partners, start=1):
        if not isinstance(row, dict):
            continue
        if not str(row.get("name") or "").strip() and not str(row.get("document") or "").strip():
            continue
        label = f"{context} {idx}"
        status = str(row.get("marital_status") or "").strip().upper()
        if not status:
            motivos.append(f"Informe o estado civil de {label}.")
            continue
        if status not in MARITAL_REQUIRES_SPOUSE:
            continue
        if not str(row.get("spouse_name") or "").strip():
            motivos.append(f"Informe o nome do cônjuge de {label}.")
        spouse_doc = _digits(str(row.get("spouse_document") or ""))
        if len(spouse_doc) != 11:
            motivos.append(f"Informe o CPF do cônjuge de {label} (11 dígitos).")
    return motivos


def validate_desk_marital_compliance(data: dict) -> list[str]:
    motivos = validate_pf_marital(data)
    person = str(data.get("person_type") or "PF").strip().upper()
    if person == "PJ":
        motivos.extend(validate_partners_marital(data.get("partners_json"), context="sócio"))
    return motivos
