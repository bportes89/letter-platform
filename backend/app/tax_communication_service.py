import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    CommissionEntry, CommunicationConsent, CommunicationDelivery,
    CommunicationTemplate, TaxClosing, TaxDocument, TaxException, User,
)


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def issue_tax_document(db: Session, user: User, target: User, reference_month: str, gross_amount: Decimal, tax_amount: Decimal, content: str) -> TaxDocument:
    digest = hashlib.sha256(content.encode()).hexdigest()
    existing = db.scalar(select(TaxDocument).where(TaxDocument.content_hash == digest))
    if existing:
        return existing
    item = TaxDocument(
        organization_id=user.organization_id, user_id=target.id, reference_month=reference_month,
        document_number=f"NFSE-MOCK-{reference_month.replace('-', '')}-{uuid4().hex[:8].upper()}",
        gross_amount=money(gross_amount), tax_amount=money(tax_amount), content_hash=digest,
    )
    db.add(item)
    return item


def close_tax_month(db: Session, user: User, reference_month: str) -> TaxClosing:
    existing = db.scalar(select(TaxClosing).where(TaxClosing.organization_id == user.organization_id, TaxClosing.reference_month == reference_month))
    if existing:
        return existing
    entries = list(db.scalars(select(CommissionEntry).where(CommissionEntry.organization_id == user.organization_id)))
    entries = [x for x in entries if x.created_at.strftime("%Y-%m") == reference_month]
    documents = list(db.scalars(select(TaxDocument).where(TaxDocument.organization_id == user.organization_id, TaxDocument.reference_month == reference_month, TaxDocument.status == "VALIDATED")))
    gross = money(sum((Decimal(str(x.amount)) for x in entries), Decimal("0")))
    documented = money(sum((Decimal(str(x.gross_amount)) for x in documents), Decimal("0")))
    closing = TaxClosing(
        organization_id=user.organization_id, reference_month=reference_month,
        gross_commissions=gross, documented_amount=documented,
        eligible_payout=min(gross, documented), closed_by_id=user.id,
    )
    db.add(closing); db.flush()
    by_user: dict[str, Decimal] = {}
    docs_by_user: dict[str, Decimal] = {}
    for entry in entries: by_user[entry.beneficiary_id] = by_user.get(entry.beneficiary_id, Decimal("0")) + Decimal(str(entry.amount))
    for document in documents: docs_by_user[document.user_id] = docs_by_user.get(document.user_id, Decimal("0")) + Decimal(str(document.gross_amount))
    for user_id, amount in by_user.items():
        missing = money(max(Decimal("0"), amount - docs_by_user.get(user_id, Decimal("0"))))
        if missing:
            db.add(TaxException(organization_id=user.organization_id, closing_id=closing.id, user_id=user_id, reason="MISSING_OR_INSUFFICIENT_NFSE", amount=missing))
            closing.exception_count += 1
    closing.status = "EXCEPTIONS" if closing.exception_count else "CLOSED"
    closing.closed_at = datetime.now(UTC)
    return closing


def resolve_tax_exception(item: TaxException, user: User, note: str) -> TaxException:
    if item.status != "OPEN":
        raise HTTPException(status_code=409, detail="Exceção fiscal já resolvida")
    item.status = "RESOLVED"; item.resolved_by_id = user.id; item.resolved_at = datetime.now(UTC); item.resolution_note = note
    return item


def create_template(db: Session, user: User, key: str, channel: str, subject: str | None, body: str, purpose: str) -> CommunicationTemplate:
    current = db.scalar(select(func.max(CommunicationTemplate.version)).where(CommunicationTemplate.organization_id == user.organization_id, CommunicationTemplate.key == key, CommunicationTemplate.channel == channel)) or 0
    for old in db.scalars(select(CommunicationTemplate).where(CommunicationTemplate.organization_id == user.organization_id, CommunicationTemplate.key == key, CommunicationTemplate.channel == channel, CommunicationTemplate.active.is_(True))): old.active = False
    item = CommunicationTemplate(organization_id=user.organization_id, key=key, channel=channel, version=current + 1, subject=subject, body=body, purpose=purpose)
    db.add(item); return item


def update_consent(db: Session, user: User, subject_type: str, subject_id: str, channel: str, status: str, source: str, evidence: dict) -> CommunicationConsent:
    item = db.scalar(select(CommunicationConsent).where(CommunicationConsent.organization_id == user.organization_id, CommunicationConsent.subject_type == subject_type, CommunicationConsent.subject_id == subject_id, CommunicationConsent.channel == channel))
    if not item:
        item = CommunicationConsent(organization_id=user.organization_id, subject_type=subject_type, subject_id=subject_id, channel=channel)
        db.add(item)
    item.status=status; item.source=source; item.evidence_json=json.dumps(evidence,ensure_ascii=False); item.changed_at=datetime.now(UTC)
    return item


def queue_delivery(db: Session, user: User, template: CommunicationTemplate, subject_type: str, subject_id: str, destination: str, idempotency_key: str, variables: dict) -> tuple[CommunicationDelivery, bool]:
    existing=db.scalar(select(CommunicationDelivery).where(CommunicationDelivery.idempotency_key==idempotency_key))
    if existing: return existing,False
    consent=db.scalar(select(CommunicationConsent).where(CommunicationConsent.organization_id==user.organization_id,CommunicationConsent.subject_type==subject_type,CommunicationConsent.subject_id==subject_id,CommunicationConsent.channel==template.channel))
    if (template.purpose=="MARKETING" and (not consent or consent.status!="OPT_IN")) or (consent and consent.status=="OPT_OUT"):
        raise HTTPException(status_code=422,detail="Envio bloqueado por ausência de consentimento ou opt-out")
    rendered=template.body
    for key,value in variables.items(): rendered=rendered.replace("{{"+key+"}}",str(value))
    masked=(destination[:2]+"***"+destination[-3:]) if len(destination)>5 else "***"
    item=CommunicationDelivery(organization_id=user.organization_id,template_id=template.id,subject_type=subject_type,subject_id=subject_id,destination_masked=masked,idempotency_key=idempotency_key,rendered_body=rendered)
    db.add(item);return item,True


def mock_deliver(item: CommunicationDelivery) -> CommunicationDelivery:
    if item.status == "DELIVERED": return item
    item.status="DELIVERED";item.provider_message_id=f"mock_{uuid4().hex}";item.delivered_at=datetime.now(UTC);return item
