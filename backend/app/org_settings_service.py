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

def _field(
    key: str,
    label: str,
    *,
    hint: str = "",
) -> dict[str, str]:
    row: dict[str, str] = {"key": key, "label": label}
    if hint:
        row["hint"] = hint
    return row


SETTING_GROUPS: dict[str, list[dict[str, str]]] = {
    "info": [
        _field("phone", "Telefone", hint="Exibido no site público, rodapé e canais de contato."),
        _field("email_1", "E-mail", hint="E-mail institucional de contato."),
        _field("cnpj", "CNPJ"),
        _field("razao_social", "Razão social"),
        _field("whatsapp", "WhatsApp", hint="Número com DDD (apenas dígitos ou formatado)."),
        _field("whatsapp_code", "WhatsApp (código país)", hint="Ex.: 55 para Brasil."),
        _field("whatsapp_txt", "WhatsApp (texto padrão)", hint="Mensagem pré-preenchida ao abrir o WhatsApp."),
        _field("opening_hours", "Horário de atendimento"),
        _field("facebook", "Facebook", hint="URL completa do perfil."),
        _field("youtube", "Youtube", hint="URL do canal ou vídeo institucional."),
        _field("instagram", "Instagram"),
        _field("tiktok", "Tiktok"),
        _field("linkedin", "Linkedin"),
        _field(
            "txt_cadastro",
            "Mensagem para clientes",
            hint="Texto exibido em cadastros / área do cliente (HTML simples permitido).",
        ),
        _field(
            "txt_fornecedores",
            "Mensagem para fornecedores",
            hint="Texto exibido no portal e fluxos de fornecedor.",
        ),
    ],
    "payments": [
        _field(
            "platform_commission_percent",
            "Taxa da plataforma Letter (%)",
            hint=(
                "Percentual global da LETTER na liberação de comissão do marketplace "
                "(legado x_settings «price»). Usado quando o fornecedor não tem «% plataforma» no cadastro. "
                "Não é markup do fornecedor (Fornecedores) nem comissão da rede MMN (menu Rede e comissões)."
            ),
        ),
        _field(
            "min_withdrawal_amount",
            "Mínimo para saque (R$)",
            hint="Valor mínimo para parceiro/fornecedor solicitar saque (legado price_min_saque).",
        ),
        _field(
            "bank_display_mode",
            "Modo carteira parceiro",
            hint="legacy = extrato de ganhos interno; asaas = conta digital Asaas (quando habilitado).",
        ),
    ],
    "templates": [
        _field(
            "marketplace_contract_html",
            "Contrato marketplace (HTML)",
            hint="Minuta exibida no chat Nina e cadastros. Cole o HTML aqui ou use «Importar SQL legado».",
        ),
        _field(
            "contract_template_html",
            "Contrato geral (HTML — legado)",
            hint="Template antigo do editor menu 87; mantido para compatibilidade.",
        ),
        _field("venda_direta_html", "Texto venda direta (HTML)"),
        _field("venda_direta_robo_html", "Texto venda direta robô (HTML)"),
        _field(
            "chat_robo_video_url",
            "Vídeo explicativo (URL)",
            hint="YouTube ou Vimeo — aparece no robô de venda direta e no chat.",
        ),
        _field("sdc_flow_html", "Texto fluxo SDC (HTML)"),
    ],
    "meta": [
        _field("name_site", "Nome do site", hint="Nome exibido em títulos e identidade pública."),
        _field(
            "meta_title",
            "Meta title (SEO)",
            hint="Título sugerido para buscadores (Google). Aparece na aba do navegador e em resultados de busca.",
        ),
        _field(
            "meta_description",
            "Meta description (SEO)",
            hint="Resumo curto da página para buscadores (até ~160 caracteres).",
        ),
    ],
}

SETTING_GROUP_META: dict[str, dict[str, str]] = {
    "info": {
        "title": "Informações do site",
        "summary": (
            "Dados de contato e redes sociais da LETTER no site público, rodapé, WhatsApp e mensagens "
            "de boas-vindas. Corresponde ao bloco «Informações» do admin legado (menu interno id 11) — "
            "não é menu de navegação do painel."
        ),
    },
    "payments": {
        "title": "Pagamentos e taxa Letter",
        "summary": (
            "Ajustes financeiros globais do marketplace. A taxa da plataforma (%) aqui é única e vale como "
            "fallback na liberação de comissão. As outras comissões são configuradas em outros lugares: "
            "markup e % plataforma por fornecedor em «Fornecedores»; repasse MMN (rede, níveis, retenção) "
            "em «Rede e comissões» (/modules/mmn); comissão do parceiro na venda segue as regras do produto "
            "e do MMN, não este campo."
        ),
    },
    "templates": {
        "title": "Contratos e textos de fluxo",
        "summary": (
            "Templates em HTML usados pelo sistema ao gerar contratos e textos nos fluxos (marketplace, "
            "venda direta, SDC). Não há upload de Word/PDF nesta tela: cole o HTML formatado ou importe "
            "do SQL legado. Os contratos que você enviou em .docx precisam ser convertidos para HTML "
            "(equipe LETTER ou importação legada) antes de aparecerem aqui. E-mails transacionais ficam em "
            "«Textos e e-mails»."
        ),
    },
    "meta": {
        "title": "Meta tags (SEO)",
        "summary": (
            "Meta tags são informações para buscadores (Google): título e descrição da página pública. "
            "Não alteram o contrato nem comissões; melhoram como o site aparece nos resultados de busca."
        ),
    },
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


def _merge_import_setting_value(current: str, incoming: str) -> str:
    """Legado repete chaves (ex.: whatsapp_text + whatsapp_txt); prioriza valor não vazio."""
    if incoming.strip():
        return incoming
    return current


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
    return {"groups": SETTING_GROUPS, "values": values, "group_meta": SETTING_GROUP_META}


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
    by_key: dict[str, OrganizationSetting] = {
        row.field_key: row
        for row in db.scalars(
            select(OrganizationSetting).where(OrganizationSetting.organization_id == organization_id)
        )
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
        existing = by_key.get(key)
        if existing:
            existing.value = _merge_import_setting_value(str(existing.value or ""), value)
            updated += 1
        else:
            item = OrganizationSetting(organization_id=organization_id, field_key=key, value=value)
            db.add(item)
            by_key[key] = item
            created += 1
    db.flush()
    return {"created": created, "updated": updated, "total_legacy": len(rows)}
