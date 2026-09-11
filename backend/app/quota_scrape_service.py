"""Sync de inventário via scraping HTML (porte Paulo QuotasUrlCrons — layout TablePress)."""

from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from app.models import QuotaSupplier
HTTP_TIMEOUT = 30.0


def _api_price(raw: Any) -> Decimal:
    text = str(raw if raw is not None else "0").strip()
    if not text:
        return Decimal("0.00")
    if "," in text:
        cleaned = re.sub(r"[^0-9,]", "", text).replace(",", ".")
    else:
        cleaned = re.sub(r"[^0-9.\-]", "", text) or "0"
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0.00")


TABLEPRESS_LAYOUT = {
    "preco": 0,
    "preco_entrada": 1,
    "parcelas": 2,
    "administradas": 4,
    "data_vencimento": 5,
    "status": 6,
}

_ACCENT_FROM = "àáâãäåçèéêëìíîïñòóôõöùüúÿÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÜÚŸ"
_ACCENT_TO = "aaaaaaceeeeiiiinooooouuuyAAAAAACEEEEIIIINOOOOOUUUY"


def parse_scrape_config(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def normalized_scrape_config(raw: str | None) -> dict:
    config = parse_scrape_config(raw)
    layout = str(config.get("layout") or "tablepress").strip().lower()
    if layout != "tablepress":
        raise HTTPException(status_code=422, detail="layout SCRAPE suportado: tablepress.")
    table_id = str(config.get("table_id") or "").strip()
    if not table_id:
        raise HTTPException(status_code=422, detail="scrape_config.table_id obrigatório (ex.: tablepress-tab-imoveis).")
    category = str(config.get("category") or "REAL_ESTATE").strip().upper()
    if category not in {"REAL_ESTATE", "VEHICLE"}:
        raise HTTPException(status_code=422, detail="scrape_config.category deve ser REAL_ESTATE ou VEHICLE.")
    return {"layout": layout, "table_id": table_id, "category": category}


def _without_accents(text: str) -> str:
    table = {ord(a): b for a, b in zip(_ACCENT_FROM, _ACCENT_TO, strict=False)}
    return text.translate(table)


def _parcela_split(parcela: str) -> list[str]:
    return re.split(r"x", parcela, flags=re.IGNORECASE)


def _parcelas_com_valor(parcelas: str) -> bool:
    for chunk in str(parcelas or "").split("+"):
        parts = _parcela_split(chunk.strip())
        try:
            value = _api_price(parts[1] if len(parts) > 1 else "0")
        except Exception:
            return False
        if value <= 0:
            return False
    return bool(str(parcelas or "").strip())


def _sum_parcelas(parcelas_txt: str) -> tuple[int, Decimal]:
    total_qty = 0
    total_value = Decimal("0")
    for chunk in str(parcelas_txt or "").split("+"):
        parts = _parcela_split(chunk.strip())
        qty = int(re.sub(r"\D", "", parts[0] or "0") or 0)
        total_qty += qty
        total_value += _api_price(parts[1] if len(parts) > 1 else "0")
    return total_qty, total_value


def _table_rows(html: str, table_id: str) -> list[dict[str, Any]]:
    if not (html or "").strip():
        return []
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find(id=table_id)
    if not node:
        return []
    tbody = node if node.name and node.name.lower() == "tbody" else node.find("tbody")
    if not tbody:
        return []
    rows: list[dict[str, Any]] = []
    for tr in tbody.find_all("tr"):
        cells = [re.sub(r"\s+", " ", td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        checkbox = "nenhum"
        for input_tag in tr.find_all("input"):
            if str(input_tag.get("type") or "").lower() != "checkbox":
                continue
            checkbox = "travado" if input_tag.has_attr("disabled") else "livre"
            break
        rows.append({"cells": cells, "checkbox": checkbox})
    return rows


def _row_available(cells: list[str]) -> bool:
    status = str(cells[TABLEPRESS_LAYOUT["status"]] if len(cells) > TABLEPRESS_LAYOUT["status"] else "").strip()
    return status == ""


def _row_to_payload(cells: list[str], *, category: str) -> dict[str, Any] | None:
    credit = _api_price(cells[TABLEPRESS_LAYOUT["preco"]] if len(cells) > TABLEPRESS_LAYOUT["preco"] else 0)
    entrada = _api_price(cells[TABLEPRESS_LAYOUT["preco_entrada"]] if len(cells) > TABLEPRESS_LAYOUT["preco_entrada"] else 0)
    parcelas_txt = str(cells[TABLEPRESS_LAYOUT["parcelas"]] if len(cells) > TABLEPRESS_LAYOUT["parcelas"] else "").strip()
    adm = str(cells[TABLEPRESS_LAYOUT["administradas"]] if len(cells) > TABLEPRESS_LAYOUT["administradas"] else "").strip()
    due_raw = str(cells[TABLEPRESS_LAYOUT["data_vencimento"]] if len(cells) > TABLEPRESS_LAYOUT["data_vencimento"] else "").strip()

    if credit <= 0 or not adm or not _parcelas_com_valor(parcelas_txt):
        return None

    qty, parcela = _sum_parcelas(parcelas_txt)
    parcel_qty_parts = []
    for chunk in parcelas_txt.split("+"):
        parts = _parcela_split(chunk.strip())
        parcel_qty_parts.append(re.sub(r"\D", "", parts[0] or "0") or "0")
    external_ref = _without_accents(f"{credit:.2f}-{'_'.join(parcel_qty_parts)}-{adm}")

    payload: dict[str, Any] = {
        "id": external_ref[:120],
        "valor_credito": str(credit),
        "entrada": str(entrada),
        "valor_parcela": str(parcela),
        "parcelas": qty,
        "administradora": adm,
        "categoria": "Imóvel" if category == "REAL_ESTATE" else "Veículo",
        "reserva": "disponivel",
    }
    if due_raw:
        payload["date_vencimento"] = due_raw
    return payload


def fetch_scrape_payload(supplier: QuotaSupplier) -> list[dict]:
    url = (supplier.api_url or "").strip()
    if not url:
        raise HTTPException(status_code=422, detail="Configure api_url do fornecedor antes de sincronizar.")
    config = normalized_scrape_config(supplier.scrape_config_json)
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao consultar página do fornecedor: {exc}") from exc

    rows: list[dict] = []
    for row in _table_rows(html, config["table_id"]):
        cells = row.get("cells") or []
        if not isinstance(cells, list) or not _row_available(cells):
            continue
        payload = _row_to_payload(cells, category=config["category"])
        if payload:
            rows.append(payload)
    return rows
