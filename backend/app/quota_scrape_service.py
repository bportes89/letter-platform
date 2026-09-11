"""Sync de inventário via scraping HTML (porte Paulo QuotasUrlCrons)."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import certifi
import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from app.models import QuotaSupplier

HTTP_TIMEOUT = 30.0
CERTS_DIR = Path(__file__).resolve().parent.parent / "resources" / "certs"
SUPPORTED_LAYOUTS = frozenset({"tablepress", "contempladosp", "cartascontempladas"})

LAYOUTS: dict[str, dict[str, Any]] = {
    "tablepress": {
        "regra": "status_vazio",
        "preco": 0,
        "preco_entrada": 1,
        "parcelas": 2,
        "administradas": 4,
        "data_vencimento": 5,
        "status": 6,
        "chave_entrada": False,
    },
    "contempladosp": {
        "regra": "checkbox",
        "preco": 1,
        "preco_entrada": 2,
        "parcelas": 3,
        "administradas": 4,
        "chave_entrada": True,
    },
    "cartascontempladas": {
        "regra": "checkbox",
        "administradas": 3,
        "preco": 4,
        "preco_entrada": 5,
        "parcelas_qtd": 6,
        "parcelas_valor": 7,
        "data_vencimento": 8,
        "chave_entrada": True,
    },
}

_ACCENT_FROM = "àáâãäåçèéêëìíîïñòóôõöùüúÿÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÜÚŸ"
_ACCENT_TO = "aaaaaaceeeeiiiinooooouuuyAAAAAACEEEEIIIINOOOOOUUUY"


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


def parse_scrape_config(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def normalized_scrape_config(raw: str | None) -> dict:
    config = parse_scrape_config(raw)
    layout = str(config.get("layout") or "tablepress").strip().lower()
    if layout not in SUPPORTED_LAYOUTS:
        raise HTTPException(
            status_code=422,
            detail="layout SCRAPE suportado: tablepress, contempladosp, cartascontempladas.",
        )
    table_id = str(config.get("table_id") or "").strip()
    if not table_id:
        raise HTTPException(
            status_code=422,
            detail="scrape_config.table_id obrigatório (ex.: tablepress-tab-imoveis, tbCotasGerais, listaCotas).",
        )
    category = str(config.get("category") or "REAL_ESTATE").strip().upper()
    if category not in {"REAL_ESTATE", "VEHICLE"}:
        raise HTTPException(status_code=422, detail="scrape_config.category deve ser REAL_ESTATE ou VEHICLE.")
    ca = str(config.get("ca") or "").strip() or None
    if ca and ("/" in ca or ca.startswith("..")):
        raise HTTPException(status_code=422, detail="scrape_config.ca inválido.")
    return {"layout": layout, "table_id": table_id, "category": category, "ca": ca}


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


def _parcelas_text(cells: list[str], layout: dict[str, Any]) -> str:
    if "parcelas" in layout:
        return str(cells[layout["parcelas"]] if len(cells) > layout["parcelas"] else "").strip()
    qtd = str(cells[layout["parcelas_qtd"]] if len(cells) > layout["parcelas_qtd"] else "").strip()
    valor = str(cells[layout["parcelas_valor"]] if len(cells) > layout["parcelas_valor"] else "").strip()
    if re.search(r"x", valor, flags=re.IGNORECASE):
        return valor
    return f"{qtd} x {valor}".strip()


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


def _row_available(row: dict[str, Any], layout: dict[str, Any]) -> bool:
    if layout.get("regra") == "checkbox":
        return row.get("checkbox") == "livre"
    cells = row.get("cells") or []
    status_idx = layout.get("status")
    if status_idx is None:
        return False
    status = str(cells[status_idx] if len(cells) > status_idx else "").strip()
    return status == ""


def _build_external_ref(
    credit: Decimal,
    entrada: Decimal,
    parcelas_txt: str,
    adm: str,
    *,
    chave_entrada: bool,
) -> str:
    parcel_qty_parts = []
    for chunk in parcelas_txt.split("+"):
        parts = _parcela_split(chunk.strip())
        parcel_qty_parts.append(re.sub(r"\D", "", parts[0] or "0") or "0")
    ref = f"{credit:.2f}-{'_'.join(parcel_qty_parts)}-{adm}"
    if chave_entrada:
        ref += f"-{entrada:.2f}"
    return _without_accents(ref)[:120]


def _row_to_payload(cells: list[str], *, category: str, layout: dict[str, Any]) -> dict[str, Any] | None:
    credit = _api_price(cells[layout["preco"]] if len(cells) > layout["preco"] else 0)
    entrada = _api_price(cells[layout["preco_entrada"]] if len(cells) > layout["preco_entrada"] else 0)
    parcelas_txt = _parcelas_text(cells, layout)
    adm = str(cells[layout["administradas"]] if len(cells) > layout["administradas"] else "").strip()
    due_idx = layout.get("data_vencimento")
    due_raw = (
        str(cells[due_idx] if due_idx is not None and len(cells) > due_idx else "").strip()
        if due_idx is not None
        else ""
    )

    if credit <= 0 or not adm or not _parcelas_com_valor(parcelas_txt):
        return None

    qty, parcela = _sum_parcelas(parcelas_txt)
    external_ref = _build_external_ref(
        credit,
        entrada,
        parcelas_txt,
        adm,
        chave_entrada=bool(layout.get("chave_entrada")),
    )

    payload: dict[str, Any] = {
        "id": external_ref,
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


def _tls_verify_bundle(ca: str | None) -> bool | str:
    if not ca:
        return True
    extra = CERTS_DIR / ca
    if not extra.is_file():
        return True
    base = certifi.where()
    bundle = CERTS_DIR / f"ca_{Path(ca).stem}.pem"
    stale = (
        not bundle.is_file()
        or bundle.stat().st_mtime < extra.stat().st_mtime
        or (os.path.isfile(base) and bundle.stat().st_mtime < os.path.getmtime(base))
    )
    if stale:
        tmp = bundle.with_suffix(f".{os.getpid()}.tmp")
        with open(base, encoding="utf-8") as base_file:
            base_text = base_file.read()
        with open(extra, encoding="utf-8") as extra_file:
            extra_text = extra_file.read()
        tmp.write_text(f"{base_text}\n{extra_text}", encoding="utf-8")
        tmp.replace(bundle)
    return str(bundle)


def fetch_scrape_payload(supplier: QuotaSupplier) -> list[dict]:
    url = (supplier.api_url or "").strip()
    if not url:
        raise HTTPException(status_code=422, detail="Configure api_url do fornecedor antes de sincronizar.")
    config = normalized_scrape_config(supplier.scrape_config_json)
    layout = LAYOUTS[config["layout"]]
    verify = _tls_verify_bundle(config.get("ca"))
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True, verify=verify) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao consultar página do fornecedor: {exc}") from exc

    rows: list[dict] = []
    for row in _table_rows(html, config["table_id"]):
        cells = row.get("cells") or []
        if not isinstance(cells, list) or not _row_available(row, layout):
            continue
        payload = _row_to_payload(cells, category=config["category"], layout=layout)
        if payload:
            rows.append(payload)
    return rows
