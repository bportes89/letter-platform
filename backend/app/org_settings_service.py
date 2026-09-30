"""Configurações globais (legado x_settings / menus 11, 87, 1033–1038)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cms_text_service import decode_z_text_value
from app.legacy_export_service import DEFAULT_SQL
from app.legacy_sql_parser import load_table
from app.models import OrganizationSetting, User

DEFAULT_LEGACY_SQL = DEFAULT_SQL

SETTING_GROUPS: dict[str, list[dict[str, str]]] = {
    "info": [
        {"key": "phone", "label": "Telefone"},
        {"key": "email_1", "label": "E-mail"},
        {"key": "cnpj", "label": "CNPJ"},
        {"key": "razao_social", "label": "Razão social"},
        {"key": "whatsapp", "label": "WhatsApp"},
        {"key": "whatsapp_code", "label": "WhatsApp (código país)"},
        {"key": "whatsapp_txt", "label": "WhatsApp (texto padrão)"},
        {"key": "opening_hours", "label": "Horário de atendimento"},
        {"key": "facebook", "label": "Facebook"},
        {"key": "youtube", "label": "Youtube"},
        {"key": "instagram", "label": "Instagram"},
        {"key": "tiktok", "label": "Tiktok"},
        {"key": "linkedin", "label": "Linkedin"},
        {"key": "txt_cadastro", "label": "Mensagem para clientes"},
        {"key": "txt_fornecedores", "label": "Mensagem para fornecedores"},
    ],
    "payments": [
        {"key": "platform_commission_percent", "label": "Comissão do site (%)"},
        {"key": "min_withdrawal_amount", "label": "Mínimo para saque (R$)"},
        {
            "key": "bank_display_mode",
            "label": "Bank parceiro: legacy (ganhos) ou asaas (conta digital)",
        },
    ],
    "templates": [
        {"key": "marketplace_contract_html", "label": "Contrato marketplace (chat/cadastros)"},
        {"key": "contract_template_html", "label": "Contrato (editor legado menu 87)"},
        {"key": "venda_direta_html", "label": "Texto venda direta"},
        {"key": "venda_direta_robo_html", "label": "Texto venda direta robô"},
        {"key": "chat_robo_video_url", "label": "Vídeo explicativo (URL YouTube/Vimeo) — robô chat"},
        {"key": "sdc_flow_html", "label": "Texto fluxo SDC"},
    ],
    "meta": [
        {"key": "name_site", "label": "Nome do site"},
        {"key": "meta_title", "label": "Meta title"},
        {"key": "meta_description", "label": "Meta description"},
    ],
}

PUBLIC_SITE_KEYS = frozenset(
    {
        "phone",
        "email_1",
        "whatsapp",
        "whatsapp_code",
        "whatsapp_txt",
        "opening_hours",
        "facebook",
        "youtube",
        "instagram",
        "tiktok",
        "linkedin",
        "razao_social",
        "cnpj",
        "txt_cadastro",
        "txt_fornecedores",
    }
)

LEGACY_FIELD_ALIASES = {
    "price": "platform_commission_percent",
    "price_min_saque": "min_withdrawal_amount",
    "whatsapp_text": "whatsapp_txt",
}


def _all_known_keys() -> set[str]:
    keys: set[str] = set()
    for items in SETTING_GROUPS.values():
        for item in items:
            keys.add(item["key"])
    return keys


def get_setting(db: Session, organization_id: str, field_key: str, default: str = "") -> str:
    row = db.scalar(
        select(OrganizationSetting).where(
            OrganizationSetting.organization_id == organization_id,
            OrganizationSetting.field_key == field_key,
        )
    )
    if not row:
        return default
    return str(row.value or "")


def settings_map(db: Session, organization_id: str) -> dict[str, str]:
    rows = db.scalars(
        select(OrganizationSetting).where(OrganizationSetting.organization_id == organization_id)
    ).all()
    return {row.field_key: str(row.value or "") for row in rows}


def set_settings(db: Session, organization_id: str, payload: dict[str, Any]) -> dict[str, str]:
    known = _all_known_keys()
    for raw_key, raw_value in payload.items():
        key = LEGACY_FIELD_ALIASES.get(str(raw_key), str(raw_key))
        if key not in known and not str(raw_key).startswith("custom_"):
            raise HTTPException(status_code=422, detail=f"Chave de configuração desconhecida: {raw_key}")
        value = "" if raw_value is None else str(raw_value)
        row = db.scalar(
            select(OrganizationSetting).where(
                OrganizationSetting.organization_id == organization_id,
                OrganizationSetting.field_key == key,
            )
        )
        if row:
            row.value = value
        else:
            db.add(OrganizationSetting(organization_id=organization_id, field_key=key, value=value))
    db.flush()
    return settings_map(db, organization_id)


def admin_settings_view(db: Session, user: User) -> dict[str, Any]:
    values = settings_map(db, user.organization_id)
    return {"groups": SETTING_GROUPS, "values": values}


def public_site_info(db: Session, organization_id: str) -> dict[str, str]:
    all_values = settings_map(db, organization_id)
    return {k: all_values.get(k, "") for k in PUBLIC_SITE_KEYS}


def import_legacy_settings(
    db: Session,
    organization_id: str,
    *,
    sql_path: Path | None = None,
) -> dict[str, int]:
    path = sql_path or DEFAULT_LEGACY_SQL
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"SQL legado não encontrado: {path}")
    rows = load_table(path, "x_settings")
    z_rows = load_table(path, "z_text")
    editor_html: dict[str, str] = {}
    for z in z_rows:
        model_key = str(z.get("model_") or "").lower()
        if "x_settings" not in model_key and "xsettings" not in model_key:
            continue
        field = str(z.get("fields") or "")
        if field not in {"editor", "txt"}:
            continue
        legacy_row_id = str(z.get("id_") or "")
        editor_html[legacy_row_id] = decode_z_text_value(z.get("value"))

    created = updated = 0
    template_keys_by_legacy_field = {
        "txt": "contract_template_html",
    }
    for row in rows:
        field = str(row.get("fields") or "").strip()
        if not field:
            continue
        key = LEGACY_FIELD_ALIASES.get(field, field)
        if key not in _all_known_keys() and field not in template_keys_by_legacy_field:
            continue
        if field in template_keys_by_legacy_field:
            key = template_keys_by_legacy_field[field]
        value = str(row.get("value") or "")
        row_id = str(row.get("id") or "")
        if row_id in editor_html and editor_html[row_id]:
            value = editor_html[row_id]
        existing = db.scalar(
            select(OrganizationSetting).where(
                OrganizationSetting.organization_id == organization_id,
                OrganizationSetting.field_key == key,
            )
        )
        if existing:
            existing.value = value
            updated += 1
        else:
            db.add(OrganizationSetting(organization_id=organization_id, field_key=key, value=value))
            created += 1
    db.flush()
    return {"created": created, "updated": updated, "total_legacy": len(rows)}
