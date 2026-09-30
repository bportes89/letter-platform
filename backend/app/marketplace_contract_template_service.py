"""Template e renderização do contrato Marketplace (chat / cadastros)."""

from __future__ import annotations

import html
import re
from html import unescape

from sqlalchemy.orm import Session

from app.models import Lead
from app.storage_service import get_storage

RESERVE_TTL = 30

INCOME_PROOF_OPTIONS = {
    "holerite": "Holerite",
    "ir": "IR",
    "decore": "Decore",
    "extrato": "Extrato",
}


def _digits(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _brl(value) -> str:
    try:
        num = float(value)
    except (TypeError, ValueError):
        num = 0.0
    return f"R$ {num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

TEMPLATE_STORAGE_SUFFIX = "config/marketplace-contract-template.html"

# Campos substituídos pelo sistema — não devem ser alterados manualmente no HTML salvo.
LOCKED_FIELD_LABELS = {
    "nome": "Nome / razão social",
    "documento": "CPF/CNPJ",
    "profissao": "Profissão / ramo",
    "renda": "Renda / faturamento",
    "comprovacao_renda": "Comprovação de renda",
    "endereco": "Endereço",
    "email": "E-mail",
    "whatsapp": "WhatsApp",
    "administradora": "Administradora(s)",
    "valor_credito": "Valor do crédito",
    "valor_entrada": "Valor da entrada",
    "parcelas": "Parcelas",
    "data_extenso": "Data",
    "empresa_dados": "Dados LETTER",
    "empresa_chave_pix": "Chave PIX",
}

DEFAULT_MARKETPLACE_CONTRACT_TEMPLATE = """
<p><strong>LETTER BANK LTDA</strong> — CNPJ 41.163.819/0001-57<br/>
Representada por Sr. Paulo Stutz Netto Souza — foro em Nanuque/MG</p>
<p><strong>Termo de intermediação de cota contemplada</strong></p>
<p><strong>Contratante:</strong> {nome}<br/>
<strong>Documento:</strong> {documento}<br/>
<strong>{profissao_label}:</strong> {profissao}<br/>
<strong>{renda_label}:</strong> {renda}<br/>
<strong>Comprovação de renda:</strong> {comprovacao_renda}<br/>
<strong>Endereço:</strong> {endereco}<br/>
<strong>E-mail:</strong> {email} · <strong>WhatsApp:</strong> {whatsapp}</p>
<p><strong>Objeto:</strong> intermediação de cota(s) contemplada(s).<br/>
Administradora(s): {administradora}<br/>
Crédito: {valor_credito} · Entrada: {valor_entrada}<br/>
Parcelas: {parcelas}<br/>
Reserva das cotas: {reserva_minutos} minutos a partir da escolha.</p>
<p>PIX de referência LETTER: <strong>{empresa_chave_pix}</strong></p>
<p>Ao aceitar, o contratante confirma ciência das condições de intermediação.
A assinatura digital completa (ZapSign) pode ser enviada após a criação da conta LETTER.</p>
<p>{cidade}, {data_extenso}.</p>
<p>{empresa_dados}</p>
""".strip()


def template_storage_key(organization_id: str) -> str:
    return f"{organization_id}/{TEMPLATE_STORAGE_SUFFIX}"


def load_organization_template(db: Session | None, organization_id: str) -> str:
    if db is not None:
        from app.org_settings_service import get_setting

        stored = get_setting(db, organization_id, "marketplace_contract_html")
        if stored.strip():
            return stored.strip()
    key = template_storage_key(organization_id)
    try:
        raw = get_storage().get(key)
        if raw:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
            if text.strip():
                return text.strip()
    except Exception:
        pass
    return DEFAULT_MARKETPLACE_CONTRACT_TEMPLATE


def save_organization_template(
    organization_id: str,
    template_html: str,
    db: Session | None = None,
) -> None:
    body = (template_html or "").strip()
    if not body:
        raise ValueError("Template vazio")
    if db is not None:
        from app.org_settings_service import set_settings

        set_settings(db, organization_id, {"marketplace_contract_html": body})
    get_storage().put(template_storage_key(organization_id), body.encode("utf-8"), "text/html; charset=utf-8")


def _locked_span(field: str, value: str) -> str:
    safe = html.escape(str(value or "—"), quote=False)
    return (
        f'<span data-letter-field="{field}" class="letter-contract-locked" contenteditable="false" '
        f'style="background:#f3f4f6;border-radius:3px;padding:0 2px;">{safe}</span>'
    )


def build_contract_variables(lead: Lead, snap: dict) -> dict[str, str]:
    person = str(snap.get("person_type") or "PF").upper()
    doc = _digits(lead.document or snap.get("document") or "")
    address = snap.get("address") if isinstance(snap.get("address"), dict) else {}
    nome = str(snap.get("razao_social") or lead.name or "")
    if person != "PJ":
        nome = lead.name or nome
    credit = snap.get("handoff_credit")
    entrada = snap.get("handoff_entrada")
    quotas = snap.get("handoff_quotas") or []
    admins = ", ".join(
        sorted({str(q.get("administradora") or "").strip() for q in quotas if isinstance(q, dict) and q.get("administradora")})
    ) or "—"
    parcelas_txt = "; ".join(
        f"{q.get('parcelas') or '—'}x de {q.get('price_parcela') or '—'}"
        for q in quotas
        if isinstance(q, dict)
    ) or "—"
    end_txt = (
        f"{address.get('street') or '—'}, {address.get('number') or '—'} "
        f"{address.get('complement') or ''} — {address.get('neighborhood') or '—'}, "
        f"{address.get('city') or '—'}/{address.get('uf') or '—'} CEP {address.get('zipcode') or '—'}"
    ).strip()
    profissao = str(snap.get("profession") or snap.get("activity") or "—")
    renda = snap.get("declared_income")
    proofs = snap.get("income_proof") or []
    proof_labels = ", ".join(INCOME_PROOF_OPTIONS.get(str(p), str(p)) for p in proofs) or "—"
    from datetime import date

    today = date.today()
    meses = (
        "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro"
    ).split()
    data_extenso = f"{today.day} de {meses[today.month - 1]} de {today.year}"
    empresa_dados = (
        "<b>LETTER BANK LTDA</b>, PESSOA JURÍDICA DE DIREITO PRIVADO, INSCRITA NO CNPJ N° "
        "41.163.819/0001-57, REPRESENTADA POR SEU SÓCIO ADMINISTRADOR, <b>SR. PAULO STUTZ NETTO SOUZA</b>."
    )
    documento = f"CNPJ N° {doc}" if person == "PJ" and doc else (f"CPF N° {doc}" if doc else "—")
    return {
        "nome": nome,
        "documento": documento,
        "profissao": profissao,
        "profissao_label": "Ramo de atividade" if person == "PJ" else "Profissão",
        "renda": _brl(renda) if renda not in (None, "") else "—",
        "renda_label": "Faturamento mensal" if person == "PJ" else "Renda mensal",
        "comprovacao_renda": proof_labels,
        "endereco": end_txt,
        "email": str(snap.get("email") or "—"),
        "whatsapp": lead.phone or "—",
        "administradora": admins,
        "valor_credito": _brl(credit or 0),
        "valor_entrada": _brl(entrada or 0),
        "parcelas": parcelas_txt,
        "reserva_minutos": str(RESERVE_TTL),
        "empresa_chave_pix": "COMERCIAL@LETTER.APP.BR DO BANCO INTER",
        "empresa_dados": empresa_dados,
        "cidade": str(address.get("city") or "Brasil"),
        "data_extenso": data_extenso,
    }


def render_marketplace_contract_html(
    db: Session | None,
    organization_id: str,
    lead: Lead,
    snap: dict,
    *,
    template_html: str | None = None,
) -> str:
    template = (template_html or load_organization_template(db, organization_id)).strip()
    vars_map = build_contract_variables(lead, snap)
    out = template
    for key, value in vars_map.items():
        token = "{" + key + "}"
        replacement = _locked_span(key, value) if key in LOCKED_FIELD_LABELS else str(value)
        out = out.replace(token, replacement)
    # Tokens legados não mapeados viram travados genéricos
    for match in re.findall(r"\{([a-zA-Z0-9_]+)\}", out):
        out = out.replace("{" + match + "}", _locked_span(match, "—"))
    return f'<div class="letter-contract-body" style="padding:12px 0;line-height:1.5;text-align:justify">{out}</div>'


def _normalize_locked_inner(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text or "")).strip()


def extract_locked_fields(html_body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in re.finditer(
        r'data-letter-field="([^"]+)"[^>]*>(.*?)</span>',
        html_body or "",
        flags=re.IGNORECASE | re.DOTALL,
    ):
        fields[match.group(1)] = _normalize_locked_inner(match.group(2))
    return fields


def assert_locked_fields_unchanged(before_html: str, after_html: str) -> None:
    before = extract_locked_fields(before_html)
    if not before:
        return
    after = extract_locked_fields(after_html)
    for key, value in before.items():
        if key not in after:
            raise ValueError(f"Campo programado removido: {LOCKED_FIELD_LABELS.get(key, key)}")
        if after[key] != value:
            raise ValueError(f"Não altere o campo programado: {LOCKED_FIELD_LABELS.get(key, key)}")
