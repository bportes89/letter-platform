import hashlib
import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (AcceptanceTemplate, Contract, OperationalJob, SellerEvidenceAudit,
                        QuotaTransferVerification, TransactionAcceptance, User)

TYPES = {"CHECKOUT_INITIAL", "TRANSFER_RELEASE"}


def canonical_hash(value: dict | str) -> str:
    raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def create_template(db: Session, user: User, *, acceptance_type: str, version: int, title: str, body: str) -> AcceptanceTemplate:
    if acceptance_type not in TYPES:
        raise HTTPException(422, "Tipo de aceite inválido")
    item = AcceptanceTemplate(organization_id=user.organization_id, acceptance_type=acceptance_type,
        version=version, title=title, body=body, body_hash=canonical_hash(body), created_by_id=user.id)
    db.add(item); db.flush(); return item


def approve_template(db: Session, user: User, item: AcceptanceTemplate) -> AcceptanceTemplate:
    for other in db.scalars(select(AcceptanceTemplate).where(AcceptanceTemplate.organization_id==user.organization_id,
            AcceptanceTemplate.acceptance_type==item.acceptance_type, AcceptanceTemplate.active.is_(True))):
        other.active=False
    item.legal_review_status="APPROVED"; item.active=True; item.approved_by_id=user.id; item.approved_at=datetime.now(UTC)
    return item


def active_template(db: Session, organization_id: str, kind: str) -> AcceptanceTemplate:
    item=db.scalar(select(AcceptanceTemplate).where(AcceptanceTemplate.organization_id==organization_id,
        AcceptanceTemplate.acceptance_type==kind, AcceptanceTemplate.active.is_(True),
        AcceptanceTemplate.legal_review_status=="APPROVED").order_by(AcceptanceTemplate.version.desc()))
    if not item: raise HTTPException(409, f"Texto {kind} não possui versão ativa aprovada pelo jurídico")
    return item


def record_acceptance(db: Session, user: User, contract: Contract, kind: str, evidence: dict,
                      ip_address: str | None, user_agent: str | None) -> TransactionAcceptance:
    existing=db.scalar(select(TransactionAcceptance).where(TransactionAcceptance.contract_id==contract.id,
        TransactionAcceptance.acceptance_type==kind))
    if existing: return existing
    template=active_template(db,user.organization_id,kind)
    snapshot={"contract_id":contract.id,"acceptance_type":kind,"template_id":template.id,"template_version":template.version,
              "template_hash":template.body_hash,"accepted_by":user.id,"evidence":evidence}
    item=TransactionAcceptance(organization_id=user.organization_id,contract_id=contract.id,template_id=template.id,
        acceptance_type=kind,accepted_by_id=user.id,evidence_json=json.dumps(snapshot,ensure_ascii=False,sort_keys=True),
        evidence_hash=canonical_hash(snapshot),ip_address=ip_address,user_agent=user_agent)
    db.add(item);db.flush();return item


def accept_checkout(db: Session, user: User, contract: Contract, *, confirmation: bool, read_full_contract: bool,
                    ip_address: str | None, user_agent: str | None) -> TransactionAcceptance:
    if not confirmation or not read_full_contract: raise HTTPException(422,"Leitura do contrato e manifestação expressa são obrigatórias")
    if contract.status not in {"DRAFT","ACCEPTED"}: raise HTTPException(409,"Contrato indisponível para o aceite inicial")
    item=record_acceptance(db,user,contract,"CHECKOUT_INITIAL",{"confirmation":True,"read_full_contract":True},ip_address,user_agent)
    contract.status="ACCEPTED";contract.accepted_at=item.accepted_at;contract.accepted_by_id=user.id
    contract.evidence_json=item.evidence_json
    return item


def open_window(db: Session, user: User, contract: Contract, administrator_reference: str, quota_id: str | None) -> QuotaTransferVerification:
    initial=db.scalar(select(TransactionAcceptance).where(TransactionAcceptance.contract_id==contract.id,
        TransactionAcceptance.acceptance_type=="CHECKOUT_INITIAL"))
    if not initial: raise HTTPException(409,"Aceite inicial do checkout ainda não registrado")
    seller_audit=db.scalar(select(SellerEvidenceAudit).where(SellerEvidenceAudit.contract_id==contract.id,SellerEvidenceAudit.status=="APPROVED"))
    if not seller_audit: raise HTTPException(409,"Os três lastros do vendedor exigem OCR conforme e aprovação humana antes da janela de 24 horas")
    existing=db.scalar(select(QuotaTransferVerification).where(QuotaTransferVerification.contract_id==contract.id))
    if existing: return existing
    now=datetime.now(UTC); deadline=now+timedelta(hours=24)
    item=QuotaTransferVerification(organization_id=user.organization_id,contract_id=contract.id,quota_id=quota_id,
        status="AUDIT_WINDOW_OPEN",administrator_reference=administrator_reference,transfer_reported_at=now,
        audit_deadline_at=deadline,evidence_json=json.dumps({"source":"ADMINISTRATOR_TRANSFER_REPORT","initial_acceptance_id":initial.id,"seller_evidence_audit_id":seller_audit.id}))
    db.add(item);db.flush()
    for suffix,scheduled,kind in [("start",now,"QUOTA_AUDIT_WINDOW_STARTED"),("12h",now+timedelta(hours=12),"QUOTA_AUDIT_REMINDER_12H"),("2h",deadline-timedelta(hours=2),"QUOTA_AUDIT_REMINDER_2H")]:
        db.add(OperationalJob(organization_id=user.organization_id,job_type=kind,idempotency_key=f"quota-audit:{item.id}:{suffix}",
            payload_json=json.dumps({"verification_id":item.id,"contract_id":contract.id,"deadline":deadline.isoformat(),"channels":["SUPER_APP","WHATSAPP","EMAIL"]}),scheduled_at=scheduled))
    return item


def confirm_release(db: Session, user: User, item: QuotaTransferVerification, *, logged_into_administrator: bool,
                    quota_in_buyer_name: bool, authorize_release: bool, biometric_reference: str | None,
                    ip_address: str | None, user_agent: str | None) -> TransactionAcceptance:
    now=datetime.now(UTC)
    if item.status!="AUDIT_WINDOW_OPEN": raise HTTPException(409,"Janela de auditoria não está aberta")
    deadline=item.audit_deadline_at
    if deadline and (deadline.tzinfo is None and now.replace(tzinfo=None)>deadline or deadline.tzinfo is not None and now>deadline):
        item.status="EXPIRED_REVIEW";item.payout_unlocked=False;raise HTTPException(409,"Janela expirada; saldo permanece bloqueado para revisão manual")
    if not all([logged_into_administrator,quota_in_buyer_name,authorize_release]):
        raise HTTPException(422,"Login, titularidade e autorização expressa são obrigatórios")
    contract=db.get(Contract,item.contract_id)
    evidence={"logged_into_administrator":True,"quota_in_buyer_name":True,"authorize_release":True,
              "administrator_reference":item.administrator_reference,"biometric_reference":biometric_reference}
    acceptance=record_acceptance(db,user,contract,"TRANSFER_RELEASE",evidence,ip_address,user_agent)
    item.status="BUYER_CONFIRMED";item.confirmed_at=now;item.payout_unlocked=True
    item.evidence_json=json.dumps({**evidence,"release_acceptance_id":acceptance.id},ensure_ascii=False,sort_keys=True)
    return acceptance


def dispute(db: Session, item: QuotaTransferVerification, reason: str) -> QuotaTransferVerification:
    if item.status not in {"AUDIT_WINDOW_OPEN","EXPIRED_REVIEW"}: raise HTTPException(409,"Verificação não aceita contestação neste estado")
    item.status="DISPUTED";item.disputed_at=datetime.now(UTC);item.payout_unlocked=False
    item.evidence_json=json.dumps({"dispute_reason":reason},ensure_ascii=False);return item
