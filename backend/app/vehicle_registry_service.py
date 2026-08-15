"""Consulta de restrições veiculares (DETRAN e adaptadores).

Em produção, substituir o adaptador sandbox por integração homologada com DETRAN
ou provedor autorizado. CRLV pode estar desatualizado; a consulta oficial prevalece.
"""

from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException

VEHICLE_CLASSES = {"LIGHT", "HEAVY", "MACHINE"}
BLOCKING_RESTRICTION_TYPES = {
    "JUDICIAL_BLOCK",
    "FIDUCIARY_LIEN",
    "TRANSFER_RESTRICTION",
}

RESTRICTION_LABELS = {
    "JUDICIAL_BLOCK": "Bloqueio judicial",
    "FIDUCIARY_LIEN": "Alienação fiduciária ativa",
    "TRANSFER_RESTRICTION": "Restrição de transferência (incentivo fiscal / prazo)",
}


def normalize_plate(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


def query_vehicle_registry(
    *,
    plate: str,
    uf: str,
    vehicle_class: str,
    renavam: str | None = None,
    mode: str = "sandbox",
) -> dict[str, Any]:
    plate_norm = normalize_plate(plate)
    uf_norm = uf.upper().strip()
    vclass = vehicle_class.upper().strip()
    if len(plate_norm) < 7:
        raise HTTPException(status_code=422, detail="Placa inválida")
    if len(uf_norm) != 2:
        raise HTTPException(status_code=422, detail="UF deve ter 2 caracteres")
    if vclass not in VEHICLE_CLASSES:
        raise HTTPException(
            status_code=422,
            detail="vehicle_class deve ser LIGHT (leve), HEAVY (pesado) ou MACHINE (máquina)",
        )

    queried_at = datetime.now(UTC).isoformat()
    if mode == "sandbox":
        restrictions = _sandbox_restrictions(plate_norm, vclass)
        source = "DETRAN_SANDBOX"
    else:
        raise HTTPException(
            status_code=501,
            detail="Integração DETRAN produtiva pendente de homologação; use modo sandbox",
        )

    blocking = [r for r in restrictions if r["type"] in BLOCKING_RESTRICTION_TYPES]
    return {
        "plate": plate_norm,
        "renavam": renavam,
        "uf": uf_norm,
        "vehicle_class": vclass,
        "registry_source": source,
        "queried_at": queried_at,
        "restrictions": restrictions,
        "blocking_restrictions": blocking,
        "cleared": len(blocking) == 0,
        "note": "Consulta oficial prevalece sobre CRLV desatualizado",
    }


def _sandbox_restrictions(plate: str, vehicle_class: str) -> list[dict[str, Any]]:
    """Simula respostas DETRAN para demo/homologação."""
    last = plate[-1]
    restrictions: list[dict[str, Any]] = []
    if last == "B":
        restrictions.append({
            "type": "JUDICIAL_BLOCK",
            "description": "Veículo com bloqueio judicial ativo (simulação DETRAN)",
            "deadline_date": None,
            "source_document": "DETRAN",
        })
    if last == "A":
        restrictions.append({
            "type": "FIDUCIARY_LIEN",
            "description": "Alienação fiduciária registrada — bem não quitado (simulação DETRAN)",
            "deadline_date": None,
            "source_document": "DETRAN",
        })
    if last == "T":
        restrictions.append({
            "type": "TRANSFER_RESTRICTION",
            "description": "Restrição de transferência por incentivo fiscal — prazo não expirado",
            "deadline_date": str(date.today().replace(year=date.today().year + 2)),
            "source_document": "DETRAN",
        })
    if vehicle_class == "MACHINE" and last == "M":
        restrictions.append({
            "type": "TRANSFER_RESTRICTION",
            "description": "Máquina agrícola com restrição de circulação/transferência",
            "deadline_date": str(date.today().replace(year=date.today().year + 1)),
            "source_document": "DETRAN",
        })
    return restrictions


def assert_vehicle_cleared_for_stamp(payload: dict, *, require_tapaf: bool = True) -> dict[str, Any]:
    """Valida veículo no momento TAPAF / emissão Valid-Stamp."""
    vehicle = payload.get("vehicle")
    if not isinstance(vehicle, dict):
        raise HTTPException(
            status_code=422,
            detail="Valid-Stamp veicular exige objeto vehicle (plate, uf, vehicle_class, renavam opcional)",
        )
    if require_tapaf and not str(payload.get("tapaf_evidence_reference", "")).strip():
        raise HTTPException(
            status_code=422,
            detail="Emissão de selo veicular exige pagamento TAPAF (tapaf_evidence_reference)",
        )

    result = query_vehicle_registry(
        plate=str(vehicle.get("plate", "")),
        uf=str(vehicle.get("uf", "")),
        vehicle_class=str(vehicle.get("vehicle_class", "")),
        renavam=str(vehicle.get("renavam")) if vehicle.get("renavam") else None,
    )
    if not result["cleared"]:
        labels = ", ".join(
            RESTRICTION_LABELS.get(r["type"], r["type"]) for r in result["blocking_restrictions"]
        )
        raise HTTPException(
            status_code=409,
            detail=f"Veículo com restrição impeditiva ({labels}). Operação SDC veículo bloqueada.",
        )
    return result
