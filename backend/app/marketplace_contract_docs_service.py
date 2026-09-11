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


def resolve_contract_html(db: Session, user: User, lead_id: str) -> tuple[str, dict]:
    lead = get_lead_for_user(db, user, lead_id)
    proposal = _proposal_for_lead(db, user, lead)
    terms = _parse_json(proposal.terms_json) if proposal else {}
    snap = {}
    try:
        detail = _parse_json(lead.scr_detail_json)
        snap = detail.get("chat") if isinstance(detail.get("chat"), dict) else {}
    except Exception:
        snap = {}
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
