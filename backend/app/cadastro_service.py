"""Admin Cadastro — lista operacional de vendas Marketplace (Paulo / LETTER)."""

from __future__ import annotations

import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Contract, Lead, Proposal, Quota, User
from app.network_visibility import get_lead_for_user, list_visible_leads, owner_map
from app.services import money

PIPELINE_ALL = "ALL"
PIPELINE_NOVOS = "NOVOS"
PIPELINE_NEGOCIACAO = "NEGOCIACAO"
PIPELINE_CONCLUIDO = "CONCLUIDO"
PIPELINE_INCOMPLETO = "INCOMPLETO"
PIPELINE_COMPRAS = "COMPRAS"

MARKETPLACE_SOURCES = frozenset(
    {
        "VENDA_DIRETA_ROBO",
        "VENDA_DIRETA_MANUAL",
        "DIRECT",
        "DASHBOARD",
        "PUBLIC_SITE",
        "CHAT",
        "SITE_CHAT",
    }
)

SITUATION_LABELS = {
    "INCOMPLETO": "Incompleto",
    "AGUARDANDO_PAGAMENTO": "Aguardando pagamento",
    "EM_NEGOCIACAO": "Em negociação",
    "CONCLUIDA": "Concluída",
    "CANCELADA": "Cancelada",
}


def _parse_json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _snapshot_from_lead(lead: Lead) -> dict:
    detail = _parse_json(lead.scr_detail_json)
    for key in ("venda_direta_manual", "venda_direta_robo", "chat", "cadastro"):
        snap = detail.get(key)
        if isinstance(snap, dict) and snap:
            return snap
    return {}


def _classify(lead: Lead, proposal: Proposal | None, contract: Contract | None, quotas: list[Quota]) -> tuple[str, str]:
    """Retorna (pipeline_bucket, situation_code)."""
    if any(q.status == "SOLD" for q in quotas) or (contract and contract.status in {"ACCEPTED", "SIGNED", "ACTIVE", "COMPLETED"}):
        return PIPELINE_CONCLUIDO, "CONCLUIDA"
    if proposal and (contract or any(q.status == "RESERVED" for q in quotas) or proposal.status in {"APPROVED", "UNDER_REVIEW"}):
        return PIPELINE_NEGOCIACAO, "EM_NEGOCIACAO"
    if proposal and proposal.product == "MARKETPLACE":
        return PIPELINE_NOVOS, "AGUARDANDO_PAGAMENTO"
    if lead.status in {"NEW", "CONTACTED"} or not proposal:
        if lead.product_interest == "MARKETPLACE" or lead.source in MARKETPLACE_SOURCES:
            return PIPELINE_INCOMPLETO, "INCOMPLETO"
    if lead.product_interest == "MARKETPLACE" or lead.source in MARKETPLACE_SOURCES:
        return PIPELINE_INCOMPLETO, "INCOMPLETO"
    return PIPELINE_INCOMPLETO, "INCOMPLETO"


def _is_marketplace_row(lead: Lead, proposal: Proposal | None) -> bool:
    if lead.product_interest == "MARKETPLACE":
        return True
    if lead.source in MARKETPLACE_SOURCES:
        return True
    if proposal and proposal.product == "MARKETPLACE":
        return True
    return False


def list_cadastros(db: Session, user: User, *, pipeline: str = PIPELINE_ALL, q: str | None = None) -> list[dict]:
    pipeline = (pipeline or PIPELINE_ALL).upper()
    leads = list_visible_leads(db, user)
    if not leads:
        return []

    lead_ids = [lead.id for lead in leads]
    proposals = list(
        db.scalars(
            select(Proposal)
            .where(
                Proposal.organization_id == user.organization_id,
                Proposal.lead_id.in_(lead_ids),
                Proposal.product == "MARKETPLACE",
            )
            .order_by(Proposal.created_at.desc())
        )
    )
    proposal_by_lead: dict[str, Proposal] = {}
    for proposal in proposals:
        if proposal.lead_id not in proposal_by_lead:
            proposal_by_lead[proposal.lead_id] = proposal

    proposal_ids = [p.id for p in proposal_by_lead.values()]
    contracts = list(
        db.scalars(select(Contract).where(Contract.proposal_id.in_(proposal_ids))) if proposal_ids else []
    )
    contract_by_proposal = {c.proposal_id: c for c in contracts}

    all_quota_ids: set[str] = set()
    terms_by_proposal: dict[str, dict] = {}
    for proposal in proposal_by_lead.values():
        terms = _parse_json(proposal.terms_json)
        terms_by_proposal[proposal.id] = terms
        for qid in terms.get("quota_ids") or []:
            all_quota_ids.add(str(qid))
        for row in terms.get("quotas") or []:
            if isinstance(row, dict) and row.get("quota_id"):
                all_quota_ids.add(str(row["quota_id"]))

    quotas = list(db.scalars(select(Quota).where(Quota.id.in_(all_quota_ids)))) if all_quota_ids else []
    quota_by_id = {q.id: q for q in quotas}

    owners = owner_map(db, {lead.owner_id for lead in leads if lead.owner_id})
    needle = (q or "").strip().lower()
    rows: list[dict] = []

    for lead in leads:
        proposal = proposal_by_lead.get(lead.id)
        if not _is_marketplace_row(lead, proposal):
            continue
        terms = terms_by_proposal.get(proposal.id, {}) if proposal else {}
        snap = _snapshot_from_lead(lead)
        quota_ids = [str(x) for x in (terms.get("quota_ids") or [])]
        linked_quotas = [quota_by_id[qid] for qid in quota_ids if qid in quota_by_id]
        contract = contract_by_proposal.get(proposal.id) if proposal else None
        bucket, situation = _classify(lead, proposal, contract, linked_quotas)

        if pipeline == PIPELINE_COMPRAS:
            if bucket != PIPELINE_CONCLUIDO:
                continue
        elif pipeline != PIPELINE_ALL and bucket != pipeline:
            continue

        email = snap.get("email") or terms.get("client_email")
        credit = terms.get("total_credit") or (str(proposal.requested_amount) if proposal else None)
        entrada = terms.get("total_entrada") or terms.get("total_entrada_base")
        if not entrada and snap.get("pricing"):
            entrada = (snap.get("pricing") or {}).get("entrada_final")
        suppliers = sorted(
            {
                str(q.supplier_source)
                for q in linked_quotas
                if q.supplier_source
            }
            | {
                str(row.get("supplier_source"))
                for row in (terms.get("quotas") or [])
                if isinstance(row, dict) and row.get("supplier_source")
            }
        )
        owner = owners.get(lead.owner_id) if lead.owner_id else None
        label_bits = f"{lead.name} {lead.document or ''} {lead.phone} {email or ''}".lower()
        if needle and needle not in label_bits:
            continue

        rows.append(
            {
                "lead_id": lead.id,
                "created_at": lead.created_at,
                "name": lead.name,
                "document": lead.document,
                "phone": lead.phone,
                "email": email,
                "source": lead.source,
                "lead_status": lead.status,
                "pipeline": bucket,
                "situation": situation,
                "situation_label": SITUATION_LABELS.get(situation, situation),
                "credit_value": str(money(Decimal(str(credit)))) if credit not in (None, "") else None,
                "entrada_value": str(money(Decimal(str(entrada)))) if entrada not in (None, "") else None,
                "partner_name": owner.name if owner else None,
                "partner_role": owner.role if owner else None,
                "proposal_id": proposal.id if proposal else None,
                "proposal_status": proposal.status if proposal else None,
                "contract_id": contract.id if contract else None,
                "contract_status": contract.status if contract else None,
                "quota_ids": quota_ids,
                "quota_codes": [f"{q.group_code}/{q.quota_code}" for q in linked_quotas],
                "supplier_sources": suppliers,
                "person_type": snap.get("person_type") or terms.get("person_type"),
            }
        )
    return rows


def get_cadastro_detail(db: Session, user: User, lead_id: str) -> dict:
    lead = get_lead_for_user(db, user, lead_id)
    rows = list_cadastros(db, user, pipeline=PIPELINE_ALL)
    row = next((r for r in rows if r["lead_id"] == lead_id), None)
    if not row:
        # lead existe mas não é marketplace — ainda assim devolve base
        owners = owner_map(db, {lead.owner_id} if lead.owner_id else set())
        owner = owners.get(lead.owner_id) if lead.owner_id else None
        row = {
            "lead_id": lead.id,
            "created_at": lead.created_at,
            "name": lead.name,
            "document": lead.document,
            "phone": lead.phone,
            "email": None,
            "source": lead.source,
            "lead_status": lead.status,
            "pipeline": PIPELINE_INCOMPLETO,
            "situation": "INCOMPLETO",
            "situation_label": "Incompleto",
            "credit_value": None,
            "entrada_value": None,
            "partner_name": owner.name if owner else None,
            "partner_role": owner.role if owner else None,
            "proposal_id": None,
            "proposal_status": None,
            "contract_id": None,
            "contract_status": None,
            "quota_ids": [],
            "quota_codes": [],
            "supplier_sources": [],
            "person_type": None,
        }
    snap = _snapshot_from_lead(lead)
    proposal = None
    if row.get("proposal_id"):
        proposal = db.get(Proposal, row["proposal_id"])
    terms = _parse_json(proposal.terms_json) if proposal else {}
    return {
        **row,
        "snapshot": snap,
        "terms": terms,
        "address": snap.get("address") or {},
        "purchase_readonly": {
            "credit_value": row.get("credit_value"),
            "entrada_value": row.get("entrada_value"),
            "quota_codes": row.get("quota_codes"),
            "supplier_sources": row.get("supplier_sources"),
            "channel": terms.get("channel") or lead.source,
        },
    }


def update_cadastro(
    db: Session,
    user: User,
    lead_id: str,
    *,
    name: str | None = None,
    phone: str | None = None,
    document: str | None = None,
    email: str | None = None,
    lead_status: str | None = None,
    zipcode: str | None = None,
    street: str | None = None,
    number: str | None = None,
    neighborhood: str | None = None,
    city: str | None = None,
    uf: str | None = None,
) -> dict:
    lead = get_lead_for_user(db, user, lead_id)
    if name is not None:
        lead.name = name.strip()
    if phone is not None:
        lead.phone = phone.strip()
    if document is not None:
        lead.document = "".join(ch for ch in document if ch.isdigit()) or lead.document
    if lead_status is not None:
        allowed = {"NEW", "CONTACTED", "QUALIFIED", "PROPOSAL", "CONVERTED", "CANCELLED"}
        if lead_status not in allowed:
            raise HTTPException(status_code=422, detail=f"Status inválido: {lead_status}")
        lead.status = lead_status

    detail = _parse_json(lead.scr_detail_json)
    key = next(
        (k for k in ("venda_direta_manual", "venda_direta_robo", "chat", "cadastro") if isinstance(detail.get(k), dict)),
        "cadastro",
    )
    snap = detail.get(key) if isinstance(detail.get(key), dict) else {}
    if email is not None:
        snap["email"] = email.strip()
    address = snap.get("address") if isinstance(snap.get("address"), dict) else {}
    for field, value in (
        ("zipcode", zipcode),
        ("street", street),
        ("number", number),
        ("neighborhood", neighborhood),
        ("city", city),
        ("uf", uf),
    ):
        if value is not None:
            address[field] = value.strip().upper() if field == "uf" else value.strip()
    snap["address"] = address
    detail[key] = snap
    lead.scr_detail_json = json.dumps(detail, ensure_ascii=False)
    db.flush()
    return get_cadastro_detail(db, user, lead.id)
