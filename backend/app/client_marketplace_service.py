"""Escritório do cliente — compras Marketplace (boleto, docs, finalizar)."""

from __future__ import annotations

import json

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cadastro_service import (
    SIT_CONCLUIDO,
    SIT_PAGO,
    apply_situation_transition,
    get_cadastro_detail,
    list_cadastros,
    seed_marketplace_lifecycle,
)
from app.document_service import persist_upload
from app.inter_boleto_service import issue_marketplace_boleto
from app.models import Document, Lead, Proposal, Role, User
from app.network_visibility import get_lead_for_user

ENTITY_TYPE = "marketplace_lead"
DOC_KINDS = frozenset(
    {
        "IDENTITY",
        "ADDRESS",
        "INCOME",
        "CONTRACT",
        "PAYMENT_PROOF",
        "OTHER",
    }
)


def _chat_email(lead: Lead) -> str:
    try:
        detail = json.loads(lead.scr_detail_json or "{}")
        snap = detail.get("chat") if isinstance(detail, dict) else {}
        if isinstance(snap, dict):
            return str(snap.get("email") or "").strip().lower()
    except json.JSONDecodeError:
        pass
    return ""


def _bind_proposal(db: Session, lead: Lead, user: User) -> None:
    proposals = list(
        db.scalars(
            select(Proposal).where(
                Proposal.lead_id == lead.id,
                Proposal.organization_id == user.organization_id,
                Proposal.product == "MARKETPLACE",
            )
        )
    )
    for proposal in proposals:
        if not proposal.client_user_id:
            proposal.client_user_id = user.id
        terms = seed_marketplace_lifecycle(json.loads(proposal.terms_json or "{}"))
        terms["client_user_id"] = user.id
        proposal.terms_json = json.dumps(terms, ensure_ascii=False)


def bind_site_chat_lead(db: Session, user: User, chat_lead_id: str | None = None) -> dict:
    """Vincula lead SITE_CHAT ao usuário CLIENT (por id ou e-mail do snapshot)."""
    if user.role != Role.CLIENT:
        raise HTTPException(status_code=403, detail="Somente clientes vinculam compras do chat.")

    lead: Lead | None = None
    lead_id = (chat_lead_id or "").strip()
    if lead_id:
        lead = db.scalar(
            select(Lead).where(
                Lead.id == lead_id,
                Lead.organization_id == user.organization_id,
                Lead.source == "SITE_CHAT",
            )
        )
        if not lead:
            raise HTTPException(status_code=404, detail="Compra do chat não encontrada.")
    else:
        email = (user.email or "").strip().lower()
        if email:
            candidates = list(
                db.scalars(
                    select(Lead)
                    .where(
                        Lead.organization_id == user.organization_id,
                        Lead.source == "SITE_CHAT",
                        Lead.client_user_id.is_(None),
                    )
                    .order_by(Lead.created_at.desc())
                    .limit(40)
                )
            )
            for candidate in candidates:
                if _chat_email(candidate) == email:
                    lead = candidate
                    break

    if not lead:
        return {"bound": False, "lead_id": None, "message": "Nenhuma compra do chat para vincular."}

    if lead.client_user_id and lead.client_user_id != user.id:
        raise HTTPException(status_code=409, detail="Esta compra já está vinculada a outra conta.")

    lead.client_user_id = user.id
    if user.document and not lead.document:
        lead.document = user.document
    _bind_proposal(db, lead, user)
    db.flush()
    return {"bound": True, "lead_id": lead.id, "message": "Compra vinculada à sua conta."}


def list_my_compras(db: Session, user: User) -> list[dict]:
    if user.role != Role.CLIENT:
        raise HTTPException(status_code=403, detail="Somente clientes.")
    # tenta auto-vincular por e-mail antes de listar
    bind_site_chat_lead(db, user, None)
    return list_cadastros(db, user, pipeline="ALL")


def get_my_compra(db: Session, user: User, lead_id: str) -> dict:
    if user.role != Role.CLIENT:
        raise HTTPException(status_code=403, detail="Somente clientes.")
    get_lead_for_user(db, user, lead_id)
    return get_cadastro_detail(db, user, lead_id)


def refresh_my_zapsign(db: Session, user: User, lead_id: str) -> dict:
    if user.role != Role.CLIENT:
        raise HTTPException(status_code=403, detail="Somente clientes.")
    get_lead_for_user(db, user, lead_id)
    proposal = db.scalar(
        select(Proposal)
        .where(
            Proposal.lead_id == lead_id,
            Proposal.organization_id == user.organization_id,
            Proposal.product == "MARKETPLACE",
        )
        .order_by(Proposal.created_at.desc())
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposta Marketplace não encontrada.")

    from app.marketplace_zapsign_service import refresh_marketplace_zapsign, zapsign_view_from_terms

    current = zapsign_view_from_terms(json.loads(proposal.terms_json or "{}"))
    if current and current.get("status") == "SENT":
        return {"zapsign": refresh_marketplace_zapsign(db, proposal)}
    return {"zapsign": current}


def issue_my_boleto(db: Session, user: User, lead_id: str, *, force_new: bool = False) -> dict:
    if user.role != Role.CLIENT:
        raise HTTPException(status_code=403, detail="Somente clientes.")
    get_lead_for_user(db, user, lead_id)
    return issue_marketplace_boleto(db, user, lead_id, force_new=force_new)


def finalize_my_compra(db: Session, user: User, lead_id: str) -> dict:
    """Cliente marca venda como finalizada → CONCLUIDO (exige fornecedor confirmado)."""
    if user.role != Role.CLIENT:
        raise HTTPException(status_code=403, detail="Somente clientes.")
    lead = get_lead_for_user(db, user, lead_id)
    proposal = db.scalar(
        select(Proposal)
        .where(
            Proposal.lead_id == lead.id,
            Proposal.organization_id == user.organization_id,
            Proposal.product == "MARKETPLACE",
        )
        .order_by(Proposal.created_at.desc())
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposta Marketplace não encontrada.")

    terms = seed_marketplace_lifecycle(json.loads(proposal.terms_json or "{}"))
    life = terms.get("lifecycle") if isinstance(terms.get("lifecycle"), dict) else {}
    situation = str(life.get("situation") or "").upper()
    if situation not in {SIT_PAGO, SIT_CONCLUIDO}:
        raise HTTPException(
            status_code=409,
            detail="Só é possível finalizar após o pagamento da entrada (status Pagou).",
        )
    apply_situation_transition(db, user, lead, proposal, SIT_CONCLUIDO, force_admin_conclude=False)
    db.flush()
    return get_cadastro_detail(db, user, lead_id)


def list_my_documents(db: Session, user: User, lead_id: str) -> list[Document]:
    if user.role != Role.CLIENT:
        raise HTTPException(status_code=403, detail="Somente clientes.")
    get_lead_for_user(db, user, lead_id)
    return list(
        db.scalars(
            select(Document)
            .where(
                Document.organization_id == user.organization_id,
                Document.entity_type == ENTITY_TYPE,
                Document.entity_id == lead_id,
            )
            .order_by(Document.created_at.desc())
        )
    )


async def upload_my_document(
    db: Session,
    user: User,
    lead_id: str,
    *,
    kind: str,
    file: UploadFile,
) -> Document:
    if user.role != Role.CLIENT:
        raise HTTPException(status_code=403, detail="Somente clientes.")
    get_lead_for_user(db, user, lead_id)
    kind_norm = (kind or "OTHER").strip().upper()
    if kind_norm not in DOC_KINDS:
        raise HTTPException(status_code=422, detail=f"Tipo de documento inválido: {kind}")
    document = await persist_upload(file, user, ENTITY_TYPE, lead_id, kind_norm)
    db.add(document)
    db.flush()
    return document
