"""Autovistoria por matrícula — urbano/rural (SDC / Flash). Fotos via câmera no ato."""

from __future__ import annotations

import re
from typing import Any

URBAN_ROOM_TYPES = (
    "SALA",
    "COZINHA",
    "BANHEIRO",
    "QUARTO",
    "SUITE",
    "AREA_LAZER",
    "AREA_GOURMET",
)

URBAN_PHOTO_SLOTS = (
    "EXTERNA",
    "RUA",
    "SALA",
    "COZINHA",
    "BANHEIRO",
    "QUARTO",
    "SUITE",
    "AREA_LAZER",
    "AREA_GOURMET",
)

RURAL_IMPROVEMENT_TYPES = (
    "CURRAL",
    "RESFRIADOR_LEITE",
    "SILO",
    "GALPAO",
    "CERCA",
    "OUTRA",
)

RURAL_BUILDING_TYPES = ("SEDE", "CASA_VAQUEIRO", "OUTRA")

RURAL_PHOTO_GROUPS = (
    "FAZENDA",
    "MELHORIAS",
    "AREA_PRODUTIVA",
    "SEDE",
)

MIN_FARM_PHOTOS = 5
MIN_LOTE_URBANO_PHOTOS = 5


def _slug(s: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(s or "").strip().upper())[:40]


def inspection_from_properties(properties: list[dict] | None) -> list[dict]:
    """Gera estrutura vazia por matrícula a partir de properties_json."""
    out: list[dict] = []
    if not isinstance(properties, list):
        return out
    for p in properties:
        if not isinstance(p, dict):
            continue
        mat = str(p.get("matricula") or p.get("property_registry") or "").strip()
        if not mat:
            continue
        zone = str(p.get("zone") or p.get("zona") or "URBANO").strip().upper()
        if zone not in {"URBANO", "RURAL"}:
            zone = "URBANO"
        lot_type = str(p.get("lot_type") or p.get("tipo_lote") or "").strip().upper()
        out.append(
            {
                "matricula": mat,
                "zone": zone,
                "lot_type": lot_type,
                "built_area_m2": p.get("built_area_m2"),
                "rooms": p.get("rooms") or {},
                "rural": p.get("rural") or {},
                "photos": p.get("inspection_photos") or {},
            },
        )
    return out


def _count_photos(photos: dict, prefix: str) -> int:
    if not isinstance(photos, dict):
        return 0
    total = 0
    for key, val in photos.items():
        if not str(key).startswith(prefix):
            continue
        if isinstance(val, list):
            total += len([x for x in val if x])
        elif val:
            total += 1
    return total


def _total_photos(photos: dict) -> int:
    if not isinstance(photos, dict):
        return 0
    n = 0
    for val in photos.values():
        if isinstance(val, list):
            n += len([x for x in val if x])
        elif val:
            n += 1
    return n


def validate_inspection_block(block: dict, index: int = 0) -> list[str]:
    label = f"matrícula {block.get('matricula') or index + 1}"
    motivos: list[str] = []
    zone = str(block.get("zone") or "URBANO").upper()
    lot_type = str(block.get("lot_type") or "").upper()
    photos = block.get("photos") if isinstance(block.get("photos"), dict) else {}

    if zone == "URBANO" and lot_type == "LOTE":
        if _total_photos(photos) < MIN_LOTE_URBANO_PHOTOS:
            motivos.append(f"Lote urbano: mínimo {MIN_LOTE_URBANO_PHOTOS} fotos — {label}.")
        if _count_photos(photos, "RUA") < 1:
            motivos.append(f"Lote urbano: inclua foto da rua — {label}.")
    elif zone == "URBANO":
        try:
            area = float(block.get("built_area_m2") or 0)
        except (TypeError, ValueError):
            area = 0
        if area <= 0:
            motivos.append(f"Informe a área construída (m²) do imóvel — {label}.")
        rooms = block.get("rooms") if isinstance(block.get("rooms"), dict) else {}
        if not rooms:
            motivos.append(f"Informe os cômodos e quantidades antes das fotos — {label}.")
        else:
            for rt in URBAN_ROOM_TYPES:
                if rt in rooms:
                    try:
                        q = int(rooms[rt])
                    except (TypeError, ValueError):
                        q = 0
                    if q < 0:
                        motivos.append(f"Quantidade inválida de {rt} — {label}.")
        if _count_photos(photos, "EXTERNA") < 1:
            motivos.append(f"Foto externa do imóvel — {label}.")
        if _count_photos(photos, "RUA") < 1:
            motivos.append(f"Foto da rua — {label}.")
        for rt, qty in rooms.items():
            try:
                q = int(qty)
            except (TypeError, ValueError):
                q = 0
            if q <= 0:
                continue
            base = _slug(rt)
            for i in range(1, q + 1):
                key = f"{base}_{i}" if q > 1 else base
                if _count_photos(photos, key) < 1:
                    motivos.append(f"Falta foto de {rt}{' ' + str(i) if q > 1 else ''} — {label}.")
    elif zone == "RURAL":
        rural = block.get("rural") if isinstance(block.get("rural"), dict) else {}
        if rural.get("has_improvements") in (True, "SIM", "sim"):
            imps = rural.get("improvement_types") or []
            if not imps:
                motivos.append(f"Informe os tipos de melhorias na área rural — {label}.")
        if _count_photos(photos, "FAZENDA") < MIN_FARM_PHOTOS:
            motivos.append(f"Área rural: mínimo {MIN_FARM_PHOTOS} fotos da fazenda — {label}.")
        if rural.get("has_improvements") in (True, "SIM", "sim") and _count_photos(photos, "MELHORIAS") < 1:
            motivos.append(f"Inclua fotos das melhorias (currais, resfriadores etc.) — {label}.")
        if rural.get("has_productive_areas") in (True, "SIM", "sim") and _count_photos(photos, "AREA_PRODUTIVA") < 1:
            motivos.append(f"Inclua fotos das áreas produtivas — {label}.")
        if rural.get("has_headquarters") in (True, "SIM", "sim"):
            if _count_photos(photos, "SEDE") < 1:
                motivos.append(f"Inclua fotos da sede/construção rural — {label}.")
    return motivos


def validate_property_inspections(
    inspections: list | None,
    properties: list | None,
    *,
    asset_is_real_estate: bool,
) -> list[str]:
    if not asset_is_real_estate:
        return []
    if not isinstance(properties, list) or not properties:
        return ["Cadastre ao menos um imóvel com matrícula para autovistoria."]
    mats = {
        str(p.get("matricula") or "").strip()
        for p in properties
        if isinstance(p, dict) and str(p.get("matricula") or "").strip()
    }
    if not mats:
        return ["Informe a matrícula de cada imóvel antes das fotos."]
    by_mat = {str(b.get("matricula") or "").strip(): b for b in (inspections or []) if isinstance(b, dict)}
    motivos: list[str] = []
    for i, mat in enumerate(sorted(mats)):
        block = by_mat.get(mat)
        if not block:
            motivos.append(f"Complete a autovistoria (fotos) da matrícula {mat}.")
            continue
        motivos.extend(validate_inspection_block(block, i))
    return motivos


def merge_inspection_payload(existing: list | None, patch: dict) -> list[dict]:
    mat = str(patch.get("matricula") or "").strip()
    if not mat:
        raise ValueError("matricula obrigatória")
    rows = [r for r in (existing or []) if isinstance(r, dict)]
    found = False
    out: list[dict] = []
    for row in rows:
        if str(row.get("matricula") or "").strip() == mat:
            merged = {**row, **patch, "matricula": mat}
            out.append(merged)
            found = True
        else:
            out.append(row)
    if not found:
        out.append({**patch, "matricula": mat})
    return out


def attach_photo_ref(
    inspections: list[dict],
    matricula: str,
    photo_key: str,
    ref: dict[str, Any],
    *,
    camera_native: bool,
) -> list[dict]:
    if not camera_native:
        raise ValueError("As fotos de autovistoria devem ser capturadas na hora (câmera).")
    key = _slug(photo_key)
    mat = str(matricula or "").strip()
    rows = merge_inspection_payload(inspections, {"matricula": mat})
    for row in rows:
        if str(row.get("matricula") or "").strip() != mat:
            continue
        photos = row.get("photos") if isinstance(row.get("photos"), dict) else {}
        current = photos.get(key)
        if isinstance(current, list):
            photos[key] = [*current, ref]
        elif current:
            photos[key] = [current, ref]
        else:
            photos[key] = [ref]
        row["photos"] = photos
    return rows
