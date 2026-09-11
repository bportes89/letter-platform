"""Admin Cadastro — lista operacional de vendas Marketplace (Paulo / LETTER)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Contract, Lead, Proposal, Quota, Role, User
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

SIT_AGUARDANDO = "AGUARDANDO_PAGAMENTO"
SIT_PAGO = "PAGO"
SIT_CONCLUIDO = "CONCLUIDO"
SIT_CANCELADO = "CANCELADO"
SIT_CANCELADO_FALTA = "CANCELADO_FALTA_PAGAMENTO"
SIT_INCOMPLETO = "INCOMPLETO"

SALE_SITUATIONS = frozenset({SIT_AGUARDANDO, SIT_PAGO, SIT_CONCLUIDO, SIT_CANCELADO, SIT_CANCELADO_FALTA})

SITUATION_LABELS = {
    SIT_INCOMPLETO: "Incompleto",
    SIT_AGUARDANDO: "Aguardando pagamento",
    SIT_PAGO: "Pagou",
    "EM_NEGOCIACAO": "Em negociação",
    SIT_CONCLUIDO: "Concluído",
    "CONCLUIDA": "Concluída",
    SIT_CANCELADO: "Cancelado",
    SIT_CANCELADO_FALTA: "Cancelado (falta de pagamento)",
    "CANCELADA": "Cancelada",
}

COMM_NOT_DUE = "NOT_DUE"
COMM_PENDING = "PENDING"
COMM_RELEASED = "RELEASED"
COMM_RELEASED_STUB = "RELEASED_STUB"  # legado pré-liberação real
COMM_SKIPPED = "SKIPPED"
COMM_RELEASED_ANY = frozenset({COMM_RELEASED, COMM_RELEASED_STUB})


def _parse_json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def seed_marketplace_lifecycle(terms: dict | None = None) -> dict:
    """Garante bloco lifecycle em terms_json de proposta Marketplace."""
    data = dict(terms or {})
    life = data.get("lifecycle")
    if not isinstance(life, dict):
        life = {}
    if not life.get("situation"):
        life["situation"] = SIT_AGUARDANDO
    life.setdefault("supplier_transfer_confirmed", False)
    life.setdefault("commission_release_status", COMM_NOT_DUE)
    life.setdefault("paid_at", None)
    life.setdefault("supplier_transfer_confirmed_at", None)
    life.setdefault("commission_released_at", None)
    life.setdefault("force_admin_conclude", False)
    data["lifecycle"] = life
    return data


def _lifecycle(terms: dict) -> dict:
    life = terms.get("lifecycle")
    return life if isinstance(life, dict) else {}


def _write_lifecycle(proposal: Proposal, **fields) -> dict:
    terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json))
    life = terms["lifecycle"]
    for key, value in fields.items():
        life[key] = value
    terms["lifecycle"] = life
    proposal.terms_json = json.dumps(terms, ensure_ascii=False)
    return life


def _snapshot_from_lead(lead: Lead) -> dict:
    detail = _parse_json(lead.scr_detail_json)
    for key in ("venda_direta_manual", "venda_direta_robo", "chat", "cadastro"):
        snap = detail.get(key)
        if isinstance(snap, dict) and snap:
            return snap
    return {}


def _pipeline_for_situation(situation: str) -> str:
    if situation == SIT_AGUARDANDO:
        return PIPELINE_NOVOS
    if situation == SIT_PAGO:
        return PIPELINE_NEGOCIACAO
    if situation in {SIT_CONCLUIDO, "CONCLUIDA"}:
        return PIPELINE_CONCLUIDO
    if situation in {SIT_CANCELADO, SIT_CANCELADO_FALTA, "CANCELADA"}:
        return PIPELINE_ALL  # só aparece em ALL
    return PIPELINE_INCOMPLETO


def _classify(lead: Lead, proposal: Proposal | None, contract: Contract | None, quotas: list[Quota], terms: dict | None = None) -> tuple[str, str]:
    """Retorna (pipeline_bucket, situation_code). Prefere lifecycle explícito."""
    terms = terms or (_parse_json(proposal.terms_json) if proposal else {})
    life = _lifecycle(terms)
    stored = str(life.get("situation") or "").strip().upper()
    if stored in SALE_SITUATIONS or stored in {"CONCLUIDA", "CANCELADA", "EM_NEGOCIACAO"}:
        if stored == "CONCLUIDA":
            stored = SIT_CONCLUIDO
        if stored == "CANCELADA":
            stored = SIT_CANCELADO
        if stored == "EM_NEGOCIACAO":
            stored = SIT_PAGO
        bucket = _pipeline_for_situation(stored)
        return bucket, stored

    if any(q.status == "SOLD" for q in quotas) or (contract and contract.status in {"ACCEPTED", "SIGNED", "ACTIVE", "COMPLETED"}):
        return PIPELINE_CONCLUIDO, SIT_CONCLUIDO
    if proposal and (contract or any(q.status == "RESERVED" for q in quotas) or proposal.status in {"APPROVED", "UNDER_REVIEW"}):
        return PIPELINE_NEGOCIACAO, SIT_PAGO
    if proposal and proposal.product == "MARKETPLACE":
        return PIPELINE_NOVOS, SIT_AGUARDANDO
    if lead.product_interest == "MARKETPLACE" or lead.source in MARKETPLACE_SOURCES:
        return PIPELINE_INCOMPLETO, SIT_INCOMPLETO
    return PIPELINE_INCOMPLETO, SIT_INCOMPLETO


def _is_marketplace_row(lead: Lead, proposal: Proposal | None) -> bool:
    if lead.product_interest == "MARKETPLACE":
        return True
    if lead.source in MARKETPLACE_SOURCES:
        return True
    if proposal and proposal.product == "MARKETPLACE":
        return True
    return False


def _on_first_pago(db: Session, proposal: Proposal, terms: dict, life: dict) -> None:
    if life.get("paid_at"):
        return
    now = datetime.now(UTC).isoformat()
    _write_lifecycle(
        proposal,
        situation=SIT_PAGO,
        paid_at=now,
        commission_release_status=COMM_PENDING,
    )
    quota_ids = [str(x) for x in (terms.get("quota_ids") or [])]
    if not quota_ids:
        for row in terms.get("quotas") or []:
            if isinstance(row, dict) and row.get("quota_id"):
                quota_ids.append(str(row["quota_id"]))
    if quota_ids:
        quotas = list(db.scalars(select(Quota).where(Quota.id.in_(quota_ids))))
        for quota in quotas:
            if quota.status in {"AVAILABLE", "RESERVED"}:
                quota.status = "SOLD"


def _on_concluir(db: Session, user: User, proposal: Proposal, life: dict, *, force_admin: bool) -> None:
    confirmed = bool(life.get("supplier_transfer_confirmed"))
    if not confirmed and not force_admin:
        raise HTTPException(
            status_code=409,
            detail=(
                "Não é possível concluir a venda: o fornecedor ainda não confirmou a transferência da cota. "
                "Marque a confirmação ou use forçar conclusão (admin)."
            ),
        )
    now = datetime.now(UTC).isoformat()
    fields = {
        "situation": SIT_CONCLUIDO,
        "concluded_by": user.id,
    }
    if force_admin and not confirmed:
        fields["supplier_transfer_confirmed"] = True
        fields["supplier_transfer_confirmed_at"] = now
        fields["force_admin_conclude"] = True
    _write_lifecycle(proposal, **fields)
    from app.marketplace_commission_release_service import release_marketplace_commissions

    release_marketplace_commissions(db, user, proposal)


def apply_situation_transition(
    db: Session,
    user: User,
    lead: Lead,
    proposal: Proposal,
    new_situation: str,
    *,
    force_admin_conclude: bool = False,
) -> None:
    situation = str(new_situation or "").strip().upper()
    if situation not in SALE_SITUATIONS:
        raise HTTPException(status_code=422, detail=f"Situação inválida: {new_situation}")

    terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json))
    proposal.terms_json = json.dumps(terms, ensure_ascii=False)
    life = terms["lifecycle"]
    current = str(life.get("situation") or SIT_AGUARDANDO).upper()
    if current == situation:
        return  # idempotente

    if situation == SIT_PAGO:
        already_paid = bool(life.get("paid_at"))
        _on_first_pago(db, proposal, terms, life)
        if not already_paid:
            from app.marketplace_notification_service import dispatch_payment_received_notifications

            dispatch_payment_received_notifications(db, user, lead, proposal)
        lead.status = "PROPOSAL"
        return

    if situation == SIT_CONCLUIDO:
        # refresh life after possible prior writes
        life = _lifecycle(_parse_json(proposal.terms_json))
        if str(life.get("situation") or "") == SIT_AGUARDANDO:
            _on_first_pago(db, proposal, _parse_json(proposal.terms_json), life)
            life = _lifecycle(_parse_json(proposal.terms_json))
        _on_concluir(db, user, proposal, life, force_admin=force_admin_conclude)
        lead.status = "CONVERTED"
        return

    if situation in {SIT_CANCELADO, SIT_CANCELADO_FALTA}:
        status = life.get("commission_release_status") or COMM_NOT_DUE
        if status not in COMM_RELEASED_ANY:
            status = COMM_SKIPPED
        _write_lifecycle(proposal, situation=situation, commission_release_status=status)
        lead.status = "CANCELLED"
        return

    if situation == SIT_AGUARDANDO:
        _write_lifecycle(proposal, situation=SIT_AGUARDANDO)
        return


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
        terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json))
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
        bucket, situation = _classify(lead, proposal, contract, linked_quotas, terms)
        life = _lifecycle(terms)

        if situation in {SIT_CANCELADO, SIT_CANCELADO_FALTA} and pipeline not in {PIPELINE_ALL}:
            continue
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
                "pipeline": (
                    "CANCELADO"
                    if situation in {SIT_CANCELADO, SIT_CANCELADO_FALTA}
                    else bucket
                    if bucket != PIPELINE_ALL
                    else PIPELINE_INCOMPLETO
                ),
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
                "supplier_transfer_confirmed": bool(life.get("supplier_transfer_confirmed")),
                "commission_release_status": life.get("commission_release_status"),
                "paid_at": life.get("paid_at"),
                "lifecycle_editable": bool(proposal),
            }
        )
    return rows


def get_cadastro_detail(db: Session, user: User, lead_id: str) -> dict:
    lead = get_lead_for_user(db, user, lead_id)
    rows = list_cadastros(db, user, pipeline=PIPELINE_ALL)
    row = next((r for r in rows if r["lead_id"] == lead_id), None)
    if not row:
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
            "situation": SIT_INCOMPLETO,
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
            "supplier_transfer_confirmed": False,
            "commission_release_status": None,
            "paid_at": None,
            "lifecycle_editable": False,
        }
    snap = _snapshot_from_lead(lead)
    proposal = None
    if row.get("proposal_id"):
        proposal = db.get(Proposal, row["proposal_id"])
    terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json)) if proposal else {}
    life = _lifecycle(terms)
    boleto = None
    if proposal:
        from app.inter_boleto_service import boleto_view_from_terms

        boleto = boleto_view_from_terms(terms, lead_id=lead.id)
    from app.marketplace_contract_docs_service import site_contract_meta

    contract_meta = site_contract_meta(terms, snap)
    from app.marketplace_zapsign_service import zapsign_view_from_terms

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
        "supplier_transfer_confirmed": bool(life.get("supplier_transfer_confirmed")),
        "commission_release_status": life.get("commission_release_status"),
        "paid_at": life.get("paid_at"),
        "lifecycle_editable": bool(proposal),
        "can_conclude": bool(proposal) and bool(life.get("supplier_transfer_confirmed")),
        "commission_release": life.get("commission_release") if isinstance(life.get("commission_release"), dict) else None,
        "boleto": boleto,
        "has_site_contract": contract_meta["has_site_contract"],
        "contract_ack": contract_meta["contract_ack"],
        "zapsign": zapsign_view_from_terms(terms),
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
    situation: str | None = None,
    force_admin_conclude: bool = False,
    supplier_transfer_confirmed: bool | None = None,
) -> dict:
    lead = get_lead_for_user(db, user, lead_id)
    if user.role == Role.CLIENT:
        # Cliente só finaliza (CONCLUIDO) pela rota dedicada /marketplace/me; PATCH admin fica bloqueado.
        raise HTTPException(
            status_code=403,
            detail="Use o escritório Minhas compras (finalizar / boleto / documentos) para esta conta.",
        )
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

    proposal = db.scalar(
        select(Proposal)
        .where(
            Proposal.lead_id == lead.id,
            Proposal.organization_id == user.organization_id,
            Proposal.product == "MARKETPLACE",
        )
        .order_by(Proposal.created_at.desc())
    )
    if proposal:
        terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json))
        proposal.terms_json = json.dumps(terms, ensure_ascii=False)
        if supplier_transfer_confirmed is not None:
            now = datetime.now(UTC).isoformat() if supplier_transfer_confirmed else None
            _write_lifecycle(
                proposal,
                supplier_transfer_confirmed=bool(supplier_transfer_confirmed),
                supplier_transfer_confirmed_at=now if supplier_transfer_confirmed else None,
            )
        if situation is not None:
            apply_situation_transition(
                db,
                user,
                lead,
                proposal,
                situation,
                force_admin_conclude=bool(force_admin_conclude),
            )

    db.flush()
    return get_cadastro_detail(db, user, lead.id)
