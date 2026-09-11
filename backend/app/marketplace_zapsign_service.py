"""Assinatura ZapSign para contratos do chat Marketplace (sem Contract FinOps)."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.marketplace_contract_docs_service import build_site_contract_pdf
from app.models import Lead, Proposal
from app.zapsign_client import ZapSignClient
from app.zapsign_signature_service import zapsign_configured


def _parse_json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def zapsign_view_from_terms(terms: dict) -> dict | None:
    block = terms.get("zapsign") if isinstance(terms.get("zapsign"), dict) else None
    if not block or not block.get("external_id"):
        return None
    return {
        "provider": block.get("provider") or "ZAPSIGN",
        "status": block.get("status") or "SENT",
        "sign_url": block.get("sign_url"),
        "signed_at": block.get("signed_at"),
        "signer_email": block.get("signer_email"),
        "error": block.get("error"),
    }


def _signer_payload(email: str, name: str | None) -> dict:
    signer: dict = {
        "email": email,
        "auth_mode": settings.zapsign_auth_mode,
        "send_automatic_email": settings.zapsign_send_automatic_email,
    }
    if name and name.strip():
        signer["name"] = name.strip()
    return signer


def ensure_marketplace_zapsign(
    db: Session,
    *,
    lead: Lead,
    proposal: Proposal,
    html: str,
    ack: dict,
    signer_email: str,
    signer_name: str | None = None,
) -> dict | None:
    """Envia PDF do contrato do chat ao ZapSign. Idempotente; falhas não bloqueiam o fluxo."""
    terms = _parse_json(proposal.terms_json)
    existing = terms.get("zapsign") if isinstance(terms.get("zapsign"), dict) else {}
    if existing.get("external_id") and existing.get("status") in {"SENT", "SIGNED"}:
        return existing

    if not zapsign_configured():
        return None

    email = (signer_email or "").strip().lower()
    if not email or "@" not in email:
        return None

    name = (signer_name or lead.name or email.split("@", 1)[0]).strip()
    doc_name = f"Contrato Marketplace {lead.name or lead.id}"[:255]

    try:
        pdf_bytes = build_site_contract_pdf(html=html, ack=ack, lead_name=lead.name)
        with ZapSignClient() as client:
            created = client.create_doc_from_pdf(
                name=doc_name,
                base64_pdf=base64.b64encode(pdf_bytes).decode("ascii"),
                signers=[_signer_payload(email, name)],
                external_id=f"marketplace_lead:{lead.id}",
                lang=settings.zapsign_lang,
            )
        doc_token = str(created.get("token", "")).strip()
        signers = created.get("signers") if isinstance(created.get("signers"), list) else []
        sign_url = ""
        if signers and isinstance(signers[0], dict):
            sign_url = str(signers[0].get("sign_url") or "").strip()
        if not doc_token:
            raise ValueError("ZapSign não retornou token do documento.")

        block = {
            "provider": "ZAPSIGN",
            "external_id": doc_token,
            "sign_url": sign_url or None,
            "status": "SENT",
            "sent_at": datetime.now(UTC).isoformat(),
            "signer_email": email,
            "signer_name": name,
            "doc_status": created.get("status"),
        }
    except Exception as exc:  # noqa: BLE001 — chat não pode falhar por ZapSign
        block = {
            "provider": "ZAPSIGN",
            "status": "ERROR",
            "error": str(exc)[:500],
            "signer_email": email,
            "sent_at": datetime.now(UTC).isoformat(),
        }

    terms["zapsign"] = block
    ack_block = terms.get("contract_ack") if isinstance(terms.get("contract_ack"), dict) else dict(ack)
    if block.get("status") == "SENT":
        ack_block["zapsign_envelope_id"] = block.get("external_id")
        ack_block["zapsign_pending"] = True
    proposal.terms_json = json.dumps(terms, ensure_ascii=False)
    db.flush()
    return block


def refresh_marketplace_zapsign(db: Session, proposal: Proposal) -> dict | None:
    terms = _parse_json(proposal.terms_json)
    block = terms.get("zapsign") if isinstance(terms.get("zapsign"), dict) else None
    if not block or not block.get("external_id") or block.get("status") == "SIGNED":
        return zapsign_view_from_terms(terms)

    if not zapsign_configured():
        return zapsign_view_from_terms(terms)

    try:
        with ZapSignClient() as client:
            doc = client.get_doc(str(block["external_id"]))
    except Exception as exc:  # noqa: BLE001
        block["last_refresh_error"] = str(exc)[:300]
        terms["zapsign"] = block
        proposal.terms_json = json.dumps(terms, ensure_ascii=False)
        db.flush()
        return zapsign_view_from_terms(terms)

    doc_status = str(doc.get("status") or "").lower()
    signers = doc.get("signers") if isinstance(doc.get("signers"), list) else []
    signed_at = None
    signer_email = str(block.get("signer_email") or "").lower()
    for signer in signers:
        if isinstance(signer, dict) and str(signer.get("email", "")).lower() == signer_email:
            signed_at = signer.get("signed_at")
            if signer.get("sign_url"):
                block["sign_url"] = signer.get("sign_url")
            break

    block["doc_status"] = doc_status
    if doc_status in {"signed", "finished", "completed"} or signed_at:
        block["status"] = "SIGNED"
        block["signed_at"] = signed_at or datetime.now(UTC).isoformat()
        ack = terms.get("contract_ack") if isinstance(terms.get("contract_ack"), dict) else {}
        ack["provider"] = "ZAPSIGN"
        ack["zapsign_pending"] = False
        ack["zapsign_signed_at"] = block["signed_at"]
        terms["contract_ack"] = ack

    terms["zapsign"] = block
    proposal.terms_json = json.dumps(terms, ensure_ascii=False)
    db.flush()
    return zapsign_view_from_terms(terms)
