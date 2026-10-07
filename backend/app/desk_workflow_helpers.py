"""Fluxo mesa: TAPAF pós-fotos/análise e autovistoria em evaluation_json."""

from __future__ import annotations

from json import dumps as json_dumps
from json import loads as json_loads

from app.models import PreAnalysisPauta


def evaluation_meta(item) -> dict:
    try:
        meta = json_loads(item.evaluation_json or "{}")
    except (TypeError, ValueError):
        meta = {}
    return meta if isinstance(meta, dict) else {}


def properties_from_item(item) -> list:
    meta = evaluation_meta(item)
    props = meta.get("properties_json")
    return props if isinstance(props, list) else []


def inspections_from_item(item) -> list:
    meta = evaluation_meta(item)
    rows = meta.get("property_inspections_json")
    return rows if isinstance(rows, list) else []


def save_inspections_on_item(item, rows: list) -> None:
    meta = evaluation_meta(item)
    meta["property_inspections_json"] = rows
    channel = meta.get("channel")
    item.evaluation_json = json_dumps({**meta, **({"channel": channel} if channel else {})}, ensure_ascii=False)


def item_is_real_estate(item) -> bool:
    at = str(getattr(item, "asset_type", "") or "").strip().lower()
    cat = str(getattr(item, "asset_category", "") or "").strip().lower()
    if cat in {"imovel", "real_estate", "imovel_urbano", "imovel_rural"}:
        return True
    return at in {"imovel", "imovel_urbano", "imovel_rural", "real_estate"}


def tapaf_paid_for_item(db, item) -> bool:
    meta = evaluation_meta(item)
    tapaf = meta.get("tapaf") if isinstance(meta.get("tapaf"), dict) else {}
    pauta_id = tapaf.get("pauta_id")
    if not pauta_id:
        return False
    pauta = db.get(PreAnalysisPauta, pauta_id)
    if not pauta:
        return False
    return str(pauta.status or "").upper() == "TAPAF_PAID"
