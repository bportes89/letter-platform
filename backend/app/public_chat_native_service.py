"""Chat público nativo LETTER — jornada Marketplace com Esteira 2 (mesmo motor do admin)."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.affiliate_markup_service import resolve_affiliate_porc_a_mais
from app.cadastro_service import seed_marketplace_lifecycle
from app.marketplace_service import esteira2_nina_curated_match
from app.models import Lead, Organization, Proposal, Quota, Role, User
from app.network_service import PARTNER_NETWORK_ROLES
from app.public_site_service import headquarters_org, lookup_referral_code
from app.quota_inventory_service import run_nina_quota_scan
from app.sdc_desk_service import evaluate_sdc_desk, store_solicitation as store_sdc_solicitation
from app.flash_desk_service import evaluate_flash_desk, store_solicitation as store_flash_solicitation
from app.quitcon_desk_service import evaluate_quitcon_desk, store_solicitation as store_quitcon_solicitation
from app.services import money, reserve_quota

SOURCE = "SITE_CHAT"
PRODUCT = "MARKETPLACE"
RESERVE_TTL = 60

# Steps nativos (faixa alta para não colidir com VMC -910x nem legado baixo).
STEP_NAME = "10001"
STEP_WELCOME = "10002"
STEP_EMAIL = "10003"
STEP_PHONE = "10004"
STEP_CATEGORY = "10005"
STEP_YEAR = "10006"
STEP_DIRTY = "10007"
STEP_CREDIT = "10008"
STEP_ENTRADA = "10009"
STEP_INCOME = "10010"
STEP_ASSET = "10011"
STEP_MATCH = "10012"
STEP_CONFIRM = "10013"
STEP_HANDOFF_RESUMO = "10014"
STEP_CONTRACT_PLACEHOLDER = "10015"
STEP_ACCOUNT_CTA = "10016"
STEP_BOLETO_HANDOFF = "10017"
STEP_DONE_FINAL = "10018"
# Pós-match — dados do pagador / conta (Paulo 15–25, faixa dedicada).
STEP_PERSON_TYPE = "10030"
STEP_DOCUMENT = "10031"
STEP_RAZAO = "10032"
STEP_ZIPCODE = "10033"
STEP_ADDRESS_NUMBER = "10034"
STEP_PROFESSION = "10035"
STEP_INCOME_AMOUNT = "10036"
STEP_INCOME_PROOF = "10037"
STEP_DOUBTS = "10038"
STEP_FAQ_LIST = "10039"
STEP_FAQ_ANSWER = "10040"
# Compatível com o widget legado (clique FAQ → step 95).
STEP_FAQ_ANSWER_LEGACY = "95"
# legado (renomeado)
STEP_DONE = STEP_HANDOFF_RESUMO

# Capital de Giro (SDC) — faixa paralela ao Marketplace.
STEP_SDC_ASSET_TYPE = "10020"
STEP_SDC_YEAR = "10021"
STEP_SDC_VALUE = "10022"
STEP_SDC_PAID_OFF = "10023"
STEP_SDC_LIEN = "10024"
STEP_SDC_DOCS = "10025"
STEP_SDC_EVAL = "10026"
STEP_SDC_CONFIRM = "10027"
STEP_SDC_DONE = "10028"
# Flash Capital — faixa paralela (espelha SDC + prazo 36/60).
STEP_FLASH_ASSET_TYPE = "10050"
STEP_FLASH_YEAR = "10051"
STEP_FLASH_VALUE = "10052"
STEP_FLASH_PAID_OFF = "10053"
STEP_FLASH_LIEN = "10054"
STEP_FLASH_DOCS = "10055"
STEP_FLASH_TERM = "10056"
STEP_FLASH_EVAL = "10057"
STEP_FLASH_CONFIRM = "10058"
# QuitCon — quitação inteligente (doc253) → mesa QuitCon.
STEP_QUITCON_BALANCE = "10060"
STEP_QUITCON_MONTHS = "10061"
STEP_QUITCON_ADMIN = "10062"
STEP_QUITCON_REGISTRY = "10063"
STEP_QUITCON_CONTEMPLADA = "10064"
STEP_QUITCON_BEM = "10065"
STEP_QUITCON_PARCELAS = "10066"
STEP_QUITCON_DOCS = "10067"
STEP_QUITCON_EVAL = "10068"
STEP_QUITCON_CONFIRM = "10069"

QUITCON_ADMIN_OPTIONS = (
    ("Embracon", "Embracon"),
    ("Ademicon", "Ademicon"),
    ("Âncora", "Ancora"),
    ("HS", "HS"),
    ("Tradição", "Tradicao"),
    ("Recon", "Recon"),
    ("Groscon", "Groscon"),
    ("Roma", "Roma"),
    ("Reserva", "Reserva"),
)

KNOWN_CEPS = {
    "36010000": {
        "street": "Rua Halfeld",
        "neighborhood": "Centro",
        "city": "Juiz de Fora",
        "uf": "MG",
    },
    "29090130": {
        "street": "Avenida Nossa Senhora da Penha",
        "neighborhood": "Santa Lucia",
        "city": "Vitoria",
        "uf": "ES",
    },
    "01310100": {
        "street": "Avenida Paulista",
        "neighborhood": "Bela Vista",
        "city": "Sao Paulo",
        "uf": "SP",
    },
}

INCOME_PROOF_OPTIONS = {
    "holerite": "Holerite",
    "ir": "IR",
    "decore": "Decore",
    "extrato": "Extrato",
}

# FAQ: seed Paulo + CRUD em marketplace_chat_faq_service (admin /marketplace/chat-faq).


def _faq_by_id(db, org_id: str, faq_id: str | None) -> dict[str, str] | None:
    from app.marketplace_chat_faq_service import find_active_for_chat

    return find_active_for_chat(db, org_id, faq_id)


def _faq_list_item(db, org_id: str) -> dict:
    from app.marketplace_chat_faq_service import list_active_for_chat

    rows = list_active_for_chat(db, org_id)
    return {
        "text": "Selecione uma dúvida:",
        "faq": True,
        "items": [{"id": row["id"], "name": row["name"]} for row in rows],
        "next": int(STEP_FAQ_ANSWER),
    }


def _doubts_prompt(*, lead_id: str | None = None) -> dict:
    return _wrap(
        [
            {
                "text": "Vamos dar seguimento para concluirmos a sua compra. Mas antes, você ficou com alguma dúvida?",
                "options": [
                    {"name": "Sim", "save": "yes", "next": int(STEP_DOUBTS)},
                    {"name": "Não", "save": "no", "next": int(STEP_DOUBTS)},
                ],
            }
        ],
        lead_id=lead_id,
    )


def _brl(value: Decimal | str | float | int) -> str:
    amount = money(Decimal(str(value)))
    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _money_input(raw: Any) -> Decimal:
    if raw is None or raw == "":
        raise HTTPException(422, "Informe um valor válido.")
    text = str(raw).strip()
    if not text:
        raise HTTPException(422, "Informe um valor válido.")
    cleaned = text.replace("R$", "").replace(" ", "")
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise HTTPException(422, "Digite um valor válido!") from exc
    if value < 0:
        raise HTTPException(422, "Digite um valor válido!")
    return money(value)


def _lookup_cep(cep: str) -> dict:
    digits = _digits(cep)
    if len(digits) != 8:
        raise HTTPException(422, "Digite um CEP válido!")
    if digits in KNOWN_CEPS:
        return dict(KNOWN_CEPS[digits])
    try:
        import urllib.request

        req = urllib.request.Request(
            f"https://viacep.com.br/ws/{digits}/json/",
            headers={"User-Agent": "letter-platform/chat"},
        )
        with urllib.request.urlopen(req, timeout=4) as resp:  # noqa: S310 — API pública de CEP
            payload = json.loads(resp.read().decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("erro"):
            raise HTTPException(422, "CEP não encontrado. Confira os 8 dígitos.")
        return {
            "street": str(payload.get("logradouro") or "").strip(),
            "neighborhood": str(payload.get("bairro") or "").strip(),
            "city": str(payload.get("localidade") or "").strip(),
            "uf": str(payload.get("uf") or "").strip().upper(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "Não foi possível consultar o CEP. Tente novamente.") from exc


def _contract_html(lead: Lead, snap: dict) -> str:
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
        sorted({str(q.get("administradora") or "").strip() for q in quotas if q.get("administradora")})
    ) or "—"
    parcelas_txt = "; ".join(
        f"{q.get('parcelas') or '—'}x de {q.get('price_parcela') or '—'}" for q in quotas
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
    return (
        "<p><strong>LETTER BANK LTDA</strong> — CNPJ 41.163.819/0001-57<br/>"
        "Representada por Sr. Paulo Stutz Netto Souza — foro em Nanuque/MG</p>"
        "<p><strong>Termo de intermediação de cota contemplada</strong></p>"
        f"<p><strong>Contratante:</strong> {nome}<br/>"
        f"<strong>Documento:</strong> {doc or '—'} ({'CNPJ' if person == 'PJ' else 'CPF'})<br/>"
        f"<strong>{'Ramo de atividade' if person == 'PJ' else 'Profissão'}:</strong> {profissao}<br/>"
        f"<strong>{'Faturamento mensal' if person == 'PJ' else 'Renda mensal'}:</strong> "
        f"{_brl(renda) if renda not in (None, '') else '—'}<br/>"
        f"<strong>Comprovação de renda:</strong> {proof_labels}<br/>"
        f"<strong>Endereço:</strong> {end_txt}<br/>"
        f"<strong>E-mail:</strong> {snap.get('email') or '—'} · <strong>WhatsApp:</strong> {lead.phone or '—'}</p>"
        f"<p><strong>Objeto:</strong> intermediação de cota(s) contemplada(s).<br/>"
        f"Administradora(s): {admins}<br/>"
        f"Crédito: {_brl(credit or 0)} · Entrada: {_brl(entrada or 0)}<br/>"
        f"Parcelas: {parcelas_txt}<br/>"
        f"Reserva das cotas: {RESERVE_TTL} minutos a partir da escolha.</p>"
        "<p>PIX de referência LETTER: <strong>COMERCIAL@LETTER.APP.BR</strong> (Banco Inter).</p>"
        "<p>Ao aceitar, o contratante confirma ciência das condições de intermediação. "
        "A assinatura digital completa (ZapSign) pode ser enviada após a criação da conta LETTER.</p>"
        f"<p>{address.get('city') or 'Brasil'}, {data_extenso}.</p>"
    )


def _income_proof_item(selected: list[str]) -> dict:
    marked = ", ".join(INCOME_PROOF_OPTIONS[k] for k in selected if k in INCOME_PROOF_OPTIONS)
    text = "Como você comprova a renda? (pode marcar mais de uma)"
    if marked:
        text = f"Marcado: {marked}. Quer adicionar outra forma ou continuar?"
    options = [
        {"name": label, "save": key, "next": int(STEP_INCOME_PROOF)}
        for key, label in INCOME_PROOF_OPTIONS.items()
        if key not in selected
    ]
    if selected:
        options.append({"name": "Continuar", "save": "done", "next": int(STEP_INCOME_PROOF)})
    return {"text": text, "options": options}


def _income_proof_prompt(lead: Lead, selected: list[str]) -> dict:
    return _wrap([_income_proof_item(selected)], lead_id=lead.id)


def _site_info() -> dict:
    return {
        "whatsapp": _digits(settings.company_phone),
        "whatsapp_code": "55",
        "whatsapp_txt": "Olá, gostaria de falar com a LETTER.",
        "email": settings.company_email,
    }


def _wrap(chat_next: list[dict], *, lead_id: str | None = None) -> dict:
    obj: dict[str, Any] = {"chat_next": chat_next, "info": _site_info()}
    if lead_id:
        obj["lead_id"] = lead_id
    return {"OBJ": obj, "native": True}


def _actor(db: Session, org: Organization) -> User:
    admin = db.scalar(
        select(User).where(
            User.organization_id == org.id,
            User.role == Role.PLATFORM_ADMIN,
            User.active.is_(True),
        ).order_by(User.created_at)
    )
    if not admin:
        admin = db.scalar(
            select(User).where(User.organization_id == org.id, User.active.is_(True)).order_by(User.created_at)
        )
    if not admin:
        raise HTTPException(503, "Atendimento indisponível: operador da matriz não configurado.")
    return admin


def _lead_snapshot(lead: Lead) -> dict:
    try:
        detail = json.loads(lead.scr_detail_json or "{}")
        snap = detail.get("chat") if isinstance(detail, dict) else {}
        return snap if isinstance(snap, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save_lead_snapshot(lead: Lead, snap: dict) -> None:
    try:
        detail = json.loads(lead.scr_detail_json or "{}")
        if not isinstance(detail, dict):
            detail = {}
    except json.JSONDecodeError:
        detail = {}
    detail["chat"] = snap
    lead.scr_detail_json = json.dumps(detail, ensure_ascii=False)


def _bind_chat_partner(db: Session, org: Organization, lead: Lead, payload: dict, snap: dict) -> None:
    """Vincula parceiro pelo ?ref= (regra: primeiro parceiro congelado)."""
    if snap.get("partner_frozen"):
        return
    code = str(payload.get("referral_code") or "").strip()
    if not code:
        return
    node = lookup_referral_code(db, org.id, code)
    if not node:
        return
    partner = db.get(User, node.user_id)
    if not partner or not partner.active or partner.role not in PARTNER_NETWORK_ROLES:
        return
    lead.owner_id = partner.id
    snap["partner_user_id"] = partner.id
    snap["partner_referral_code"] = node.referral_code
    snap["partner_frozen"] = True
    ref_tag = f":REF:{node.referral_code}"
    if ref_tag not in (lead.source or ""):
        lead.source = f"{SOURCE}{ref_tag}" if lead.source == SOURCE else f"{lead.source}{ref_tag}"


def _chat_affiliate_markup(db: Session, org: Organization, snap: dict) -> dict[str, str] | None:
    partner_id = snap.get("partner_user_id")
    if not partner_id:
        return None
    return resolve_affiliate_porc_a_mais(db, org.id, str(partner_id), is_sdc=False)


def _find_lead(db: Session, org: Organization, payload: dict) -> Lead | None:
    lead_id = str(payload.get("lead_id") or "").strip()
    if lead_id:
        lead = db.scalar(
            select(Lead).where(
                Lead.id == lead_id,
                Lead.organization_id == org.id,
                Lead.source.startswith(SOURCE),
            )
        )
        if lead:
            return lead
    email = str(payload.get("email") or "").strip().lower()
    if email and "@" in email:
        leads = list(
            db.scalars(
                select(Lead)
                .where(Lead.organization_id == org.id, Lead.source.startswith(SOURCE))
                .order_by(Lead.created_at.desc())
                .limit(40)
            )
        )
        for lead in leads:
            snap = _lead_snapshot(lead)
            if str(snap.get("email") or "").lower() == email:
                return lead
    return None


def _full_name_ok(name: str) -> bool:
    parts = [p for p in name.strip().split() if p]
    if len(parts) < 2:
        return False
    return all(len(p) > 2 for p in parts[:2])


def home_native() -> dict:
    return _wrap(
        [
            {
                "text": (
                    "Olá! Eu sou o Letter. Ajudo você a financiar imóveis e veículos "
                    "com cartas contempladas — menos burocracia que banco, mesmo com score baixo."
                ),
                "button": "Continuar",
                "next": int(STEP_NAME),
                "mascote": 1,
            },
            {
                "text": "Quer vender uma cota que você já tem?",
                "options": [
                    {"name": "Vender minha cota", "link": "/vender-minha-cota", "save": "open_page"},
                    {"name": "Quero comprar / financiar", "next": int(STEP_NAME)},
                ],
            },
        ]
    )


def _retry(
    message: str,
    step: str,
    *,
    input_name: str | None = None,
    label: str | None = None,
    lead_id: str | None = None,
    input_type: str = "text",
) -> dict:
    item: dict[str, Any] = {"text": message, "next": int(step)}
    if input_name:
        item["input"] = {"name": input_name, "label": label or input_name, "type": input_type}
    else:
        item["button"] = "Tentar de novo"
    return _wrap([item], lead_id=lead_id)


def handle_step(db: Session, step: str, payload: dict | None) -> dict:
    data = dict(payload or {})
    org = headquarters_org(db)
    actor = _actor(db, org)
    step = str(step)

    if step in {"0", "", "home"}:
        return home_native()

    if step == STEP_NAME:
        name = str(data.get("name") or "").strip()
        if not _full_name_ok(name):
            return _retry("Digite o seu nome completo!", STEP_NAME, input_name="name", label="Nome completo")
        first = name.split()[0]
        return _wrap(
            [
                {
                    "text": f"Muito prazer, {first}. Vamos montar sua simulação com cartas contempladas.",
                    "button": "Continuar",
                    "next": int(STEP_EMAIL),
                    "mascote": 1,
                }
            ]
        )

    if step == STEP_EMAIL:
        # Coming from welcome button — ask email
        if "email" not in data or data.get("_ask_email"):
            return _wrap(
                [
                    {
                        "text": "Qual é o seu e-mail?",
                        "input": {"name": "email", "label": "E-mail", "type": "email", "tags": 'placeholder="voce@email.com" type="email"'},
                        "next": int(STEP_EMAIL),
                    }
                ]
            )
        email = str(data.get("email") or "").strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            return _retry("Digite um e-mail válido!", STEP_EMAIL, input_name="email", label="E-mail")
        name = str(data.get("name") or "").strip() or "Visitante"
        lead = _find_lead(db, org, data)
        if not lead:
            lead = Lead(
                organization_id=org.id,
                owner_id=actor.id,
                name=name,
                phone="0000000000",
                product_interest=PRODUCT,
                status="NEW",
                source=SOURCE,
            )
            db.add(lead)
            db.flush()
        snap = _lead_snapshot(lead)
        snap.update({"email": email, "name": name})
        _bind_chat_partner(db, org, lead, data, snap)
        _save_lead_snapshot(lead, snap)
        lead.name = name
        db.flush()
        return _wrap(
            [
                {
                    "text": "Agora o seu WhatsApp com DDD.",
                    "input": {"name": "phone", "label": "Telefone", "type": "tel", "tags": 'placeholder="(00) 00000-0000" type="tel"'},
                    "next": int(STEP_PHONE),
                }
            ],
            lead_id=lead.id,
        )

    # After welcome video Continuar lands on STEP_EMAIL without email yet — handle via asking
    if step == STEP_WELCOME:
        return _wrap(
            [
                {
                    "text": "Qual é o seu e-mail?",
                    "input": {"name": "email", "label": "E-mail", "type": "email"},
                    "next": int(STEP_EMAIL),
                }
            ]
        )

    lead = _find_lead(db, org, data)
    if lead:
        snap = _lead_snapshot(lead)
        _bind_chat_partner(db, org, lead, data, snap)
        _save_lead_snapshot(lead, snap)
        db.flush()

    if step == STEP_PHONE:
        phone = _digits(str(data.get("phone") or ""))
        if len(phone) < 10:
            return _retry(
                "Digite um telefone válido!",
                STEP_PHONE,
                input_name="phone",
                label="Telefone",
                lead_id=lead.id if lead else None,
            )
        if not lead:
            email = str(data.get("email") or "").strip().lower()
            name = str(data.get("name") or "Visitante").strip()
            lead = Lead(
                organization_id=org.id,
                owner_id=actor.id,
                name=name,
                phone=phone,
                product_interest=PRODUCT,
                status="CONTACTED",
                source=SOURCE,
            )
            db.add(lead)
            db.flush()
            _save_lead_snapshot(lead, {"email": email, "name": name, "phone": phone})
        else:
            lead.phone = phone
            lead.status = "CONTACTED"
            snap = _lead_snapshot(lead)
            snap["phone"] = phone
            _save_lead_snapshot(lead, snap)
            db.flush()
        return _wrap(
            [
                {
                    "text": "O que você deseja financiar?",
                    "options": [
                        {"name": "Imóvel", "next": int(STEP_DIRTY), "save": "REAL_ESTATE", "id": "REAL_ESTATE"},
                        {"name": "Veículo", "next": int(STEP_YEAR), "save": "VEHICLE", "id": "VEHICLE"},
                        {"name": "Capital de Giro (SDC)", "next": int(STEP_SDC_ASSET_TYPE), "save": "SDC", "id": "SDC"},
                        {"name": "Flash Capital", "next": int(STEP_FLASH_ASSET_TYPE), "save": "FLASH", "id": "FLASH"},
                        {"name": "QuitCon", "next": int(STEP_QUITCON_BALANCE), "save": "QUITCON", "id": "QUITCON"},
                        {"name": "Vender minha cota", "link": "/vender-minha-cota", "save": "open_page"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_YEAR:
        # category vehicle selected
        category = "VEHICLE"
        if data.get("option_save") == "VEHICLE" or data.get("option_id") == "VEHICLE":
            if lead:
                snap = _lead_snapshot(lead)
                snap["category"] = category
                _save_lead_snapshot(lead, snap)
        year_raw = data.get("asset_year")
        if year_raw is None and data.get("option_id") in (None, "VEHICLE"):
            current = date.today().year
            years = [{"name": "Zero KM", "next": int(STEP_YEAR), "id": "0", "save": "zero"}] + [
                {"name": str(y), "next": int(STEP_YEAR), "id": str(y), "save": str(y)} for y in range(current, current - 26, -1)
            ]
            return _wrap(
                [{"text": "Qual o ano de fabricação?", "options": years, "options_select": True}],
                lead_id=lead.id if lead else None,
            )
        # year chosen via option
        if lead:
            snap = _lead_snapshot(lead)
            snap["category"] = "VEHICLE"
            if str(data.get("option_id") or "") == "0" or data.get("option_save") == "zero":
                snap["asset_year"] = date.today().year
                snap["asset_is_zero_km"] = True
            else:
                try:
                    snap["asset_year"] = int(data.get("option_id") or data.get("asset_year") or date.today().year)
                except ValueError:
                    snap["asset_year"] = date.today().year
                snap["asset_is_zero_km"] = False
            _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "Você possui alguma restrição no nome (SPC, Serasa)?",
                    "options": [
                        {"name": "Sim", "next": int(STEP_CREDIT), "id": "dirty_yes", "save": "1"},
                        {"name": "Não", "next": int(STEP_CREDIT), "id": "dirty_no", "save": "0"},
                    ],
                }
            ],
            lead_id=lead.id if lead else None,
        )

    if step == STEP_DIRTY:
        # From REAL_ESTATE category or after year
        if lead:
            snap = _lead_snapshot(lead)
            if data.get("option_save") == "REAL_ESTATE" or data.get("option_id") == "REAL_ESTATE":
                snap["category"] = "REAL_ESTATE"
                snap["asset_year"] = 2020
                snap["asset_is_zero_km"] = False
            if data.get("option_save") in {"1", "0"} or data.get("option_id") in {"dirty_yes", "dirty_no"}:
                snap["has_credit_restriction"] = data.get("option_save") == "1" or data.get("option_id") == "dirty_yes"
                _save_lead_snapshot(lead, snap)
                return _wrap(
                    [
                        {
                            "text": "Qual valor de crédito você precisa?",
                            "input": {"name": "target_amount", "label": "Crédito", "type": "text", "tags": 'placeholder="R$ 0,00"'},
                            "next": int(STEP_CREDIT),
                        }
                    ],
                    lead_id=lead.id,
                )
            _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "Você possui alguma restrição no nome (SPC, Serasa)?",
                    "options": [
                        {"name": "Sim", "next": int(STEP_CREDIT), "id": "dirty_yes", "save": "1"},
                        {"name": "Não", "next": int(STEP_CREDIT), "id": "dirty_no", "save": "0"},
                    ],
                }
            ],
            lead_id=lead.id if lead else None,
        )

    if step == STEP_CREDIT:
        # May arrive from dirty options OR from amount input
        if lead and (data.get("option_save") in {"1", "0"} or data.get("option_id") in {"dirty_yes", "dirty_no"}):
            snap = _lead_snapshot(lead)
            snap["has_credit_restriction"] = data.get("option_save") == "1" or data.get("option_id") == "dirty_yes"
            _save_lead_snapshot(lead, snap)
            if "target_amount" not in data:
                return _wrap(
                    [
                        {
                            "text": "Qual valor de crédito você precisa?",
                            "input": {"name": "target_amount", "label": "Crédito", "type": "text"},
                            "next": int(STEP_CREDIT),
                        }
                    ],
                    lead_id=lead.id,
                )
        try:
            credit = _money_input(data.get("target_amount"))
        except HTTPException:
            return _retry("Digite o valor do crédito!", STEP_CREDIT, input_name="target_amount", label="Crédito")
        if credit <= 0:
            return _retry("Digite o valor do crédito!", STEP_CREDIT, input_name="target_amount", label="Crédito")
        if lead:
            snap = _lead_snapshot(lead)
            snap["target_amount"] = str(credit)
            _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "Quanto você tem para dar de entrada? (pode ser zero)",
                    "input": {"name": "target_entrada", "label": "Entrada", "type": "text"},
                    "next": int(STEP_ENTRADA),
                }
            ],
            lead_id=lead.id if lead else None,
        )

    if step == STEP_ENTRADA:
        try:
            entrada = _money_input(data.get("target_entrada") if data.get("target_entrada") not in (None, "") else "0")
        except HTTPException:
            return _retry("Digite o valor da entrada!", STEP_ENTRADA, input_name="target_entrada", label="Entrada")
        if lead:
            snap = _lead_snapshot(lead)
            snap["target_entrada"] = str(entrada)
            _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "Qual a sua renda mensal comprovada?",
                    "input": {"name": "monthly_income", "label": "Renda", "type": "text"},
                    "next": int(STEP_INCOME),
                }
            ],
            lead_id=lead.id if lead else None,
        )

    if step == STEP_INCOME:
        try:
            income = _money_input(data.get("monthly_income"))
        except HTTPException:
            return _retry("Informe a renda mensal!", STEP_INCOME, input_name="monthly_income", label="Renda")
        if income <= 0:
            return _retry("Informe a renda mensal!", STEP_INCOME, input_name="monthly_income", label="Renda")
        if lead:
            snap = _lead_snapshot(lead)
            snap["monthly_income"] = str(income)
            _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "Qual o valor de avaliação do bem (imóvel/veículo)?",
                    "input": {"name": "asset_value", "label": "Valor do bem", "type": "text"},
                    "next": int(STEP_ASSET),
                }
            ],
            lead_id=lead.id if lead else None,
        )

    if step == STEP_ASSET:
        try:
            asset = _money_input(data.get("asset_value"))
        except HTTPException:
            return _retry("Informe o valor do bem!", STEP_ASSET, input_name="asset_value", label="Valor do bem")
        if asset <= 0:
            return _retry("Informe o valor do bem!", STEP_ASSET, input_name="asset_value", label="Valor do bem")
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        snap["asset_value"] = str(asset)
        _save_lead_snapshot(lead, snap)
        lead.status = "QUALIFIED"
        db.flush()

        category = str(snap.get("category") or "REAL_ESTATE")
        target_amount = Decimal(str(snap.get("target_amount") or "0"))
        target_entrada = Decimal(str(snap.get("target_entrada") or "0")) or None
        monthly_income = Decimal(str(snap.get("monthly_income") or "0"))
        asset_year = int(snap.get("asset_year") or 2020)
        has_restriction = bool(snap.get("has_credit_restriction"))
        zero_km = bool(snap.get("asset_is_zero_km"))

        affiliate_markup = _chat_affiliate_markup(db, org, snap)
        match = esteira2_nina_curated_match(
            db,
            actor,
            target_amount=target_amount,
            category=category,
            asset_year=asset_year,
            monthly_income=monthly_income,
            monthly_commitment=Decimal("0"),
            asset_value=asset,
            has_credit_restriction=has_restriction,
            asset_is_zero_km=zero_km,
            target_entrada=target_entrada if target_entrada and target_entrada > 0 else None,
            affiliate_markup=affiliate_markup,
        )
        options: list[dict] = []
        for lane_name, lane_rows in (
            ("Crédito", match.get("credit_matches") or []),
            ("Entrada", match.get("entrada_matches") or []),
            ("Opções", match.get("matches") or []),
        ):
            for row in lane_rows:
                qids = row.get("quota_ids") or []
                key = "|".join(qids)
                if any(o.get("id") == key for o in options):
                    continue
                q0 = (row.get("quotas") or [{}])[0]
                options.append(
                    {
                        "id": key,
                        "name": f"{lane_name}: {_brl(row.get('total_credit'))} · entrada {_brl(row.get('total_entrada') or 0)}",
                        "next": int(STEP_CONFIRM),
                        "save": key,
                        "administradora": row.get("administrator_name") or q0.get("administrator_name"),
                        "tipo_credito": "Imóvel" if category == "REAL_ESTATE" else "Veículo",
                        "price": _brl(row.get("total_credit")),
                        "price_entrada": _brl(row.get("total_entrada") or 0),
                        "parcelas": q0.get("remaining_installments"),
                        "price_parcela": _brl(q0.get("installment_value") or 0),
                    }
                )
        snap["match_options"] = {o["id"]: o["id"] for o in options}
        _save_lead_snapshot(lead, snap)
        db.flush()
        if not options:
            return _wrap(
                [
                    {
                        "text": match.get("message")
                        or "Desculpe, não encontramos nenhuma cota com esses valores! Tente mudar o crédito ou a entrada.",
                        "options": [
                            {"name": "Ajustar crédito", "next": int(STEP_CREDIT)},
                            {"name": "Recomeçar", "next": 0},
                        ],
                        "options_empty": "Nenhuma cota na régua de 5%.",
                    }
                ],
                lead_id=lead.id,
            )
        return _wrap(
            [
                {
                    "text": "Encontrei estas opções pelo robô Esteira 2 (régua 5%). Escolha uma:",
                    "options": options,
                    "options_quotas": True,
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_CONFIRM:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        chosen = str(data.get("option_save") or data.get("option_id") or "").strip()
        if not chosen:
            return _wrap([{"text": "Selecione uma das opções de cota.", "button": "Voltar", "next": int(STEP_ASSET)}], lead_id=lead.id)
        quota_ids = [qid for qid in chosen.split("|") if qid]
        quotas = list(db.scalars(select(Quota).where(Quota.id.in_(quota_ids), Quota.organization_id == org.id)))
        if len(quotas) != len(set(quota_ids)):
            raise HTTPException(404, "Cota selecionada indisponível.")
        for quota in quotas:
            if quota.nina_scan_status != "CLEARED":
                result = run_nina_quota_scan(db, actor, quota)
                if result.get("status") != "CLEARED":
                    return _wrap(
                        [
                            {
                                "text": result.get("message") or "Esta cota não passou na varredura Nina.",
                                "options": [{"name": "Ver outras opções", "next": int(STEP_ASSET)}],
                            }
                        ],
                        lead_id=lead.id,
                    )
        existing = db.scalar(
            select(Proposal).where(
                Proposal.lead_id == lead.id,
                Proposal.organization_id == org.id,
                Proposal.product == PRODUCT,
            )
        )
        total = money(sum((Decimal(str(q.credit_value)) for q in quotas), Decimal("0")))
        from app.marketplace_service import pricing_for_quota
        from app.quota_supplier_service import suppliers_index

        suppliers = suppliers_index(db, org.id)
        snap = _lead_snapshot(lead)
        affiliate_markup = _chat_affiliate_markup(db, org, snap)
        porcs = affiliate_markup or {"porc_a_mais": "0", "porc_a_mais_sellers": "0"}
        total_entrada = money(
            sum(
                (
                    pricing_for_quota(q, suppliers=suppliers, affiliate_markup=affiliate_markup)["entrada_final"]
                    for q in quotas
                ),
                Decimal("0"),
            )
        )
        if not existing:
            proposal = Proposal(
                organization_id=org.id,
                lead_id=lead.id,
                product=PRODUCT,
                requested_amount=total,
                status="SUBMITTED",
                terms_json=json.dumps(
                    seed_marketplace_lifecycle(
                        {
                            "channel": SOURCE,
                            "quota_ids": quota_ids,
                            "total_credit": str(total),
                            "total_entrada": str(total_entrada),
                            "client_email": snap.get("email"),
                            "partner_user_id": snap.get("partner_user_id"),
                            "partner_referral_code": snap.get("partner_referral_code"),
                            "porc_a_mais": porcs.get("porc_a_mais", "0"),
                            "porc_a_mais_sellers": porcs.get("porc_a_mais_sellers", "0"),
                            "filters": snap,
                        }
                    ),
                    ensure_ascii=False,
                ),
                sale_channel="SELF_SERVICE",
                created_by_user_id=actor.id,
                commission_originator_id=snap.get("partner_user_id"),
            )
            db.add(proposal)
            db.flush()
            for quota in quotas:
                if quota.status == "AVAILABLE":
                    reserve_quota(db, actor, quota, proposal.id, RESERVE_TTL)
            lead.status = "PROPOSAL"
            proposal_id = proposal.id
        else:
            proposal_id = existing.id

        snap["chosen_quota_ids"] = quota_ids
        snap["proposal_id"] = proposal_id
        snap["handoff_credit"] = str(total)
        snap["handoff_entrada"] = str(total_entrada)
        from app.marketplace_service import pricing_for_quota as _pfq

        snap["handoff_quotas"] = [
            {
                "id": q.id,
                "administradora": getattr(q, "administrator_name_txt", None),
                "tipo_credito": "Imóvel" if q.category == "REAL_ESTATE" else "Veículo",
                "price": _brl(q.credit_value),
                "price_entrada": _brl(_pfq(q, suppliers=suppliers, affiliate_markup=affiliate_markup)["entrada_final"]),
                "parcelas": q.remaining_installments,
                "price_parcela": _brl(q.installment_value or 0),
            }
            for q in quotas
        ]
        _save_lead_snapshot(lead, snap)
        db.flush()
        return _wrap(
            [
                {
                    "text": (
                        f"Perfeito! Reservei a(s) cota(s) por {RESERVE_TTL} minutos. "
                        "Vamos revisar o resumo e seguir com contrato, conta e boleto da entrada."
                    ),
                    "button": "Continuar",
                    "next": int(STEP_HANDOFF_RESUMO),
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_HANDOFF_RESUMO:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        quotas_ui = snap.get("handoff_quotas") or []
        credit = snap.get("handoff_credit")
        entrada = snap.get("handoff_entrada")
        text = "Confira o resumo da sua opção:"
        if credit or entrada:
            text = (
                f"Confira o resumo: crédito {_brl(credit or 0)} · entrada {_brl(entrada or 0)}."
            )
        return _wrap(
            [
                {
                    "text": text,
                    "resumo": True,
                    "quotas": quotas_ui,
                    "button": "Continuar",
                    "next": int(STEP_PERSON_TYPE),
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_PERSON_TYPE:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        choice = str(data.get("option_save") or data.get("option_id") or "").strip().upper()
        if choice in {"PF", "PJ"}:
            snap["person_type"] = choice
            _save_lead_snapshot(lead, snap)
            db.flush()
            label = "CPF" if choice == "PF" else "CNPJ"
            return _wrap(
                [
                    {
                        "text": f"Informe o {label} do comprador:",
                        "input": {"name": "document", "label": label, "type": "text"},
                        "next": int(STEP_DOCUMENT),
                    }
                ],
                lead_id=lead.id,
            )
        return _wrap(
            [
                {
                    "text": "A compra é para pessoa física ou jurídica?",
                    "options": [
                        {"name": "Pessoa física (CPF)", "save": "PF", "next": int(STEP_PERSON_TYPE)},
                        {"name": "Pessoa jurídica (CNPJ)", "save": "PJ", "next": int(STEP_PERSON_TYPE)},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_DOCUMENT:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        person = str(snap.get("person_type") or "PF").upper()
        raw_doc = data.get("document")
        if raw_doc is None or str(raw_doc).strip() == "":
            label = "CPF" if person == "PF" else "CNPJ"
            return _wrap(
                [
                    {
                        "text": f"Informe o {label} do comprador:",
                        "input": {"name": "document", "label": label, "type": "text"},
                        "next": int(STEP_DOCUMENT),
                    }
                ],
                lead_id=lead.id,
            )
        try:
            from app.account_uniqueness import assert_valid_cpf_or_cnpj

            doc = assert_valid_cpf_or_cnpj(str(raw_doc), field_label="CPF" if person == "PF" else "CNPJ")
        except HTTPException as exc:
            label = "CPF" if person == "PF" else "CNPJ"
            return _retry(str(exc.detail), STEP_DOCUMENT, input_name="document", label=label, lead_id=lead.id)
        if person == "PF" and len(doc) != 11:
            return _retry("CPF inválido (informe 11 dígitos).", STEP_DOCUMENT, input_name="document", label="CPF", lead_id=lead.id)
        if person == "PJ" and len(doc) != 14:
            return _retry("CNPJ inválido (informe 14 dígitos).", STEP_DOCUMENT, input_name="document", label="CNPJ", lead_id=lead.id)
        lead.document = doc
        snap["document"] = doc
        _save_lead_snapshot(lead, snap)
        db.flush()
        if person == "PJ":
            return _wrap(
                [
                    {
                        "text": "Qual a razão social da empresa?",
                        "input": {"name": "razao_social", "label": "Razão social", "type": "text"},
                        "next": int(STEP_RAZAO),
                    }
                ],
                lead_id=lead.id,
            )
        return _wrap(
            [
                {
                    "text": "Qual o CEP do endereço de cobrança?",
                    "input": {"name": "zipcode", "label": "CEP", "type": "text"},
                    "next": int(STEP_ZIPCODE),
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_RAZAO:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        razao = str(data.get("razao_social") or "").strip()
        if len(razao) < 2:
            return _retry(
                "Informe a razão social.",
                STEP_RAZAO,
                input_name="razao_social",
                label="Razão social",
                lead_id=lead.id,
            )
        snap["razao_social"] = razao
        _save_lead_snapshot(lead, snap)
        db.flush()
        return _wrap(
            [
                {
                    "text": "Qual o CEP do endereço de cobrança?",
                    "input": {"name": "zipcode", "label": "CEP", "type": "text"},
                    "next": int(STEP_ZIPCODE),
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_ZIPCODE:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        raw_cep = data.get("zipcode")
        if raw_cep is None or str(raw_cep).strip() == "":
            return _wrap(
                [
                    {
                        "text": "Qual o CEP do endereço de cobrança?",
                        "input": {"name": "zipcode", "label": "CEP", "type": "text"},
                        "next": int(STEP_ZIPCODE),
                    }
                ],
                lead_id=lead.id,
            )
        try:
            looked = _lookup_cep(str(raw_cep))
        except HTTPException as exc:
            return _retry(str(exc.detail), STEP_ZIPCODE, input_name="zipcode", label="CEP", lead_id=lead.id)
        if not looked.get("street") or not looked.get("city") or not looked.get("uf"):
            return _retry(
                "CEP incompleto no serviço de consulta. Tente outro CEP.",
                STEP_ZIPCODE,
                input_name="zipcode",
                label="CEP",
                lead_id=lead.id,
            )
        address = snap.get("address") if isinstance(snap.get("address"), dict) else {}
        address.update(
            {
                "zipcode": _digits(str(raw_cep))[:8],
                "street": looked["street"],
                "neighborhood": looked.get("neighborhood") or "Centro",
                "city": looked["city"],
                "uf": looked["uf"],
            }
        )
        snap["address"] = address
        _save_lead_snapshot(lead, snap)
        db.flush()
        return _wrap(
            [
                {
                    "text": (
                        f"Encontrei {looked['street']} — {looked.get('neighborhood') or ''}, "
                        f"{looked['city']}/{looked['uf']}. Qual o número?"
                    ),
                    "input": {"name": "number", "label": "Número", "type": "text"},
                    "next": int(STEP_ADDRESS_NUMBER),
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_ADDRESS_NUMBER:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        number = str(data.get("number") or "").strip()
        if not number:
            return _retry(
                "Informe o número do endereço.",
                STEP_ADDRESS_NUMBER,
                input_name="number",
                label="Número",
                lead_id=lead.id,
            )
        address = snap.get("address") if isinstance(snap.get("address"), dict) else {}
        if not address.get("street") or not address.get("zipcode"):
            return _wrap(
                [
                    {
                        "text": "Precisamos do CEP antes do número.",
                        "input": {"name": "zipcode", "label": "CEP", "type": "text"},
                        "next": int(STEP_ZIPCODE),
                    }
                ],
                lead_id=lead.id,
            )
        # número pode vir como "123 apto 4" — separa complemento simples
        complement = str(data.get("complement") or "").strip()
        if not complement and " " in number:
            parts = number.split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                number, complement = parts[0], parts[1]
        address["number"] = number[:20]
        if complement:
            address["complement"] = complement[:40]
        snap["address"] = address
        _save_lead_snapshot(lead, snap)
        proposal = db.get(Proposal, snap.get("proposal_id")) if snap.get("proposal_id") else None
        if proposal:
            terms = seed_marketplace_lifecycle(json.loads(proposal.terms_json or "{}"))
            terms["person_type"] = snap.get("person_type") or "PF"
            terms["client_email"] = snap.get("email")
            if snap.get("razao_social"):
                terms["razao_social"] = snap["razao_social"]
            proposal.terms_json = json.dumps(terms, ensure_ascii=False)
        db.flush()
        person = str(snap.get("person_type") or "PF").upper()
        if person == "PJ":
            prompt = "Qual o ramo de atividade da empresa?"
            label = "Ramo de atividade"
        else:
            prompt = "Qual a sua profissão?"
            label = "Profissão"
        return _wrap(
            [
                {
                    "text": prompt,
                    "input": {"name": "profession", "label": label, "type": "text"},
                    "next": int(STEP_PROFESSION),
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_PROFESSION:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        person = str(snap.get("person_type") or "PF").upper()
        label = "Ramo de atividade" if person == "PJ" else "Profissão"
        raw = str(data.get("profession") or data.get("activity") or "").strip()
        if len(raw) < 2:
            return _retry(
                f"Informe {label.lower()}.",
                STEP_PROFESSION,
                input_name="profession",
                label=label,
                lead_id=lead.id,
            )
        if person == "PJ":
            snap["activity"] = raw
            snap["profession"] = raw
        else:
            snap["profession"] = raw
        _save_lead_snapshot(lead, snap)
        db.flush()
        income_label = "Faturamento mensal" if person == "PJ" else "Renda mensal"
        return _wrap(
            [
                {
                    "text": f"Qual o {income_label.lower()}?",
                    "input": {"name": "declared_income", "label": income_label, "type": "text"},
                    "next": int(STEP_INCOME_AMOUNT),
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_INCOME_AMOUNT:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        person = str(snap.get("person_type") or "PF").upper()
        income_label = "Faturamento mensal" if person == "PJ" else "Renda mensal"
        if data.get("declared_income") is None or str(data.get("declared_income") or "").strip() == "":
            return _wrap(
                [
                    {
                        "text": f"Qual o {income_label.lower()}?",
                        "input": {"name": "declared_income", "label": income_label, "type": "text"},
                        "next": int(STEP_INCOME_AMOUNT),
                    }
                ],
                lead_id=lead.id,
            )
        try:
            amount = _money_input(data.get("declared_income"))
        except HTTPException as exc:
            return _retry(
                str(exc.detail),
                STEP_INCOME_AMOUNT,
                input_name="declared_income",
                label=income_label,
                lead_id=lead.id,
            )
        if amount <= 0:
            return _retry(
                f"{income_label} precisa ser maior que zero.",
                STEP_INCOME_AMOUNT,
                input_name="declared_income",
                label=income_label,
                lead_id=lead.id,
            )
        snap["declared_income"] = str(amount)
        _save_lead_snapshot(lead, snap)
        db.flush()
        return _income_proof_prompt(lead, snap.get("income_proof") or [])

    if step == STEP_INCOME_PROOF:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        selected = [str(x) for x in (snap.get("income_proof") or []) if str(x) in INCOME_PROOF_OPTIONS]
        choice = str(data.get("option_save") or data.get("option_id") or "").strip().lower()
        if choice == "done":
            if not selected:
                return _wrap(
                    [
                        {
                            "text": "Selecione pelo menos uma forma de comprovação!",
                            **_income_proof_item(selected),
                        }
                    ],
                    lead_id=lead.id,
                )
            snap["income_proof"] = selected
            _save_lead_snapshot(lead, snap)
            proposal = db.get(Proposal, snap.get("proposal_id")) if snap.get("proposal_id") else None
            if proposal:
                terms = seed_marketplace_lifecycle(json.loads(proposal.terms_json or "{}"))
                terms["profession"] = snap.get("profession")
                terms["activity"] = snap.get("activity")
                terms["declared_income"] = snap.get("declared_income")
                terms["income_proof"] = selected
                proposal.terms_json = json.dumps(terms, ensure_ascii=False)
            db.flush()
            return _wrap(
                [
                    {
                        "text": "Dados profissionais salvos.",
                        "button": "Continuar",
                        "next": int(STEP_DOUBTS),
                    }
                ],
                lead_id=lead.id,
            )
        if choice in INCOME_PROOF_OPTIONS:
            if choice not in selected:
                selected.append(choice)
            snap["income_proof"] = selected
            _save_lead_snapshot(lead, snap)
            db.flush()
            return _income_proof_prompt(lead, selected)
        return _income_proof_prompt(lead, selected)

    if step == STEP_DOUBTS:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        choice = str(data.get("option_save") or data.get("option_id") or "").strip().lower()
        if choice in {"no", "nao", "não", "0", "false"}:
            return _wrap(
                [
                    {
                        "text": "Perfeito. Vamos ao contrato de intermediação.",
                        "button": "Continuar para o contrato",
                        "next": int(STEP_CONTRACT_PLACEHOLDER),
                    }
                ],
                lead_id=lead.id,
            )
        if choice in {"yes", "sim", "1", "true"}:
            return _wrap([_faq_list_item(db, org.id)], lead_id=lead.id)
        return _doubts_prompt(lead_id=lead.id)

    if step in {STEP_FAQ_LIST, "94"}:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        return _wrap([_faq_list_item(db, org.id)], lead_id=lead.id)

    if step in {STEP_FAQ_ANSWER, STEP_FAQ_ANSWER_LEGACY}:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        faq_id = str(
            data.get("faq_id")
            or data.get("option_id")
            or data.get("option_save")
            or ""
        ).strip()
        if isinstance(data.get("option_save"), dict):
            faq_id = str(data["option_save"].get("faq_id") or faq_id)
        row = _faq_by_id(db, org.id, faq_id)
        if not row:
            item = _faq_list_item(db, org.id)
            item["text"] = "Não encontrei essa dúvida. Escolha outra na lista:"
            return _wrap([item], lead_id=lead.id)
        return _wrap(
            [
                {"text": row["txt"]},
                {
                    "text": "Mais alguma dúvida?",
                    "options": [
                        {"name": "Sim, ver outras dúvidas", "save": "yes", "next": int(STEP_FAQ_LIST)},
                        {"name": "Não, seguir para o contrato", "save": "no", "next": int(STEP_DOUBTS)},
                    ],
                },
            ],
            lead_id=lead.id,
        )

    if step == STEP_CONTRACT_PLACEHOLDER:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        if not snap.get("person_type") or not (lead.document or snap.get("document")):
            return _wrap(
                [
                    {
                        "text": "Antes do contrato, precisamos dos dados do comprador.",
                        "button": "Informar dados",
                        "next": int(STEP_PERSON_TYPE),
                    }
                ],
                lead_id=lead.id,
            )
        address = snap.get("address") if isinstance(snap.get("address"), dict) else {}
        if not address.get("zipcode") or not address.get("number"):
            return _wrap(
                [
                    {
                        "text": "Antes do contrato, informe o endereço de cobrança.",
                        "input": {"name": "zipcode", "label": "CEP", "type": "text"},
                        "next": int(STEP_ZIPCODE),
                    }
                ],
                lead_id=lead.id,
            )
        if not snap.get("profession") and not snap.get("activity"):
            person = str(snap.get("person_type") or "PF").upper()
            label = "Ramo de atividade" if person == "PJ" else "Profissão"
            return _wrap(
                [
                    {
                        "text": f"Antes do contrato, informe {label.lower()}.",
                        "input": {"name": "profession", "label": label, "type": "text"},
                        "next": int(STEP_PROFESSION),
                    }
                ],
                lead_id=lead.id,
            )
        if not snap.get("declared_income"):
            person = str(snap.get("person_type") or "PF").upper()
            income_label = "Faturamento mensal" if person == "PJ" else "Renda mensal"
            return _wrap(
                [
                    {
                        "text": f"Antes do contrato, informe o {income_label.lower()}.",
                        "input": {"name": "declared_income", "label": income_label, "type": "text"},
                        "next": int(STEP_INCOME_AMOUNT),
                    }
                ],
                lead_id=lead.id,
            )
        if not (snap.get("income_proof") or []):
            return _income_proof_prompt(lead, [])
        accepted = str(data.get("option_save") or data.get("option_id") or data.get("contract") or "").strip().lower()
        if accepted in {"accept", "1", "true", "aceito", "contrato_aceito"}:
            from datetime import UTC, datetime

            snap["contract_accepted_at"] = datetime.now(UTC).isoformat()
            html = _contract_html(lead, snap)
            snap["contract_html"] = html
            _save_lead_snapshot(lead, snap)
            proposal = db.get(Proposal, snap.get("proposal_id")) if snap.get("proposal_id") else None
            if proposal:
                terms = seed_marketplace_lifecycle(json.loads(proposal.terms_json or "{}"))
                terms["contract_ack"] = {
                    "accepted_at": snap["contract_accepted_at"],
                    "channel": SOURCE,
                    "provider": "SITE_CHAT_ACK",
                }
                terms["contract_html"] = html
                terms["person_type"] = snap.get("person_type") or "PF"
                proposal.terms_json = json.dumps(terms, ensure_ascii=False)
                db.flush()
                zapsign_block = None
                from app.marketplace_zapsign_service import ensure_marketplace_zapsign

                zapsign_block = ensure_marketplace_zapsign(
                    db,
                    lead=lead,
                    proposal=proposal,
                    html=html,
                    ack=terms["contract_ack"],
                    signer_email=str(snap.get("email") or ""),
                    signer_name=lead.name,
                )
            else:
                zapsign_block = None
            db.flush()
            if zapsign_block and zapsign_block.get("sign_url"):
                return _wrap(
                    [
                        {
                            "text": (
                                "Contrato registrado. A assinatura digital foi enviada pelo ZapSign — "
                                "você pode assinar agora ou depois no escritório virtual."
                            ),
                            "options": [
                                {"name": "Assinar contrato (ZapSign)", "link": zapsign_block["sign_url"]},
                                {"name": "Continuar", "next": int(STEP_ACCOUNT_CTA)},
                            ],
                        }
                    ],
                    lead_id=lead.id,
                )
            follow_text = "Contrato de intermediação registrado."
            if zapsign_block and zapsign_block.get("status") == "ERROR":
                follow_text += " A assinatura ZapSign poderá ser reenviada pelo escritório virtual."
            else:
                follow_text += " Agora vamos criar o acesso ao escritório virtual."
            return _wrap(
                [
                    {
                        "text": follow_text,
                        "button": "Continuar",
                        "next": int(STEP_ACCOUNT_CTA),
                    }
                ],
                lead_id=lead.id,
            )
        if accepted in {"decline", "0", "false", "duvidas"}:
            return _wrap(
                [
                    {
                        "text": (
                            "Sem problemas. Podemos esclarecer dúvidas antes de assinar o contrato."
                        ),
                        "button": "Ver dúvidas",
                        "next": int(STEP_DOUBTS),
                    }
                ],
                lead_id=lead.id,
            )
        html = _contract_html(lead, snap)
        return _wrap(
            [
                {
                    "text": "Leia o contrato de intermediação e aceite para continuar:",
                    "contract": True,
                    "html": html,
                    "next": int(STEP_CONTRACT_PLACEHOLDER),
                    "next_decline": int(STEP_DOUBTS),
                    "accept_save": "accept",
                    "decline_save": "decline",
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_ACCOUNT_CTA:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        email = str(snap.get("email") or "").strip()
        from urllib.parse import quote

        from app.account_uniqueness import find_user_by_email

        qs = f"email={quote(email)}&name={quote(lead.name or '')}&lead_id={quote(lead.id)}"
        existing = find_user_by_email(db, email) if email else None

        # já vinculado
        if lead.client_user_id:
            return _wrap(
                [
                    {
                        "text": "Sua conta já está vinculada a esta compra. Vamos ao boleto da entrada.",
                        "button": "Continuar para o boleto",
                        "next": int(STEP_BOLETO_HANDOFF),
                    }
                ],
                lead_id=lead.id,
            )

        password = data.get("password")
        if password is not None and str(password).strip() != "":
            if existing and existing.last_login_at is not None:
                return _wrap(
                    [
                        {
                            "text": "Este e-mail já tem conta LETTER. Entre no escritório virtual para continuar.",
                            "options": [
                                {
                                    "name": "Ir para o login",
                                    "link": f"/login?lead_id={quote(lead.id)}&next=/modules/minhas-compras",
                                },
                                {"name": "Continuar para o boleto", "next": int(STEP_BOLETO_HANDOFF)},
                            ],
                        }
                    ],
                    lead_id=lead.id,
                )
            pwd = str(password)
            if len(pwd) < 10:
                return _retry(
                    "A senha deve ter ao menos 10 caracteres.",
                    STEP_ACCOUNT_CTA,
                    input_name="password",
                    label="Senha",
                    lead_id=lead.id,
                    input_type="password",
                )
            try:
                from app.public_site_service import register_public_client

                register_public_client(
                    db,
                    name=lead.name or "Cliente LETTER",
                    email=email,
                    phone=lead.phone or "",
                    password=pwd,
                    document=lead.document or snap.get("document"),
                    chat_lead_id=lead.id,
                )
            except HTTPException as exc:
                detail = str(exc.detail)
                if "já cadastrado" in detail.lower() or exc.status_code == 409:
                    return _wrap(
                        [
                            {
                                "text": "Este e-mail já tem conta. Entre no escritório virtual.",
                                "options": [
                                    {
                                        "name": "Ir para o login",
                                        "link": f"/login?lead_id={quote(lead.id)}&next=/modules/minhas-compras",
                                    },
                                    {"name": "Continuar para o boleto", "next": int(STEP_BOLETO_HANDOFF)},
                                ],
                            }
                        ],
                        lead_id=lead.id,
                    )
                return _retry(
                    detail,
                    STEP_ACCOUNT_CTA,
                    input_name="password",
                    label="Senha",
                    lead_id=lead.id,
                    input_type="password",
                )
            db.flush()
            return _wrap(
                [
                    {
                        "text": "Conta criada e compra vinculada. Agora emitimos o boleto da entrada.",
                        "button": "Continuar para o boleto",
                        "next": int(STEP_BOLETO_HANDOFF),
                    }
                ],
                lead_id=lead.id,
            )

        if existing and existing.last_login_at is not None:
            return _wrap(
                [
                    {
                        "text": (
                            "Este e-mail já tem conta LETTER. Entre no escritório virtual para "
                            "acompanhar boleto e documentos."
                        ),
                        "options": [
                            {
                                "name": "Ir para o login",
                                "link": f"/login?lead_id={quote(lead.id)}&next=/modules/minhas-compras",
                            },
                            {"name": "Abrir cadastro", "link": f"/cadastro?{qs}"},
                            {"name": "Continuar para o boleto", "next": int(STEP_BOLETO_HANDOFF)},
                        ],
                    }
                ],
                lead_id=lead.id,
            )

        # primeira visita: pede senha in-chat
        if "password" not in data:
            return _wrap(
                [
                    {
                        "text": (
                            "Cadastre uma senha para acessar o escritório virtual LETTER "
                            "(mínimo 10 caracteres)."
                        ),
                        "input": {"name": "password", "label": "Senha", "type": "password"},
                        "next": int(STEP_ACCOUNT_CTA),
                    }
                ],
                lead_id=lead.id,
            )

        return _wrap(
            [
                {
                    "text": "Cadastre uma senha para acessar o escritório virtual.",
                    "input": {"name": "password", "label": "Senha", "type": "password"},
                    "next": int(STEP_ACCOUNT_CTA),
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_BOLETO_HANDOFF:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        from app.inter_boleto_service import issue_marketplace_boleto

        issued = issue_marketplace_boleto(db, actor, lead.id)
        boleto = issued.get("boleto") or {}
        token = boleto.get("download_token")
        pdf_path = f"/api/v1/marketplace/cadastros/{lead.id}/boleto/{token}" if token else None
        amount = boleto.get("amount")
        text = "Boleto da entrada gerado."
        if amount:
            text = f"Boleto da entrada gerado no valor de {_brl(amount)}."
        options = []
        if pdf_path:
            options.append({"name": "Baixar boleto (PDF)", "link": pdf_path})
        options.extend(
            [
                {"name": "Falar no WhatsApp", "link": f"https://wa.me/55{_digits(settings.company_phone)}"},
                {"name": "Criar / acessar conta", "link": "/cadastro"},
                {"name": "Concluir", "next": int(STEP_DONE_FINAL)},
            ]
        )
        db.flush()
        return _wrap(
            [{"text": text + " Guarde o comprovante; após o pagamento a venda segue para transferência.", "options": options}],
            lead_id=lead.id,
        )

    if step == STEP_DONE_FINAL:
        return _wrap(
            [
                {
                    "text": (
                        "Pronto! Sua reserva está ativa. Acompanhe pelo painel ou fale conosco se precisar de ajuda."
                    ),
                    "options": [
                        {"name": "Falar no WhatsApp", "link": f"https://wa.me/55{_digits(settings.company_phone)}"},
                        {"name": "Criar / acessar conta", "link": "/cadastro"},
                        {"name": "Nova simulação", "next": 0},
                    ],
                }
            ],
            lead_id=lead.id if lead else None,
        )

    # --- Capital de Giro (SDC) ---
    if step == STEP_SDC_ASSET_TYPE:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        lead.product_interest = "SDC"
        snap = _lead_snapshot(lead)
        snap["flow"] = "SDC"
        snap["product"] = "SDC"
        asset_type = str(data.get("option_save") or data.get("option_id") or "").strip().lower()
        if asset_type in {"imovel", "veiculo_leve", "veiculo_pesado", "maquina"}:
            snap["asset_type"] = asset_type
            if asset_type == "imovel":
                snap.pop("asset_year", None)
            _save_lead_snapshot(lead, snap)
            db.flush()
            if asset_type == "imovel":
                return _wrap(
                    [
                        {
                            "text": "Qual o valor do bem dado em garantia?",
                            "input": {"name": "asset_value", "label": "Valor do bem", "type": "text"},
                            "next": int(STEP_SDC_VALUE),
                        }
                    ],
                    lead_id=lead.id,
                )
            return _wrap(
                [
                    {
                        "text": "Qual o ano de fabricação do bem?",
                        "input": {"name": "asset_year", "label": "Ano", "type": "number"},
                        "next": int(STEP_SDC_YEAR),
                    }
                ],
                lead_id=lead.id,
            )
        _save_lead_snapshot(lead, snap)
        db.flush()
        return _wrap(
            [
                {
                    "text": "Qual o tipo do bem em garantia?",
                    "options": [
                        {"name": "Imóvel", "next": int(STEP_SDC_ASSET_TYPE), "save": "imovel", "id": "imovel"},
                        {"name": "Veículo leve", "next": int(STEP_SDC_ASSET_TYPE), "save": "veiculo_leve", "id": "veiculo_leve"},
                        {"name": "Veículo pesado", "next": int(STEP_SDC_ASSET_TYPE), "save": "veiculo_pesado", "id": "veiculo_pesado"},
                        {"name": "Máquina", "next": int(STEP_SDC_ASSET_TYPE), "save": "maquina", "id": "maquina"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_SDC_YEAR:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        try:
            year = int(str(data.get("asset_year") or data.get("option_id") or "0"))
        except ValueError:
            year = 0
        if year < 1980 or year > date.today().year + 1:
            return _retry(
                "Informe um ano de fabricação válido!",
                STEP_SDC_YEAR,
                input_name="asset_year",
                label="Ano",
                lead_id=lead.id,
            )
        snap = _lead_snapshot(lead)
        snap["asset_year"] = year
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "Qual o valor do bem dado em garantia?",
                    "input": {"name": "asset_value", "label": "Valor do bem", "type": "text"},
                    "next": int(STEP_SDC_VALUE),
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_SDC_VALUE:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        try:
            asset = _money_input(data.get("asset_value"))
        except HTTPException:
            return _retry("Informe o valor do bem!", STEP_SDC_VALUE, input_name="asset_value", label="Valor do bem", lead_id=lead.id)
        if asset <= 0:
            return _retry("Informe o valor do bem!", STEP_SDC_VALUE, input_name="asset_value", label="Valor do bem", lead_id=lead.id)
        snap = _lead_snapshot(lead)
        snap["asset_value"] = str(asset)
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "O bem está quitado?",
                    "options": [
                        {"name": "Sim", "next": int(STEP_SDC_LIEN), "save": "1", "id": "paid_yes"},
                        {"name": "Não", "next": int(STEP_SDC_LIEN), "save": "0", "id": "paid_no"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_SDC_PAID_OFF:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        snap["asset_paid_off"] = data.get("option_save") == "1" or data.get("option_id") == "paid_yes"
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "O bem possui alguma pendência (alienação, restrição)?",
                    "options": [
                        {"name": "Sim", "next": int(STEP_SDC_DOCS), "save": "1", "id": "lien_yes"},
                        {"name": "Não", "next": int(STEP_SDC_DOCS), "save": "0", "id": "lien_no"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_SDC_LIEN:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        oid = str(data.get("option_id") or "")
        if oid in {"paid_yes", "paid_no"}:
            snap["asset_paid_off"] = oid == "paid_yes"
            _save_lead_snapshot(lead, snap)
            return _wrap(
                [
                    {
                        "text": "O bem possui alguma pendência (alienação, restrição)?",
                        "options": [
                            {"name": "Sim", "next": int(STEP_SDC_DOCS), "save": "1", "id": "lien_yes"},
                            {"name": "Não", "next": int(STEP_SDC_DOCS), "save": "0", "id": "lien_no"},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        if oid in {"lien_yes", "lien_no"}:
            snap["asset_has_lien"] = oid == "lien_yes"
            _save_lead_snapshot(lead, snap)
            return _wrap(
                [
                    {
                        "text": "A documentação do bem está completa?",
                        "options": [
                            {"name": "Sim", "next": int(STEP_SDC_EVAL), "save": "1", "id": "docs_yes"},
                            {"name": "Não", "next": int(STEP_SDC_EVAL), "save": "0", "id": "docs_no"},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        snap["asset_paid_off"] = data.get("option_save") == "1"
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "O bem possui alguma pendência (alienação, restrição)?",
                    "options": [
                        {"name": "Sim", "next": int(STEP_SDC_DOCS), "save": "1", "id": "lien_yes"},
                        {"name": "Não", "next": int(STEP_SDC_DOCS), "save": "0", "id": "lien_no"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_SDC_DOCS:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        oid = str(data.get("option_id") or "")
        if oid in {"lien_yes", "lien_no"}:
            snap["asset_has_lien"] = oid == "lien_yes"
            _save_lead_snapshot(lead, snap)
            return _wrap(
                [
                    {
                        "text": "A documentação do bem está completa?",
                        "options": [
                            {"name": "Sim", "next": int(STEP_SDC_EVAL), "save": "1", "id": "docs_yes"},
                            {"name": "Não", "next": int(STEP_SDC_EVAL), "save": "0", "id": "docs_no"},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        snap["docs_complete"] = oid == "docs_yes" or data.get("option_save") == "1"
        _save_lead_snapshot(lead, snap)
        data = {**data, "option_id": "docs_yes" if snap["docs_complete"] else "docs_no"}
        step = STEP_SDC_EVAL

    if step == STEP_SDC_EVAL:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        oid = str(data.get("option_id") or "")
        if oid in {"docs_yes", "docs_no"}:
            snap["docs_complete"] = oid == "docs_yes"
            _save_lead_snapshot(lead, snap)
        payload = {
            "asset_type": snap.get("asset_type") or "imovel",
            "asset_value": snap.get("asset_value") or "0",
            "asset_year": snap.get("asset_year"),
            "asset_paid_off": bool(snap.get("asset_paid_off")),
            "asset_has_lien": bool(snap.get("asset_has_lien")),
            "docs_complete": bool(snap.get("docs_complete")),
        }
        result = evaluate_sdc_desk(payload)
        snap["sdc_evaluation"] = result
        _save_lead_snapshot(lead, snap)
        db.flush()
        sdc_card = {
            "viavel": bool(result.get("viable")),
            "valor_alavancado_fmt": _brl(result.get("credito_estimado") or 0),
            "prazo_fmt": f"{int(result.get('prazo_meses') or 0)} meses" if result.get("viable") else "—",
            "parcela_fmt": _brl(result.get("parcela_estimada") or 0),
            "taxa_fmt": f"{result.get('taxa_juros_mensal') or '0'}% a.m." if result.get("viable") else "—",
            "motivos": list(result.get("motivos") or []),
        }
        item: dict[str, Any] = {
            "text": result.get("message") or ("Operação viável" if result.get("viable") else "Operação não viável"),
            "sdc_result": sdc_card,
        }
        if result.get("viable"):
            item["next"] = int(STEP_SDC_CONFIRM)
            item["button"] = "Continuar"
        else:
            item["options"] = [
                {"name": "Mudar categoria", "next": int(STEP_CATEGORY)},
                {"name": "Recomeçar", "next": 0},
            ]
        return _wrap([item], lead_id=lead.id)

    if step == STEP_CATEGORY:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        return _wrap(
            [
                {
                    "text": "O que você deseja financiar?",
                    "options": [
                        {"name": "Imóvel", "next": int(STEP_DIRTY), "save": "REAL_ESTATE", "id": "REAL_ESTATE"},
                        {"name": "Veículo", "next": int(STEP_YEAR), "save": "VEHICLE", "id": "VEHICLE"},
                        {"name": "Capital de Giro (SDC)", "next": int(STEP_SDC_ASSET_TYPE), "save": "SDC", "id": "SDC"},
                        {"name": "Flash Capital", "next": int(STEP_FLASH_ASSET_TYPE), "save": "FLASH", "id": "FLASH"},
                        {"name": "QuitCon", "next": int(STEP_QUITCON_BALANCE), "save": "QUITCON", "id": "QUITCON"},
                        {"name": "Vender minha cota", "link": "/vender-minha-cota", "save": "open_page"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_SDC_CONFIRM:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        if snap.get("sdc_solicitation_id"):
            return _wrap(
                [
                    {
                        "text": (
                            "Sua solicitação de Capital de Giro já está na mesa SDC. "
                            "Nossa equipe pede a documentação e segue a análise."
                        ),
                        "options": [
                            {"name": "Falar no WhatsApp", "link": f"https://wa.me/55{_digits(settings.company_phone)}"},
                            {"name": "Nova simulação", "next": 0},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        evaluation = snap.get("sdc_evaluation") or {}
        if not evaluation.get("viable"):
            return _wrap(
                [
                    {
                        "text": "A operação não está viável com os dados atuais. Ajuste a garantia ou a categoria.",
                        "options": [
                            {"name": "Mudar categoria", "next": int(STEP_CATEGORY)},
                            {"name": "Recomeçar", "next": 0},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        store_payload = {
            "asset_type": snap.get("asset_type") or "imovel",
            "asset_value": snap.get("asset_value") or "0",
            "asset_year": snap.get("asset_year"),
            "asset_paid_off": bool(snap.get("asset_paid_off")),
            "asset_has_lien": bool(snap.get("asset_has_lien")),
            "docs_complete": bool(snap.get("docs_complete")),
            "contact_name": lead.name or snap.get("name") or "Visitante",
            "contact_email": snap.get("email") or "site@letter.app.br",
            "contact_phone": lead.phone or snap.get("phone") or "",
            "person_type": "PF",
        }
        try:
            solicitation = store_sdc_solicitation(db, actor, store_payload)
        except HTTPException as exc:
            detail = exc.detail
            message = detail.get("message") if isinstance(detail, dict) else str(detail)
            motivos = detail.get("motivos") if isinstance(detail, dict) else []
            return _wrap(
                [
                    {
                        "text": message or "Não foi possível registrar a solicitação SDC.",
                        "sdc_result": {
                            "viavel": False,
                            "valor_alavancado_fmt": "R$ 0,00",
                            "prazo_fmt": "—",
                            "parcela_fmt": "R$ 0,00",
                            "taxa_fmt": "—",
                            "motivos": motivos or [message],
                        },
                        "options": [
                            {"name": "Mudar categoria", "next": int(STEP_CATEGORY)},
                            {"name": "Recomeçar", "next": 0},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        snap["sdc_solicitation_id"] = solicitation.id
        lead.product_interest = "SDC"
        lead.status = "QUALIFIED"
        try:
            detail = json.loads(solicitation.evaluation_json or "{}")
            if isinstance(detail, dict):
                detail["channel"] = SOURCE
                detail["lead_id"] = lead.id
                solicitation.evaluation_json = json.dumps(detail, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        _save_lead_snapshot(lead, snap)
        db.flush()
        return _wrap(
            [
                {
                    "text": (
                        "Perfeito! Registrei sua solicitação de Capital de Giro na mesa SDC "
                        f"(crédito estimado {_brl(solicitation.credit_estimated)}). "
                        "Envie a documentação quando a equipe entrar em contato."
                    ),
                    "options": [
                        {"name": "Falar no WhatsApp", "link": f"https://wa.me/55{_digits(settings.company_phone)}"},
                        {"name": "Criar conta / acompanhar", "link": "/login"},
                        {"name": "Nova simulação", "next": 0},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    # --- Flash Capital ---
    if step == STEP_FLASH_ASSET_TYPE:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        lead.product_interest = "FLASH_CREDIT"
        snap = _lead_snapshot(lead)
        snap["flow"] = "FLASH"
        snap["product"] = "FLASH_CREDIT"
        asset_type = str(data.get("option_save") or data.get("option_id") or "").strip().lower()
        if asset_type in {"imovel", "veiculo_leve", "veiculo_pesado", "maquina"}:
            snap["asset_type"] = asset_type
            if asset_type == "imovel":
                snap.pop("asset_year", None)
            _save_lead_snapshot(lead, snap)
            db.flush()
            if asset_type == "imovel":
                return _wrap(
                    [
                        {
                            "text": "Qual o valor do bem dado em garantia (Flash Capital — LTV até 40%)?",
                            "input": {"name": "asset_value", "label": "Valor do bem", "type": "text"},
                            "next": int(STEP_FLASH_VALUE),
                        }
                    ],
                    lead_id=lead.id,
                )
            return _wrap(
                [
                    {
                        "text": "Qual o ano de fabricação do bem?",
                        "input": {"name": "asset_year", "label": "Ano", "type": "number"},
                        "next": int(STEP_FLASH_YEAR),
                    }
                ],
                lead_id=lead.id,
            )
        _save_lead_snapshot(lead, snap)
        db.flush()
        return _wrap(
            [
                {
                    "text": "Flash Capital — qual o tipo do bem em garantia?",
                    "options": [
                        {"name": "Imóvel", "next": int(STEP_FLASH_ASSET_TYPE), "save": "imovel", "id": "imovel"},
                        {"name": "Veículo leve", "next": int(STEP_FLASH_ASSET_TYPE), "save": "veiculo_leve", "id": "veiculo_leve"},
                        {"name": "Veículo pesado", "next": int(STEP_FLASH_ASSET_TYPE), "save": "veiculo_pesado", "id": "veiculo_pesado"},
                        {"name": "Máquina", "next": int(STEP_FLASH_ASSET_TYPE), "save": "maquina", "id": "maquina"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_FLASH_YEAR:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        try:
            year = int(str(data.get("asset_year") or data.get("option_id") or "0"))
        except ValueError:
            year = 0
        if year < 1980 or year > date.today().year + 1:
            return _retry(
                "Informe um ano de fabricação válido!",
                STEP_FLASH_YEAR,
                input_name="asset_year",
                label="Ano",
                lead_id=lead.id,
            )
        snap = _lead_snapshot(lead)
        snap["asset_year"] = year
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "Qual o valor do bem dado em garantia?",
                    "input": {"name": "asset_value", "label": "Valor do bem", "type": "text"},
                    "next": int(STEP_FLASH_VALUE),
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_FLASH_VALUE:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        try:
            asset = _money_input(data.get("asset_value"))
        except HTTPException:
            return _retry("Informe o valor do bem!", STEP_FLASH_VALUE, input_name="asset_value", label="Valor do bem", lead_id=lead.id)
        if asset <= 0:
            return _retry("Informe o valor do bem!", STEP_FLASH_VALUE, input_name="asset_value", label="Valor do bem", lead_id=lead.id)
        snap = _lead_snapshot(lead)
        snap["asset_value"] = str(asset)
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "O bem está quitado?",
                    "options": [
                        {"name": "Sim", "next": int(STEP_FLASH_LIEN), "save": "1", "id": "paid_yes"},
                        {"name": "Não", "next": int(STEP_FLASH_LIEN), "save": "0", "id": "paid_no"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_FLASH_PAID_OFF:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        snap["asset_paid_off"] = data.get("option_save") == "1" or data.get("option_id") == "paid_yes"
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "O bem possui alguma pendência (alienação, restrição)?",
                    "options": [
                        {"name": "Sim", "next": int(STEP_FLASH_DOCS), "save": "1", "id": "lien_yes"},
                        {"name": "Não", "next": int(STEP_FLASH_DOCS), "save": "0", "id": "lien_no"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_FLASH_LIEN:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        oid = str(data.get("option_id") or "")
        if oid in {"paid_yes", "paid_no"}:
            snap["asset_paid_off"] = oid == "paid_yes"
            _save_lead_snapshot(lead, snap)
            return _wrap(
                [
                    {
                        "text": "O bem possui alguma pendência (alienação, restrição)?",
                        "options": [
                            {"name": "Sim", "next": int(STEP_FLASH_DOCS), "save": "1", "id": "lien_yes"},
                            {"name": "Não", "next": int(STEP_FLASH_DOCS), "save": "0", "id": "lien_no"},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        if oid in {"lien_yes", "lien_no"}:
            snap["asset_has_lien"] = oid == "lien_yes"
            _save_lead_snapshot(lead, snap)
            return _wrap(
                [
                    {
                        "text": "A documentação do bem está completa?",
                        "options": [
                            {"name": "Sim", "next": int(STEP_FLASH_TERM), "save": "1", "id": "docs_yes"},
                            {"name": "Não", "next": int(STEP_FLASH_TERM), "save": "0", "id": "docs_no"},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        snap["asset_paid_off"] = data.get("option_save") == "1"
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "O bem possui alguma pendência (alienação, restrição)?",
                    "options": [
                        {"name": "Sim", "next": int(STEP_FLASH_DOCS), "save": "1", "id": "lien_yes"},
                        {"name": "Não", "next": int(STEP_FLASH_DOCS), "save": "0", "id": "lien_no"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_FLASH_DOCS:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        oid = str(data.get("option_id") or "")
        if oid in {"lien_yes", "lien_no"}:
            snap["asset_has_lien"] = oid == "lien_yes"
            _save_lead_snapshot(lead, snap)
            return _wrap(
                [
                    {
                        "text": "A documentação do bem está completa?",
                        "options": [
                            {"name": "Sim", "next": int(STEP_FLASH_TERM), "save": "1", "id": "docs_yes"},
                            {"name": "Não", "next": int(STEP_FLASH_TERM), "save": "0", "id": "docs_no"},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        snap["docs_complete"] = oid == "docs_yes" or data.get("option_save") == "1"
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "Qual o prazo desejado?",
                    "options": [
                        {"name": "36 meses", "next": int(STEP_FLASH_EVAL), "save": "36", "id": "term_36"},
                        {"name": "60 meses", "next": int(STEP_FLASH_EVAL), "save": "60", "id": "term_60"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_FLASH_TERM:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        oid = str(data.get("option_id") or "")
        if oid in {"docs_yes", "docs_no"}:
            snap["docs_complete"] = oid == "docs_yes"
            _save_lead_snapshot(lead, snap)
            return _wrap(
                [
                    {
                        "text": "Qual o prazo desejado?",
                        "options": [
                            {"name": "36 meses", "next": int(STEP_FLASH_EVAL), "save": "36", "id": "term_36"},
                            {"name": "60 meses", "next": int(STEP_FLASH_EVAL), "save": "60", "id": "term_60"},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        term_raw = str(data.get("option_save") or oid or "36").replace("term_", "")
        try:
            term = int(term_raw)
        except ValueError:
            term = 36
        if term not in {36, 60}:
            term = 36
        snap["term_months"] = term
        _save_lead_snapshot(lead, snap)
        data = {**data, "option_id": f"term_{term}", "option_save": str(term)}
        step = STEP_FLASH_EVAL

    if step == STEP_FLASH_EVAL:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        oid = str(data.get("option_id") or "")
        if oid in {"term_36", "term_60"} or str(data.get("option_save") or "") in {"36", "60"}:
            term_raw = str(data.get("option_save") or oid).replace("term_", "")
            try:
                snap["term_months"] = int(term_raw)
            except ValueError:
                snap["term_months"] = 36
            _save_lead_snapshot(lead, snap)
        payload = {
            "asset_type": snap.get("asset_type") or "imovel",
            "asset_value": snap.get("asset_value") or "0",
            "asset_year": snap.get("asset_year"),
            "asset_paid_off": bool(snap.get("asset_paid_off")),
            "asset_has_lien": bool(snap.get("asset_has_lien")),
            "docs_complete": bool(snap.get("docs_complete")),
            "term_months": int(snap.get("term_months") or 36),
            "capital_source": "RETAIL",
        }
        result = evaluate_flash_desk(payload)
        snap["flash_evaluation"] = result
        _save_lead_snapshot(lead, snap)
        db.flush()
        flash_card = {
            "viavel": bool(result.get("viable")),
            "principal_fmt": _brl(result.get("principal") or 0),
            "ltv_fmt": f"{result.get('ltv_percent') or '0'}%" if result.get("viable") else "—",
            "parcela_fmt": _brl(result.get("monthly_payment") or 0),
            "prazo_fmt": f"{int(result.get('term_months') or 0)} meses" if result.get("viable") else "—",
            "liquido_fmt": _brl(result.get("net_payout") or 0),
            "motivos": list(result.get("motivos") or []),
        }
        item: dict[str, Any] = {
            "text": result.get("message") or ("Operação viável" if result.get("viable") else "Operação não viável"),
            "flash_result": flash_card,
        }
        if result.get("viable"):
            item["next"] = int(STEP_FLASH_CONFIRM)
            item["button"] = "Continuar"
        else:
            item["options"] = [
                {"name": "Mudar categoria", "next": int(STEP_CATEGORY)},
                {"name": "Recomeçar", "next": 0},
            ]
        return _wrap([item], lead_id=lead.id)

    if step == STEP_FLASH_CONFIRM:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        if snap.get("flash_solicitation_id"):
            return _wrap(
                [
                    {
                        "text": (
                            "Sua solicitação Flash Capital já está na mesa. "
                            "Nossa equipe pede a documentação e segue a análise."
                        ),
                        "options": [
                            {"name": "Falar no WhatsApp", "link": f"https://wa.me/55{_digits(settings.company_phone)}"},
                            {"name": "Nova simulação", "next": 0},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        evaluation = snap.get("flash_evaluation") or {}
        if not evaluation.get("viable"):
            return _wrap(
                [
                    {
                        "text": "A operação Flash não está viável com os dados atuais. Ajuste a garantia ou a categoria.",
                        "options": [
                            {"name": "Mudar categoria", "next": int(STEP_CATEGORY)},
                            {"name": "Recomeçar", "next": 0},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        store_payload = {
            "asset_type": snap.get("asset_type") or "imovel",
            "asset_value": snap.get("asset_value") or "0",
            "asset_year": snap.get("asset_year"),
            "asset_paid_off": bool(snap.get("asset_paid_off")),
            "asset_has_lien": bool(snap.get("asset_has_lien")),
            "docs_complete": bool(snap.get("docs_complete")),
            "term_months": int(snap.get("term_months") or evaluation.get("term_months") or 36),
            "capital_source": "RETAIL",
            "contact_name": lead.name or snap.get("name") or "Visitante",
            "contact_email": snap.get("email") or "site@letter.app.br",
            "contact_phone": lead.phone or snap.get("phone") or "",
            "person_type": "PF",
        }
        try:
            solicitation = store_flash_solicitation(db, actor, store_payload)
        except HTTPException as exc:
            detail = exc.detail
            message = detail.get("message") if isinstance(detail, dict) else str(detail)
            motivos = detail.get("motivos") if isinstance(detail, dict) else []
            return _wrap(
                [
                    {
                        "text": message or "Não foi possível registrar a solicitação Flash Capital.",
                        "flash_result": {
                            "viavel": False,
                            "principal_fmt": "R$ 0,00",
                            "ltv_fmt": "—",
                            "parcela_fmt": "R$ 0,00",
                            "prazo_fmt": "—",
                            "liquido_fmt": "R$ 0,00",
                            "motivos": motivos or [message],
                        },
                        "options": [
                            {"name": "Mudar categoria", "next": int(STEP_CATEGORY)},
                            {"name": "Recomeçar", "next": 0},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        snap["flash_solicitation_id"] = solicitation.id
        lead.product_interest = "FLASH_CREDIT"
        lead.status = "QUALIFIED"
        try:
            detail = json.loads(solicitation.evaluation_json or "{}")
            if isinstance(detail, dict):
                detail["channel"] = SOURCE
                detail["lead_id"] = lead.id
                solicitation.evaluation_json = json.dumps(detail, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        _save_lead_snapshot(lead, snap)
        db.flush()
        return _wrap(
            [
                {
                    "text": (
                        "Perfeito! Registrei sua solicitação Flash Capital na mesa "
                        f"(principal {_brl(solicitation.principal)}, LTV {solicitation.ltv_percent}%). "
                        "Envie a documentação quando a equipe entrar em contato."
                    ),
                    "options": [
                        {"name": "Falar no WhatsApp", "link": f"https://wa.me/55{_digits(settings.company_phone)}"},
                        {"name": "Criar conta / acompanhar", "link": "/login"},
                        {"name": "Nova simulação", "next": 0},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    # --- QuitCon ---
    if step == STEP_QUITCON_BALANCE:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        lead.product_interest = "QUITCON"
        snap = _lead_snapshot(lead)
        snap["flow"] = "QUITCON"
        snap["product"] = "QUITCON"
        # Entrada pela categoria ou re-prompt — sem saldo ainda.
        raw = data.get("outstanding_balance")
        if raw in (None, ""):
            _save_lead_snapshot(lead, snap)
            db.flush()
            return _wrap(
                [
                    {
                        "text": "QuitCon — informe o saldo devedor bruto da cota (valor total que ainda falta pagar).",
                        "input": {"name": "outstanding_balance", "label": "Saldo devedor", "type": "text"},
                        "next": int(STEP_QUITCON_BALANCE),
                    }
                ],
                lead_id=lead.id,
            )
        try:
            saldo = _money_input(raw)
        except HTTPException:
            return _retry(
                "Informe o saldo devedor!",
                STEP_QUITCON_BALANCE,
                input_name="outstanding_balance",
                label="Saldo devedor",
                lead_id=lead.id,
            )
        if saldo <= 0:
            return _retry(
                "Informe o saldo devedor!",
                STEP_QUITCON_BALANCE,
                input_name="outstanding_balance",
                label="Saldo devedor",
                lead_id=lead.id,
            )
        snap["outstanding_balance"] = str(saldo)
        _save_lead_snapshot(lead, snap)
        db.flush()
        return _wrap(
            [
                {
                    "text": "Quantos meses faltam para encerrar o contrato?",
                    "input": {"name": "meses_restantes", "label": "Meses restantes", "type": "number"},
                    "next": int(STEP_QUITCON_MONTHS),
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_QUITCON_MONTHS:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        try:
            meses = int(str(data.get("meses_restantes") or data.get("option_id") or "0"))
        except ValueError:
            meses = 0
        if meses <= 0 or meses > 240:
            return _retry(
                "Informe os meses restantes (1 a 240)!",
                STEP_QUITCON_MONTHS,
                input_name="meses_restantes",
                label="Meses restantes",
                lead_id=lead.id,
            )
        snap = _lead_snapshot(lead)
        snap["meses_restantes"] = meses
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "Qual a administradora da cota? (whitelist QuitCon)",
                    "options": [
                        {
                            "name": label,
                            "next": int(STEP_QUITCON_REGISTRY),
                            "save": value,
                            "id": value.lower(),
                        }
                        for label, value in QUITCON_ADMIN_OPTIONS
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_QUITCON_ADMIN:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        # Compat: se caiu no step admin sem escolha, reexibe lista.
        return _wrap(
            [
                {
                    "text": "Qual a administradora da cota? (whitelist QuitCon)",
                    "options": [
                        {
                            "name": label,
                            "next": int(STEP_QUITCON_REGISTRY),
                            "save": value,
                            "id": value.lower(),
                        }
                        for label, value in QUITCON_ADMIN_OPTIONS
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_QUITCON_REGISTRY:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        admin = str(data.get("option_save") or data.get("registry_office") or "").strip()
        if admin and not data.get("registry_number"):
            snap["registry_office"] = admin
            _save_lead_snapshot(lead, snap)
            return _wrap(
                [
                    {
                        "text": "Informe grupo e cota (ex.: G-12/C-034).",
                        "input": {"name": "registry_number", "label": "Grupo / cota", "type": "text"},
                        "next": int(STEP_QUITCON_REGISTRY),
                    }
                ],
                lead_id=lead.id,
            )
        registry = str(data.get("registry_number") or data.get("option_id") or "").strip()
        if len(registry) < 2:
            return _retry(
                "Informe grupo e cota!",
                STEP_QUITCON_REGISTRY,
                input_name="registry_number",
                label="Grupo / cota",
                lead_id=lead.id,
            )
        if admin:
            snap["registry_office"] = admin
        snap["registry_number"] = registry
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "A cota já está contemplada?",
                    "options": [
                        {"name": "Sim", "next": int(STEP_QUITCON_BEM), "save": "1", "id": "contemplada_yes"},
                        {"name": "Não", "next": int(STEP_QUITCON_BEM), "save": "0", "id": "contemplada_no"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_QUITCON_CONTEMPLADA:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        snap["contemplada"] = data.get("option_save") == "1" or data.get("option_id") == "contemplada_yes"
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "O bem já foi faturado?",
                    "options": [
                        {"name": "Sim", "next": int(STEP_QUITCON_PARCELAS), "save": "1", "id": "bem_yes"},
                        {"name": "Não", "next": int(STEP_QUITCON_PARCELAS), "save": "0", "id": "bem_no"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_QUITCON_BEM:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        oid = str(data.get("option_id") or "")
        if oid in {"contemplada_yes", "contemplada_no"}:
            snap["contemplada"] = oid == "contemplada_yes"
            _save_lead_snapshot(lead, snap)
            return _wrap(
                [
                    {
                        "text": "O bem já foi faturado?",
                        "options": [
                            {"name": "Sim", "next": int(STEP_QUITCON_PARCELAS), "save": "1", "id": "bem_yes"},
                            {"name": "Não", "next": int(STEP_QUITCON_PARCELAS), "save": "0", "id": "bem_no"},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        snap["bem_faturado"] = oid == "bem_yes" or data.get("option_save") == "1"
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "As parcelas estão em dia?",
                    "options": [
                        {"name": "Sim", "next": int(STEP_QUITCON_DOCS), "save": "1", "id": "parcelas_yes"},
                        {"name": "Não", "next": int(STEP_QUITCON_DOCS), "save": "0", "id": "parcelas_no"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_QUITCON_PARCELAS:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        oid = str(data.get("option_id") or "")
        if oid in {"bem_yes", "bem_no"}:
            snap["bem_faturado"] = oid == "bem_yes"
            _save_lead_snapshot(lead, snap)
            return _wrap(
                [
                    {
                        "text": "As parcelas estão em dia?",
                        "options": [
                            {"name": "Sim", "next": int(STEP_QUITCON_DOCS), "save": "1", "id": "parcelas_yes"},
                            {"name": "Não", "next": int(STEP_QUITCON_DOCS), "save": "0", "id": "parcelas_no"},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        snap["parcelas_em_dia"] = oid == "parcelas_yes" or data.get("option_save") == "1"
        _save_lead_snapshot(lead, snap)
        return _wrap(
            [
                {
                    "text": "A documentação da cota está completa (extrato, contrato, docs pessoais)?",
                    "options": [
                        {"name": "Sim", "next": int(STEP_QUITCON_EVAL), "save": "1", "id": "docs_yes"},
                        {"name": "Não", "next": int(STEP_QUITCON_EVAL), "save": "0", "id": "docs_no"},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    if step == STEP_QUITCON_DOCS:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        oid = str(data.get("option_id") or "")
        if oid in {"parcelas_yes", "parcelas_no"}:
            snap["parcelas_em_dia"] = oid == "parcelas_yes"
            _save_lead_snapshot(lead, snap)
            return _wrap(
                [
                    {
                        "text": "A documentação da cota está completa (extrato, contrato, docs pessoais)?",
                        "options": [
                            {"name": "Sim", "next": int(STEP_QUITCON_EVAL), "save": "1", "id": "docs_yes"},
                            {"name": "Não", "next": int(STEP_QUITCON_EVAL), "save": "0", "id": "docs_no"},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        snap["docs_complete"] = oid == "docs_yes" or data.get("option_save") == "1"
        _save_lead_snapshot(lead, snap)
        data = {**data, "option_id": "docs_yes" if snap["docs_complete"] else "docs_no"}
        step = STEP_QUITCON_EVAL

    if step == STEP_QUITCON_EVAL:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        oid = str(data.get("option_id") or "")
        if oid in {"docs_yes", "docs_no"}:
            snap["docs_complete"] = oid == "docs_yes"
            _save_lead_snapshot(lead, snap)
        payload = {
            "outstanding_balance": snap.get("outstanding_balance") or "0",
            "meses_restantes": int(snap.get("meses_restantes") or 48),
            "registry_office": snap.get("registry_office") or "",
            "registry_number": snap.get("registry_number") or "",
            "contemplada": bool(snap.get("contemplada")),
            "bem_faturado": bool(snap.get("bem_faturado")),
            "parcelas_em_dia": bool(snap.get("parcelas_em_dia")),
            "docs_complete": bool(snap.get("docs_complete")),
            "operational_service": False,
        }
        result = evaluate_quitcon_desk(payload)
        snap["quitcon_evaluation"] = result
        _save_lead_snapshot(lead, snap)
        db.flush()
        custos = result.get("custos_entrada") if isinstance(result.get("custos_entrada"), dict) else {}
        quitcon_card = {
            "viavel": bool(result.get("viable")),
            "vp_fmt": _brl(result.get("valor_presente_quitacao") or 0),
            "saldo_fmt": _brl(snap.get("outstanding_balance") or 0),
            "meses_fmt": f"{int(snap.get('meses_restantes') or 0)} meses",
            "admin_fmt": str(snap.get("registry_office") or "—"),
            "entrada_fmt": _brl(custos.get("total_obrigatorio_abertura") or 0) if custos else "—",
            "motivos": list(result.get("motivos") or []),
        }
        item: dict[str, Any] = {
            "text": result.get("message") or ("Operação viável" if result.get("viable") else "Operação não viável"),
            "quitcon_result": quitcon_card,
        }
        if result.get("viable"):
            item["next"] = int(STEP_QUITCON_CONFIRM)
            item["button"] = "Continuar"
        else:
            item["options"] = [
                {"name": "Mudar categoria", "next": int(STEP_CATEGORY)},
                {"name": "Recomeçar", "next": 0},
            ]
        return _wrap([item], lead_id=lead.id)

    if step == STEP_QUITCON_CONFIRM:
        if not lead:
            raise HTTPException(422, "Sessão do chat expirada. Recomece pelo início.")
        snap = _lead_snapshot(lead)
        if snap.get("quitcon_solicitation_id"):
            return _wrap(
                [
                    {
                        "text": (
                            "Sua solicitação QuitCon já está na mesa. "
                            "Nossa equipe pede a documentação e segue a análise."
                        ),
                        "options": [
                            {"name": "Falar no WhatsApp", "link": f"https://wa.me/55{_digits(settings.company_phone)}"},
                            {"name": "Nova simulação", "next": 0},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        evaluation = snap.get("quitcon_evaluation") or {}
        if not evaluation.get("viable"):
            return _wrap(
                [
                    {
                        "text": "A operação QuitCon não está viável com os dados atuais. Ajuste a cota ou a categoria.",
                        "options": [
                            {"name": "Mudar categoria", "next": int(STEP_CATEGORY)},
                            {"name": "Recomeçar", "next": 0},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        store_payload = {
            "outstanding_balance": snap.get("outstanding_balance") or "0",
            "meses_restantes": int(snap.get("meses_restantes") or 48),
            "registry_office": snap.get("registry_office") or "",
            "registry_number": snap.get("registry_number") or "",
            "contemplada": bool(snap.get("contemplada")),
            "bem_faturado": bool(snap.get("bem_faturado")),
            "parcelas_em_dia": bool(snap.get("parcelas_em_dia")),
            "docs_complete": bool(snap.get("docs_complete")),
            "operational_service": False,
            "contact_name": lead.name or snap.get("name") or "Visitante",
            "contact_email": snap.get("email") or "site@letter.app.br",
            "contact_phone": lead.phone or snap.get("phone") or "",
            "person_type": "PF",
        }
        try:
            solicitation = store_quitcon_solicitation(db, actor, store_payload)
        except HTTPException as exc:
            detail = exc.detail
            message = detail.get("message") if isinstance(detail, dict) else str(detail)
            motivos = detail.get("motivos") if isinstance(detail, dict) else []
            return _wrap(
                [
                    {
                        "text": message or "Não foi possível registrar a solicitação QuitCon.",
                        "quitcon_result": {
                            "viavel": False,
                            "vp_fmt": "R$ 0,00",
                            "saldo_fmt": "R$ 0,00",
                            "meses_fmt": "—",
                            "admin_fmt": "—",
                            "entrada_fmt": "—",
                            "motivos": motivos or [message],
                        },
                        "options": [
                            {"name": "Mudar categoria", "next": int(STEP_CATEGORY)},
                            {"name": "Recomeçar", "next": 0},
                        ],
                    }
                ],
                lead_id=lead.id,
            )
        snap["quitcon_solicitation_id"] = solicitation.id
        lead.product_interest = "QUITCON"
        lead.status = "QUALIFIED"
        try:
            detail = json.loads(solicitation.evaluation_json or "{}")
            if isinstance(detail, dict):
                detail["channel"] = SOURCE
                detail["lead_id"] = lead.id
                solicitation.evaluation_json = json.dumps(detail, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        _save_lead_snapshot(lead, snap)
        db.flush()
        return _wrap(
            [
                {
                    "text": (
                        "Perfeito! Registrei sua solicitação QuitCon na mesa "
                        f"(VP {_brl(solicitation.quitacao_vp_amount)} — {solicitation.registry_office}). "
                        "Envie a documentação quando a equipe entrar em contato."
                    ),
                    "options": [
                        {"name": "Falar no WhatsApp", "link": f"https://wa.me/55{_digits(settings.company_phone)}"},
                        {"name": "Criar conta / acompanhar", "link": "/login"},
                        {"name": "Nova simulação", "next": 0},
                    ],
                }
            ],
            lead_id=lead.id,
        )

    # Fallback: unknown native step → home
    return home_native()
