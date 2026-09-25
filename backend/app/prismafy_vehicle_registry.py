"""Consulta veicular via Prismafy (gravame + renajud) para esteira Valid-Stamp."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException

from app.prismafy_templates import TEMPLATE_ALIASES
from app.valid_stamp_consult_client import run_template


def _text_blob(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False).lower()
    return str(value).lower()


def _has_active_flag(data: dict) -> bool:
    for key in (
        "possuiGravame",
        "tem_gravame",
        "gravameAtivo",
        "gravame_ativo",
        "possui_gravame",
        "existeGravame",
    ):
        if data.get(key) in (True, "true", "sim", "s", "1", 1):
            return True
    for key in ("quantidade", "qtdGravames", "qtd_gravames", "total"):
        try:
            if int(data.get(key) or 0) > 0:
                return True
        except (TypeError, ValueError):
            pass
    situacao = _text_blob(data.get("situacao") or data.get("status") or data.get("descricao"))
    if any(word in situacao for word in ("ativo", "vigente", "existente", "alienação", "alienacao")):
        return True
    return False


def restrictions_from_prismafy_results(results: dict[str, Any]) -> list[dict[str, Any]]:
    """Normaliza blocos Prismafy para o formato interno de restrições."""
    restrictions: list[dict[str, Any]] = []
    gravame = results.get("gravame")
    if isinstance(gravame, dict) and _has_active_flag(gravame):
        restrictions.append(
            {
                "type": "FIDUCIARY_LIEN",
                "description": "Gravame / alienação fiduciária ativa (consulta Prismafy)",
                "deadline_date": gravame.get("dataLimite") or gravame.get("deadline_date"),
                "source_document": "PRISMAFY_GRAVAME",
            }
        )
    elif isinstance(gravame, list) and gravame:
        restrictions.append(
            {
                "type": "FIDUCIARY_LIEN",
                "description": "Gravame registrado (consulta Prismafy)",
                "deadline_date": None,
                "source_document": "PRISMAFY_GRAVAME",
            }
        )

    renajud = results.get("veiculo-restricoes-renajud")
    if isinstance(renajud, dict):
        blob = _text_blob(renajud)
        items = renajud.get("restricoes") or renajud.get("restrictions") or renajud.get("itens")
        count = len(items) if isinstance(items, list) else 0
        if count > 0 or any(w in blob for w in ("renajud", "bloqueio", "judicial", "restricao", "restrição")):
            if renajud.get("possuiRestricao") in (False, "false", "nao", "não", 0) and count == 0:
                pass
            elif not (renajud.get("semRestricao") or renajud.get("cleared")):
                restrictions.append(
                    {
                        "type": "JUDICIAL_BLOCK",
                        "description": "Restrição RENAJUD / judicial (consulta Prismafy)",
                        "deadline_date": None,
                        "source_document": "PRISMAFY_RENAJUD",
                    }
                )
    elif isinstance(renajud, list) and renajud:
        restrictions.append(
            {
                "type": "JUDICIAL_BLOCK",
                "description": "Restrição RENAJUD (consulta Prismafy)",
                "deadline_date": None,
                "source_document": "PRISMAFY_RENAJUD",
            }
        )

    roubo = results.get("roubo-furto")
    if isinstance(roubo, dict) and _has_active_flag(roubo):
        restrictions.append(
            {
                "type": "TRANSFER_RESTRICTION",
                "description": "Indício roubo/furto (consulta Prismafy)",
                "deadline_date": None,
                "source_document": "PRISMAFY_ROUBO_FURTO",
            }
        )
    return restrictions


def query_vehicle_registry_prismafy(
    *,
    plate: str,
    uf: str,
    vehicle_class: str,
    renavam: str | None = None,
) -> dict[str, Any]:
    plate_norm = plate
    payload = {"placa": plate_norm}
    executions: list[dict[str, Any]] = []
    merged_results: dict[str, Any] = {}
    restrictions: list[dict[str, Any]] = []

    for alias in ("gravame", "renajud"):
        template_id = TEMPLATE_ALIASES[alias]
        ok, body = run_template(template_id, payload)
        executions.append(
            {
                "template": alias,
                "template_id": template_id,
                "ok": ok,
                "execution_id": body.get("id"),
                "status": body.get("status"),
                "error": body.get("error"),
            }
        )
        if not ok:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": f"Falha na consulta Prismafy ({alias})",
                    "provider": body,
                },
            )
        status = str(body.get("status") or "").lower()
        if status in {"failed", "invalid", "timeout", "insufficient_balance"}:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": f"Consulta Prismafy {alias} não concluída ({status})",
                    "provider": body,
                },
            )
        results = body.get("results") or {}
        if isinstance(results, dict):
            merged_results.update(results)
            restrictions.extend(restrictions_from_prismafy_results(results))

    # dedupe by type
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in restrictions:
        key = r["type"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    blocking = [r for r in unique if r["type"] in {"JUDICIAL_BLOCK", "FIDUCIARY_LIEN", "TRANSFER_RESTRICTION"}]
    return {
        "plate": plate_norm,
        "renavam": renavam,
        "uf": uf,
        "vehicle_class": vehicle_class,
        "registry_source": "PRISMAFY_VALID_STAMP",
        "queried_at": datetime.now(UTC).isoformat(),
        "restrictions": unique,
        "blocking_restrictions": blocking,
        "cleared": len(blocking) == 0,
        "note": "Consulta gravame + RENAJUD via Prismafy (Valid-Stamp)",
        "prismafy_executions": executions,
        "prismafy_results": merged_results,
    }
