"""Checklists Flash Capital por tipo de operação (imóvel próprio vs terceiro)."""

from __future__ import annotations

import json
from json import loads as json_loads

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FlashChecklistConfig

ASSET_CATEGORY = "REAL_ESTATE"
OPERATION_TYPES = frozenset({"IMOVEL_PROPRIO", "IMOVEL_TERCEIRO"})

OPERATION_TYPE_LABELS = {
    "IMOVEL_PROPRIO": "Imóvel próprio",
    "IMOVEL_TERCEIRO": "Imóvel de terceiro",
}

def _normalize_checklist_item(raw: dict) -> dict:
    return {
        "code": str(raw.get("code") or "").strip(),
        "label": str(raw.get("label") or "").strip(),
        "required": bool(raw.get("required", True)),
    }


DOCS_BASE = [
    {"code": "CONTRATO_SOCIAL", "label": "Contrato social / alterações consolidadas (PJ tomador)", "required": True},
    {"code": "QSA_REPRESENTANTES", "label": "QSA / procuração dos representantes legais"},
    {"code": "RG_CPF_REPRESENTANTES", "label": "RG e CPF (ou CNH) dos representantes legais"},
    {"code": "COMPROVANTE_RENDA", "label": "Comprovante de renda / faturamento (últimos 3 meses)"},
    {"code": "MATRICULA_ENOTARIADO", "label": "Matrícula atualizada (e-notariado)"},
    {"code": "LAUDO_AVALIACAO", "label": "Laudo de avaliação do imóvel"},
    {"code": "FOTOS_IMOVEL", "label": "Fotos do imóvel (fachada, ambientes internos e áreas comuns)"},
    {"code": "SERASA", "label": "Consulta Serasa / restrições cadastrais"},
    {"code": "BACEN", "label": "Consulta Bacen (SCR)", "required": True},
]
DOCS_TERCEIRO_EXTRA = [
    {"code": "RG_CPF_PROPRIETARIO", "label": "RG e CPF (ou CNH) do proprietário do imóvel (terceiro)", "required": True},
    {"code": "COMPROVANTE_ENDERECO_PROPRIETARIO", "label": "Comprovante de endereço do proprietário (terceiro)", "required": True},
    {
        "code": "AUTORIZACAO_ASSINATURA_TERCEIRO",
        "label": "Autorização / dados para assinatura do contrato pelo proprietário",
        "required": True,
    },
]


def normalize_flash_operation_type(value: str | None) -> str:
    raw = (value or "").strip().upper()
    if raw in {"IMOVEL_TERCEIRO", "TERCEIRO", "THIRD_PARTY", "IMOVEL_DE_TERCEIRO"}:
        return "IMOVEL_TERCEIRO"
    return "IMOVEL_PROPRIO"


def default_checklist_items(operation_type: str) -> list[dict]:
    op = normalize_flash_operation_type(operation_type)
    items = [_normalize_checklist_item(x) for x in DOCS_BASE]
    if op == "IMOVEL_TERCEIRO":
        items.extend(_normalize_checklist_item(x) for x in DOCS_TERCEIRO_EXTRA)
    return items


def get_checklist_config_row(db: Session, organization_id: str, operation_type: str) -> FlashChecklistConfig | None:
    op = normalize_flash_operation_type(operation_type)
    return db.scalar(
        select(FlashChecklistConfig).where(
            FlashChecklistConfig.organization_id == organization_id,
            FlashChecklistConfig.asset_category == ASSET_CATEGORY,
            FlashChecklistConfig.operation_type == op,
        )
    )


def resolve_required_docs(
    db: Session,
    organization_id: str,
    *,
    operation_type: str | None,
    asset_category: str | None = None,
) -> list[dict]:
    _ = asset_category
    op = normalize_flash_operation_type(operation_type)
    row = get_checklist_config_row(db, organization_id, op)
    if row and row.items_json:
        try:
            parsed = json_loads(row.items_json)
            if isinstance(parsed, list) and parsed:
                return [
                    _normalize_checklist_item(i)
                    for i in parsed
                    if isinstance(i, dict) and i.get("code")
                ]
        except (TypeError, ValueError, KeyError):
            pass
    return default_checklist_items(op)


def list_checklist_configs(db: Session, organization_id: str) -> list[dict]:
    rows = list(
        db.scalars(
            select(FlashChecklistConfig).where(FlashChecklistConfig.organization_id == organization_id)
        )
    )
    by_key = {(r.asset_category, r.operation_type): r for r in rows}
    out: list[dict] = []
    for op in sorted(OPERATION_TYPES):
        row = by_key.get((ASSET_CATEGORY, op))
        if row:
            try:
                items = json_loads(row.items_json or "[]")
            except (TypeError, ValueError):
                items = []
            if not isinstance(items, list) or not items:
                items = default_checklist_items(op)
        else:
            items = default_checklist_items(op)
        out.append(
            {
                "asset_category": ASSET_CATEGORY,
                "asset_category_label": "Imóvel (Flash Capital)",
                "operation_type": op,
                "operation_type_label": OPERATION_TYPE_LABELS[op],
                "items": items,
                "customized": row is not None,
            }
        )
    return out


def save_checklist_config(
    db: Session,
    organization_id: str,
    *,
    operation_type: str,
    items: list[dict],
) -> None:
    op = normalize_flash_operation_type(operation_type)
    if op not in OPERATION_TYPES:
        raise ValueError("Tipo de operação inválido")
    cleaned = [_normalize_checklist_item(i) for i in items if isinstance(i, dict)]
    cleaned = [i for i in cleaned if i["code"] and i["label"]]
    if not cleaned:
        raise ValueError("Informe ao menos um item")
    row = get_checklist_config_row(db, organization_id, op)
    payload = json.dumps(cleaned, ensure_ascii=False)
    if row:
        row.items_json = payload
    else:
        db.add(
            FlashChecklistConfig(
                organization_id=organization_id,
                asset_category=ASSET_CATEGORY,
                operation_type=op,
                items_json=payload,
            )
        )
    db.flush()
