"""Envio de contratos para assinatura eletrônica via ZapSign."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.document_service import contract_pdf
from app.models import CalculationMemory, Contract, Proposal, SignatureEnvelope, User
from app.schemas import SignatureCreate
from app.zapsign_client import ZapSignClient


def zapsign_configured() -> bool:
    return bool(settings.zapsign_api_token and settings.zapsign_api_token.strip())


def zapsign_environment() -> str:
    url = settings.zapsign_base_url.lower()
    if "sandbox" in url:
        return "sandbox"
    return "production"


def zapsign_status() -> dict:
    if not zapsign_configured():
        return {
            "configured": False,
            "connected": False,
            "provider": "ZAPSIGN",
            "environment": zapsign_environment(),
            "message": "Configure LETTER_ZAPSIGN_API_TOKEN.",
        }
    with ZapSignClient() as client:
        payload = client.list_docs(page=1)
    total = payload.get("total") if isinstance(payload.get("total"), int) else None
    return {
        "configured": True,
        "connected": True,
        "provider": "ZAPSIGN",
        "environment": zapsign_environment(),
        "documents_total": total,
        "message": "Conexão ZapSign validada.",
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


def create_zapsign_envelope(db: Session, user: User, contract: Contract, payload: SignatureCreate) -> SignatureEnvelope:
    proposal = db.get(Proposal, contract.proposal_id)
    calculation = db.get(CalculationMemory, contract.calculation_memory_id)
    if not proposal or not calculation:
        raise HTTPException(status_code=422, detail="Contrato sem proposta ou memória de cálculo para gerar PDF.")

    pdf_bytes = contract_pdf(contract, proposal, calculation)
    doc_name = f"Contrato {contract.contract_number}"[:255]
    signer_email = str(payload.signer_email)
    signer_name = payload.signer_name or signer_email.split("@", 1)[0]

    with ZapSignClient() as client:
        created = client.create_doc_from_pdf(
            name=doc_name,
            base64_pdf=base64.b64encode(pdf_bytes).decode("ascii"),
            signers=[_signer_payload(signer_email, signer_name)],
            external_id=contract.id,
            lang=settings.zapsign_lang,
        )

    doc_token = str(created.get("token", "")).strip()
    if not doc_token:
        raise HTTPException(status_code=502, detail="ZapSign não retornou token do documento.")

    signers = created.get("signers") if isinstance(created.get("signers"), list) else []
    sign_url = ""
    if signers and isinstance(signers[0], dict):
        sign_url = str(signers[0].get("sign_url") or "").strip()

    envelope = SignatureEnvelope(
        organization_id=user.organization_id,
        contract_id=contract.id,
        provider="ZAPSIGN",
        external_id=doc_token,
        signer_email=signer_email,
        status="SENT",
        sent_at=datetime.now(UTC),
        evidence_json=json.dumps(
            {
                "zapsign_doc_token": doc_token,
                "sign_url": sign_url,
                "signer_name": signer_name,
                "doc_status": created.get("status"),
            }
        ),
    )
    db.add(envelope)
    return envelope


def refresh_zapsign_envelope(db: Session, envelope: SignatureEnvelope) -> SignatureEnvelope:
    if envelope.provider != "ZAPSIGN":
        raise HTTPException(status_code=409, detail="Atualização disponível apenas para envelopes ZapSign.")
    if envelope.status == "SIGNED":
        return envelope

    with ZapSignClient() as client:
        doc = client.get_doc(envelope.external_id)

    doc_status = str(doc.get("status") or "").lower()
    signers = doc.get("signers") if isinstance(doc.get("signers"), list) else []
    signed_at = None
    for signer in signers:
        if isinstance(signer, dict) and str(signer.get("email", "")).lower() == envelope.signer_email.lower():
            signed_at = signer.get("signed_at")
            break

    evidence = {}
    try:
        evidence = json.loads(envelope.evidence_json or "{}")
    except json.JSONDecodeError:
        evidence = {}

    evidence["doc_status"] = doc_status
    if signers:
        first = signers[0] if isinstance(signers[0], dict) else {}
        if first.get("sign_url"):
            evidence["sign_url"] = first["sign_url"]

    if doc_status in {"signed", "finished", "completed"} or signed_at:
        envelope.status = "SIGNED"
        envelope.signed_at = datetime.now(UTC)
        contract = db.get(Contract, envelope.contract_id)
        if contract:
            contract.status = "SIGNED"
        evidence["signed_at"] = signed_at or envelope.signed_at.isoformat()

    envelope.evidence_json = json.dumps(evidence)
    return envelope


def create_mock_envelope(db: Session, user: User, contract: Contract, payload: SignatureCreate) -> SignatureEnvelope:
    envelope = SignatureEnvelope(
        organization_id=user.organization_id,
        contract_id=contract.id,
        provider="MOCK",
        external_id=f"mock_sign_{__import__('uuid').uuid4().hex}",
        signer_email=str(payload.signer_email),
        status="SENT",
        sent_at=datetime.now(UTC),
    )
    db.add(envelope)
    return envelope


def envelope_sign_url(envelope: SignatureEnvelope) -> str | None:
    if envelope.provider != "ZAPSIGN":
        return None
    try:
        evidence = json.loads(envelope.evidence_json or "{}")
    except json.JSONDecodeError:
        return None
    url = evidence.get("sign_url")
    return str(url) if url else None


def envelope_to_view(envelope: SignatureEnvelope) -> dict:
    return {
        "id": envelope.id,
        "contract_id": envelope.contract_id,
        "provider": envelope.provider,
        "external_id": envelope.external_id,
        "signer_email": envelope.signer_email,
        "status": envelope.status,
        "sent_at": envelope.sent_at,
        "signed_at": envelope.signed_at,
        "sign_url": envelope_sign_url(envelope),
    }
