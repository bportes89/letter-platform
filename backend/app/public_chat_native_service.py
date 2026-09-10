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
from app.cadastro_service import seed_marketplace_lifecycle
from app.marketplace_service import esteira2_nina_curated_match
from app.models import Lead, Organization, Proposal, Quota, Role, User
from app.public_site_service import headquarters_org
from app.quota_inventory_service import run_nina_quota_scan
from app.sdc_desk_service import evaluate_sdc_desk, store_solicitation
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
STEP_DONE = "10014"

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


def _find_lead(db: Session, org: Organization, payload: dict) -> Lead | None:
    lead_id = str(payload.get("lead_id") or "").strip()
    if lead_id:
        lead = db.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.organization_id == org.id, Lead.source == SOURCE)
        )
        if lead:
            return lead
    email = str(payload.get("email") or "").strip().lower()
    if email and "@" in email:
        leads = list(
            db.scalars(
                select(Lead)
                .where(Lead.organization_id == org.id, Lead.source == SOURCE)
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
) -> dict:
    item: dict[str, Any] = {"text": message, "next": int(step)}
    if input_name:
        item["input"] = {"name": input_name, "label": label or input_name, "type": "text"}
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
        total_entrada = money(
            sum((pricing_for_quota(q, suppliers=suppliers)["entrada_final"] for q in quotas), Decimal("0"))
        )
        if not existing:
            snap = _lead_snapshot(lead)
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
                            "filters": snap,
                        }
                    ),
                    ensure_ascii=False,
                ),
                sale_channel="SELF_SERVICE",
                created_by_user_id=actor.id,
            )
            db.add(proposal)
            db.flush()
            for quota in quotas:
                if quota.status == "AVAILABLE":
                    reserve_quota(db, actor, quota, proposal.id, RESERVE_TTL)
            lead.status = "PROPOSAL"
            snap["chosen_quota_ids"] = quota_ids
            snap["proposal_id"] = proposal.id
            _save_lead_snapshot(lead, snap)
            db.flush()
            proposal_id = proposal.id
        else:
            proposal_id = existing.id
        return _wrap(
            [
                {
                    "text": (
                        f"Perfeito! Reservei a(s) cota(s) por {RESERVE_TTL} minutos. "
                        "Nossa equipe entra em contato para finalizar documentos e pagamento da entrada."
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
            solicitation = store_solicitation(db, actor, store_payload)
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

    # Fallback: unknown native step → home
    return home_native()
