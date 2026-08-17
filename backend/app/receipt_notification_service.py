import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CommunicationTemplate, Lead, PaymentReceipt, User
from app.tax_communication_service import mock_deliver, queue_delivery


RECEIPT_EMAIL_TEMPLATE_KEY = "FINOPS_RECEIPT_V3"
RECEIPT_PUSH_TEMPLATE_KEY = "FINOPS_RECEIPT_PUSH_V3"


def _ensure_template(
    db: Session, user: User, *, key: str, channel: str, subject: str, body: str,
) -> CommunicationTemplate:
    item = db.scalar(
        select(CommunicationTemplate).where(
            CommunicationTemplate.organization_id == user.organization_id,
            CommunicationTemplate.key == key,
            CommunicationTemplate.channel == channel,
            CommunicationTemplate.active.is_(True),
        )
    )
    if item:
        return item
    current = db.scalar(
        select(CommunicationTemplate.version).where(
            CommunicationTemplate.organization_id == user.organization_id,
            CommunicationTemplate.key == key,
            CommunicationTemplate.channel == channel,
        )
    ) or 0
    item = CommunicationTemplate(
        organization_id=user.organization_id,
        key=key,
        channel=channel,
        version=current + 1,
        subject=subject,
        body=body,
        purpose="TRANSACTIONAL",
        active=True,
    )
    db.add(item)
    db.flush()
    return item


def dispatch_receipt_notifications(
    db: Session,
    user: User,
    receipt: PaymentReceipt,
    lead: Lead | None,
) -> dict:
    """Dispara e-mail e push transacionais D+0 conforme doc FinOps V3."""
    customer_route = receipt.customer_route
    variables = {
        "month": str(receipt.reference_month),
        "total": str(receipt.total_paid),
        "fruicao": str(receipt.fruicao_amount),
        "amortizacao": str(receipt.amortizacao_amount),
        "receipt_link": customer_route,
        "contract_id": receipt.contract_id,
    }
    email_template = _ensure_template(
        db, user,
        key=RECEIPT_EMAIL_TEMPLATE_KEY,
        channel="EMAIL",
        subject="Recibo FinOps — competência mês {{month}}",
        body=(
            "Recibo de Fruição e Amortização disponível.\n"
            "Competência: mês {{month}}\n"
            "Total liquidado: R$ {{total}}\n"
            "Fruição: R$ {{fruicao}} · Amortização: R$ {{amortizacao}}\n"
            "Acesso: {{receipt_link}}"
        ),
    )
    push_template = _ensure_template(
        db, user,
        key=RECEIPT_PUSH_TEMPLATE_KEY,
        channel="PUSH",
        subject="Recibo disponível",
        body="Recibo mês {{month}} emitido. Total R$ {{total}}.",
    )
    destination = (lead.phone if lead and lead.phone else f"receipt-{receipt.contract_id}@letter.local")
    partner_destination = f"partner-{receipt.partner_id.lower()}@letter.local"
    deliveries = []
    for template, dest, subject_id in (
        (email_template, destination, receipt.contract_id),
        (push_template, destination, receipt.contract_id),
        (email_template, partner_destination, receipt.partner_id),
    ):
        delivery, created = queue_delivery(
            db, user, template,
            subject_type="CONTRACT",
            subject_id=subject_id,
            destination=dest,
            idempotency_key=f"receipt-{receipt.id}-{template.channel}-{dest}",
            variables=variables,
        )
        if created:
            mock_deliver(delivery)
        deliveries.append({"channel": template.channel, "destination": delivery.destination_masked, "status": delivery.status})
    return {"trigger_email_automatico": "SENT_D+0", "trigger_push_notificacao": "ACTIVE", "deliveries": deliveries}
