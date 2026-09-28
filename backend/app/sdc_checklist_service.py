"""Checklists SDC por categoria de bem + tipo de operação (configurável por organização)."""

from __future__ import annotations

import json
from json import loads as json_loads

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SdcChecklistConfig

ASSET_CATEGORIES = frozenset({"veiculo", "imovel_urbano", "imovel_rural", "maquina_agricola"})
OPERATION_TYPES = frozenset({"PF_PF", "PF_PJ", "PJ_PJ", "PJ_PF"})

ASSET_CATEGORY_LABELS = {
    "veiculo": "Veículo",
    "imovel_urbano": "Imóvel urbano",
    "imovel_rural": "Imóvel rural",
    "maquina_agricola": "Máquina agrícola",
}

OPERATION_TYPE_LABELS = {
    "PF_PF": "PF comprando de PF",
    "PF_PJ": "PF comprando de PJ",
    "PJ_PJ": "PJ comprando de PJ",
    "PJ_PF": "PJ comprando de PF",
}

DOCS_CLIENT_BASE = [
    {"code": "RG_CPF", "label": "RG e CPF (ou CNH) — proponente"},
    {"code": "COMPROVANTE_RENDA", "label": "Comprovante de renda / faturamento (últimos 3 meses)"},
    {"code": "COMPROVANTE_ENDERECO", "label": "Comprovante de endereço do proponente"},
]
DOCS_COUNTERPARTY_PJ = [
    {"code": "CONTRATO_SOCIAL", "label": "Contrato social / alterações consolidadas (PJ vendedor ou comprador)"},
    {"code": "QSA_REPRESENTANTES", "label": "QSA / procuração dos representantes legais (PJ)"},
]
DOCS_BUYER_PJ = [
    {"code": "CONTRATO_SOCIAL_COMPRADOR", "label": "Contrato social / alterações — PJ comprador"},
    {"code": "QSA_COMPRADOR", "label": "QSA / representantes legais — PJ comprador"},
]
DOCS_IMOVEL_URBANO = [
    {"code": "MATRICULA_ENOTARIADO", "label": "Matrícula atualizada (e-notariado)"},
    {"code": "LAUDO_AVALIACAO", "label": "Laudo de avaliação do imóvel em garantia"},
    {"code": "IPTU_IPTUR", "label": "IPTU / carnê do imóvel (exercício vigente)"},
    {"code": "SERASA", "label": "Consulta Serasa / restrições cadastrais"},
    {"code": "BACEN", "label": "Consulta Bacen (SCR)"},
]
DOCS_IMOVEL_RURAL = [
    {"code": "MATRICULA_CCIR", "label": "Matrícula / CCIR / CAR (imóvel rural)"},
    {"code": "LAUDO_AVALIACAO", "label": "Laudo de avaliação do imóvel rural"},
    {"code": "ITR", "label": "ITR / declaração do imóvel rural"},
    {"code": "SERASA", "label": "Consulta Serasa / restrições cadastrais"},
    {"code": "BACEN", "label": "Consulta Bacen (SCR)"},
]
DOCS_VEICULO = [
    {"code": "CRLV", "label": "CRLV (DETRAN — consulta prevalece)"},
    {"code": "FIPE_MOLICAR", "label": "Tabela FIPE ou Molicar"},
    {"code": "LAUDO_AVALIACAO", "label": "Laudo de avaliação do veículo"},
    {"code": "COMPROVANTE_QUITACAO", "label": "Comprovante de quitação / ausência de gravame"},
    {"code": "SERASA", "label": "Consulta Serasa / restrições cadastrais"},
    {"code": "BACEN", "label": "Consulta Bacen (SCR)"},
]
DOCS_MAQUINA = [
    {"code": "NOTA_FISCAL_MAQUINA", "label": "Nota fiscal / registro da máquina ou equipamento"},
    {"code": "LAUDO_AVALIACAO", "label": "Laudo de avaliação do equipamento"},
    {"code": "SERASA", "label": "Consulta Serasa / restrições cadastrais"},
    {"code": "BACEN", "label": "Consulta Bacen (SCR)"},
]


def normalize_asset_category(asset_type: str | None) -> str:
    raw = (asset_type or "").strip().lower()
    mapping = {
        "imovel": "imovel_urbano",
        "casa": "imovel_urbano",
        "lote": "imovel_urbano",
        "imovel_comercial": "imovel_urbano",
        "apartamento": "imovel_urbano",
        "imovel_rural": "imovel_rural",
        "veiculo_leve": "veiculo",
        "veiculo_pesado": "veiculo",
        "carro": "veiculo",
        "caminhao": "veiculo",
        "maquina": "maquina_agricola",
        "maquina_rural": "maquina_agricola",
    }
    if raw in ASSET_CATEGORIES:
        return raw
    return mapping.get(raw, "imovel_urbano")


def normalize_operation_type(value: str | None, person_type: str | None = None) -> str:
    raw = (value or "").strip().upper()
    if raw in OPERATION_TYPES:
        return raw
    pt = (person_type or "PF").strip().upper()
    return "PJ_PJ" if pt == "PJ" else "PF_PF"


def _asset_block(category: str) -> list[dict]:
    if category == "imovel_rural":
        return list(DOCS_IMOVEL_RURAL)
    if category == "veiculo":
        return list(DOCS_VEICULO)
    if category == "maquina_agricola":
        return list(DOCS_MAQUINA)
    return list(DOCS_IMOVEL_URBANO)


def default_checklist_items(asset_category: str, operation_type: str) -> list[dict]:
    category = normalize_asset_category(asset_category)
    op = normalize_operation_type(operation_type)
    rows: list[dict] = list(DOCS_CLIENT_BASE)
    if op.startswith("PJ_"):
        rows.extend(DOCS_BUYER_PJ)
    if op.endswith("_PJ"):
        rows.extend(DOCS_COUNTERPARTY_PJ)
    rows.extend(_asset_block(category))
    dedup: dict[str, dict] = {}
    for row in rows:
        dedup[row["code"]] = row
    return list(dedup.values())


def get_checklist_config_row(
    db: Session,
    organization_id: str,
    asset_category: str,
    operation_type: str,
) -> SdcChecklistConfig | None:
    category = normalize_asset_category(asset_category)
    op = normalize_operation_type(operation_type)
    return db.scalar(
        select(SdcChecklistConfig).where(
            SdcChecklistConfig.organization_id == organization_id,
            SdcChecklistConfig.asset_category == category,
            SdcChecklistConfig.operation_type == op,
        )
    )


def resolve_required_docs(
    db: Session | None,
    organization_id: str | None,
    *,
    asset_type: str,
    operation_type: str | None = None,
    person_type: str | None = None,
) -> list[dict]:
    category = normalize_asset_category(asset_type)
    op = normalize_operation_type(operation_type, person_type)
    if db and organization_id:
        row = get_checklist_config_row(db, organization_id, category, op)
        if row and row.items_json:
            try:
                items = json_loads(row.items_json)
                if isinstance(items, list) and items:
                    return [{"code": str(i["code"]), "label": str(i["label"])} for i in items if i.get("code")]
            except (TypeError, ValueError, KeyError):
                pass
    return default_checklist_items(category, op)


def list_checklist_configs(db: Session, organization_id: str) -> list[dict]:
    rows = list(
        db.scalars(
            select(SdcChecklistConfig).where(SdcChecklistConfig.organization_id == organization_id)
        )
    )
    by_key = {(r.asset_category, r.operation_type): r for r in rows}
    out: list[dict] = []
    for category in sorted(ASSET_CATEGORIES):
        for op in sorted(OPERATION_TYPES):
            row = by_key.get((category, op))
            items = default_checklist_items(category, op)
            if row and row.items_json:
                try:
                    parsed = json_loads(row.items_json)
                    if isinstance(parsed, list) and parsed:
                        items = parsed
                except (TypeError, ValueError):
                    pass
            out.append(
                {
                    "asset_category": category,
                    "asset_category_label": ASSET_CATEGORY_LABELS[category],
                    "operation_type": op,
                    "operation_type_label": OPERATION_TYPE_LABELS[op],
                    "items": items,
                    "customized": row is not None,
                    "id": row.id if row else None,
                }
            )
    return out


def save_checklist_config(
    db: Session,
    organization_id: str,
    *,
    asset_category: str,
    operation_type: str,
    items: list[dict],
) -> SdcChecklistConfig:
    category = normalize_asset_category(asset_category)
    op = normalize_operation_type(operation_type)
    if category not in ASSET_CATEGORIES or op not in OPERATION_TYPES:
        raise ValueError("Categoria ou tipo de operação inválido")
    cleaned = [{"code": str(i["code"]).strip().upper(), "label": str(i["label"]).strip()} for i in items if i.get("code")]
    row = get_checklist_config_row(db, organization_id, category, op)
    payload = json.dumps(cleaned, ensure_ascii=False)
    if not row:
        row = SdcChecklistConfig(
            organization_id=organization_id,
            asset_category=category,
            operation_type=op,
            items_json=payload,
        )
        db.add(row)
    else:
        row.items_json = payload
    db.flush()
    return row
