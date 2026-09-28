"""Contrato do chat Marketplace (PDF) + download de documentos do lead."""

from __future__ import annotations

import io
import json
import re
from html import unescape

from fastapi import HTTPException
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, Lead, Proposal, Role, User
from app.marketplace_contract_template_service import (
    LOCKED_FIELD_LABELS,
    assert_locked_fields_unchanged,
    extract_locked_fields,
    load_organization_template,
    render_marketplace_contract_html,
    save_organization_template,
)
from app.cadastro_service import seed_marketplace_lifecycle
from app.network_visibility import get_lead_for_user
from app.storage_service import get_storage

ENTITY_TYPE = "marketplace_lead"


def _parse_json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _proposal_for_lead(db: Session, user: User, lead: Lead) -> Proposal | None:
    return db.scalar(
        select(Proposal)
        .where(
            Proposal.lead_id == lead.id,
            Proposal.organization_id == user.organization_id,
            Proposal.product == "MARKETPLACE",
        )
        .order_by(Proposal.created_at.desc())
    )


def site_contract_meta(terms: dict, snap: dict | None = None) -> dict:
    """Metadados do contrato aceito no chat (sem criar Contract ZapSign)."""
    ack = terms.get("contract_ack") if isinstance(terms.get("contract_ack"), dict) else {}
    html = str(terms.get("contract_html") or "").strip()
    if not html and isinstance(snap, dict):
        html = str(snap.get("contract_html") or "").strip()
        if not ack.get("accepted_at") and snap.get("contract_accepted_at"):
            ack = {
                "accepted_at": snap.get("contract_accepted_at"),
                "channel": "SITE_CHAT",
                "provider": "SITE_CHAT_ACK",
            }
    return {
        "has_site_contract": bool(html and ack.get("accepted_at")),
        "contract_ack": ack or None,
        "accepted_at": ack.get("accepted_at") if ack else None,
        "provider": ack.get("provider") if ack else None,
    }


INTERNAL_CONTRACT_EDIT_ROLES = frozenset({
    Role.PLATFORM_ADMIN,
    Role.INTERNAL_STAFF,
    Role.MASTER_FRANCHISEE,
    Role.MANAGER,
})


def _load_lead_contract_html(db: Session, user: User, lead_id: str) -> tuple[Lead, str, dict, Proposal | None]:
    lead = get_lead_for_user(db, user, lead_id)
    proposal = _proposal_for_lead(db, user, lead)
    terms = _parse_json(proposal.terms_json) if proposal else {}
    snap = {}
    detail = _parse_json(lead.scr_detail_json)
    from app.cadastro_service import marketplace_snapshot_key

    snap_key = marketplace_snapshot_key(detail)
    if isinstance(detail.get(snap_key), dict):
        snap = detail[snap_key]
    elif isinstance(detail.get("chat"), dict):
        snap = detail["chat"]
    html = str(terms.get("contract_html") or "").strip()
    if not html:
        html = str(snap.get("contract_html") or "").strip()
    ack = terms.get("contract_ack") if isinstance(terms.get("contract_ack"), dict) else {}
    if not ack and snap.get("contract_accepted_at"):
        ack = {
            "accepted_at": snap.get("contract_accepted_at"),
            "channel": "SITE_CHAT",
            "provider": "SITE_CHAT_ACK",
        }
    return lead, html, ack, proposal


def contract_document_view(db: Session, user: User, lead_id: str) -> dict:
    lead, html, ack, _proposal = _load_lead_contract_html(db, user, lead_id)
    if not html:
        raise HTTPException(status_code=404, detail="Contrato ainda não foi gerado para este cadastro.")
    locked = [
        {"field": k, "label": LOCKED_FIELD_LABELS.get(k, k), "value": v}
        for k, v in extract_locked_fields(html).items()
    ]
    return {
        "html": html,
        "can_edit": user.role in INTERNAL_CONTRACT_EDIT_ROLES,
        "has_site_contract": bool(html and ack.get("accepted_at")),
        "contract_ack": ack or None,
        "locked_fields": locked,
    }


def save_lead_contract_html(db: Session, user: User, lead_id: str, html: str) -> dict:
    if user.role not in INTERNAL_CONTRACT_EDIT_ROLES:
        raise HTTPException(status_code=403, detail="Somente operação LETTER pode editar o contrato.")
    lead, previous, ack, proposal = _load_lead_contract_html(db, user, lead_id)
    if not previous:
        raise HTTPException(status_code=404, detail="Contrato ainda não foi gerado.")
    cleaned = (html or "").strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Contrato vazio.")
    try:
        assert_locked_fields_unchanged(previous, cleaned)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    detail = _parse_json(lead.scr_detail_json)
    from app.cadastro_service import marketplace_snapshot_key

    snap_key = marketplace_snapshot_key(detail)
    snap = detail.get(snap_key) if isinstance(detail.get(snap_key), dict) else {}
    if not isinstance(snap, dict):
        snap = {}
    snap["contract_html"] = cleaned
    detail[snap_key] = snap
    lead.scr_detail_json = json.dumps(detail, ensure_ascii=False)

    if proposal:
        terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json))
        terms["contract_html"] = cleaned
        proposal.terms_json = json.dumps(terms, ensure_ascii=False)
    db.flush()
    return contract_document_view(db, user, lead_id)


def regenerate_lead_contract_html(db: Session, user: User, lead_id: str) -> dict:
    if user.role not in INTERNAL_CONTRACT_EDIT_ROLES:
        raise HTTPException(status_code=403, detail="Somente operação LETTER pode regerar o contrato.")
    lead, _prev, _ack, proposal = _load_lead_contract_html(db, user, lead_id)
    detail = _parse_json(lead.scr_detail_json)
    from app.cadastro_service import marketplace_snapshot_key

    snap_key = marketplace_snapshot_key(detail)
    snap = detail.get(snap_key) if isinstance(detail.get(snap_key), dict) else {}
    if not isinstance(snap, dict) or not snap:
        raise HTTPException(status_code=422, detail="Snapshot da compra indisponível para regerar contrato.")
    html = render_marketplace_contract_html(db, user.organization_id, lead, snap)
    return save_lead_contract_html(db, user, lead_id, html)


def resolve_contract_html(db: Session, user: User, lead_id: str) -> tuple[str, dict]:
    lead, html, ack, _proposal = _load_lead_contract_html(db, user, lead_id)
    if not html:
        raise HTTPException(status_code=404, detail="Contrato do chat ainda não aceito nesta compra.")
    if not ack.get("accepted_at"):
        raise HTTPException(status_code=409, detail="Contrato ainda não foi aceito no chat.")
    return html, ack


def _html_to_paragraphs(html: str, body_style, meta_style) -> list:
    text = unescape(html or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?i)<br\s*/?>", "<br/>", text)
    chunks = re.split(r"(?i)</p\s*>", text)
    flowables: list = []
    for chunk in chunks:
        chunk = re.sub(r"(?i)<p[^>]*>", "", chunk).strip()
        if not chunk:
            continue
        chunk = chunk.replace("<strong>", "<b>").replace("</strong>", "</b>")
        chunk = chunk.replace("<STRONG>", "<b>").replace("</STRONG>", "</b>")
        # drop unsupported tags except b/i/br/font
        chunk = re.sub(r"(?i)</?(?!b\b|i\b|br\b|font\b)[a-z0-9]+[^>]*>", "", chunk)
        chunk = re.sub(r"\n{2,}", "<br/><br/>", chunk)
        flowables.append(Paragraph(chunk, body_style))
        flowables.append(Spacer(1, 4 * mm))
    if not flowables:
        flowables.append(Paragraph("(sem conteúdo)", body_style))
    return flowables


def build_site_contract_pdf(*, html: str, ack: dict, lead_name: str | None = None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        name="MktContractTitle",
        parent=styles["Title"],
        textColor=HexColor("#0B5D3B"),
        fontSize=16,
        spaceAfter=8,
    )
    body = ParagraphStyle(
        name="MktContractBody",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=13,
        spaceAfter=4,
    )
    meta = ParagraphStyle(
        name="MktContractMeta",
        parent=styles["BodyText"],
        fontSize=8.5,
        textColor=HexColor("#444444"),
        spaceAfter=10,
    )
    story = [
        Paragraph("LETTER — Contrato de intermediação (ack no chat)", title),
        Paragraph(
            f"Comprador: <b>{lead_name or '—'}</b><br/>"
            f"Aceito em: <b>{ack.get('accepted_at') or '—'}</b><br/>"
            f"Provedor: <b>{ack.get('provider') or 'SITE_CHAT_ACK'}</b> · canal {ack.get('channel') or 'SITE_CHAT'}",
            meta,
        ),
        Spacer(1, 2 * mm),
    ]
    story.extend(_html_to_paragraphs(html, body, meta))
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Documento gerado a partir do aceite no chat do site. Assinatura eletrônica ZapSign "
            "pode ser anexada em frente futura sem alterar o ciclo CONCLUIDO.",
            meta,
        )
    )
    doc.build(story)
    return buffer.getvalue()


def marketplace_contract_pdf_bytes(db: Session, user: User, lead_id: str) -> tuple[bytes, str]:
    lead = get_lead_for_user(db, user, lead_id)
    html, ack = resolve_contract_html(db, user, lead_id)
    pdf = build_site_contract_pdf(html=html, ack=ack, lead_name=lead.name)
    filename = f"contrato-marketplace-{lead_id[:8]}.pdf"
    return pdf, filename


def list_marketplace_lead_documents(db: Session, user: User, lead_id: str) -> list[Document]:
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


def read_marketplace_lead_document(
    db: Session,
    user: User,
    lead_id: str,
    document_id: str,
) -> tuple[bytes, str, str]:
    get_lead_for_user(db, user, lead_id)
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == user.organization_id,
            Document.entity_type == ENTITY_TYPE,
            Document.entity_id == lead_id,
        )
    )
    if not document:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    if user.role == Role.CLIENT and user.id != document.uploaded_by_id:
        # cliente da compra pode baixar qualquer doc do próprio lead (já gated por get_lead_for_user)
        pass
    data = get_storage().get(document.storage_key)
    if not data:
        raise HTTPException(status_code=404, detail="Arquivo ausente no storage")
    media = "application/pdf" if document.filename.lower().endswith(".pdf") else "application/octet-stream"
    if document.filename.lower().endswith((".png",)):
        media = "image/png"
    elif document.filename.lower().endswith((".jpg", ".jpeg")):
        media = "image/jpeg"
    return data, document.filename, media
