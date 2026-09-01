"""Cobrança recorrente LSS SaaS via Asaas (assinatura + webhooks)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.asaas_client import AsaasClient
from app.asaas_common import asaas_api_available
from app.core.config import settings
from app.models import SaaSPlan, SaaSSubscription

LSS_BILLING_TYPES = {"BOLETO", "PIX", "CREDIT_CARD", "UNDEFINED"}
PAYMENT_CONFIRMED_EVENTS = {"PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"}
PAYMENT_OVERDUE_EVENTS = {"PAYMENT_OVERDUE", "PAYMENT_DELETED", "PAYMENT_REFUNDED"}


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def lss_billing_live() -> bool:
    return settings.lss_billing_enabled and asaas_api_available()


def _resolve_billing_type(value: str | None) -> str:
    billing_type = (value or settings.lss_default_billing_type or "BOLETO").strip().upper()
    if billing_type not in LSS_BILLING_TYPES:
        raise HTTPException(status_code=422, detail="Forma de pagamento LSS inválida (BOLETO, PIX, CREDIT_CARD ou UNDEFINED).")
    return billing_type


def _first_checkout_url(client: AsaasClient, asaas_subscription_id: str) -> tuple[str | None, str | None, str | None]:
    payload = client.list_subscription_payments(asaas_subscription_id, limit=5)
    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        payment_id = str(row.get("id") or "").strip() or None
        status = str(row.get("status") or "").strip() or None
        checkout = (
            str(row.get("invoiceUrl") or row.get("bankSlipUrl") or row.get("transactionReceiptUrl") or "").strip()
            or None
        )
        if checkout or payment_id:
            return checkout, payment_id, status
    return None, None, None


def provision_asaas_subscription(
    db: Session,
    item: SaaSSubscription,
    plan: SaaSPlan,
    *,
    company_cnpj: str,
    subscriber_email: str,
    subscriber_phone: str | None,
    billing_type: str | None,
) -> SaaSSubscription:
    if not lss_billing_live():
        item.status = "ACTIVE_SANDBOX"
        return item

    resolved_type = _resolve_billing_type(billing_type)
    cnpj = "".join(x for x in company_cnpj if x.isdigit())
    if len(cnpj) != 14:
        raise HTTPException(status_code=422, detail="CNPJ inválido para cobrança Asaas.")

    item.billing_type = resolved_type
    item.subscriber_email = subscriber_email.strip()
    item.status = "PENDING_PAYMENT"

    with AsaasClient() as client:
        customer = client.create_customer(
            {
                "name": item.subscriber_company_name,
                "company": item.subscriber_company_name,
                "cpfCnpj": cnpj,
                "email": item.subscriber_email,
                "mobilePhone": (subscriber_phone or settings.asaas_subaccount_default_mobile_phone).strip(),
                "externalReference": item.id,
                "notificationDisabled": False,
            }
        )
        customer_id = str(customer.get("id") or "").strip()
        if not customer_id:
            raise HTTPException(status_code=502, detail="Asaas não retornou identificador do cliente.")

        next_due = _aware(item.current_period_start).date().isoformat()
        subscription = client.create_subscription(
            {
                "customer": customer_id,
                "billingType": resolved_type,
                "value": float(Decimal(str(plan.monthly_price))),
                "nextDueDate": next_due,
                "cycle": "MONTHLY",
                "description": f"LSS {plan.name} · LETTER Platform",
                "externalReference": item.id,
            }
        )
        asaas_subscription_id = str(subscription.get("id") or "").strip()
        if not asaas_subscription_id:
            raise HTTPException(status_code=502, detail="Asaas não retornou identificador da assinatura.")

        checkout_url, payment_id, payment_status = _first_checkout_url(client, asaas_subscription_id)

    item.asaas_customer_id = customer_id
    item.asaas_subscription_id = asaas_subscription_id
    item.last_payment_id = payment_id
    item.last_payment_status = payment_status
    item.payment_checkout_url = checkout_url
    db.flush()
    return item


def cancel_asaas_subscription(item: SaaSSubscription) -> None:
    if not item.asaas_subscription_id or not asaas_api_available():
        return
    with AsaasClient() as client:
        client.delete_subscription(item.asaas_subscription_id)


def _find_subscription_for_payment(db: Session, payment: dict) -> SaaSSubscription | None:
    external_ref = str(payment.get("externalReference") or "").strip()
    asaas_subscription_id = str(payment.get("subscription") or "").strip()
    if external_ref:
        item = db.scalar(select(SaaSSubscription).where(SaaSSubscription.id == external_ref))
        if item:
            return item
    if asaas_subscription_id:
        return db.scalar(select(SaaSSubscription).where(SaaSSubscription.asaas_subscription_id == asaas_subscription_id))
    payment_id = str(payment.get("id") or "").strip()
    if payment_id:
        return db.scalar(select(SaaSSubscription).where(SaaSSubscription.last_payment_id == payment_id))
    return None


def _apply_payment_period(item: SaaSSubscription, payment: dict) -> None:
    due_date = payment.get("dueDate") or payment.get("originalDueDate")
    if due_date:
        try:
            start = datetime.fromisoformat(str(due_date)).replace(tzinfo=UTC)
        except ValueError:
            start = _aware(item.current_period_start)
    else:
        start = _aware(item.current_period_start)
    item.current_period_start = start
    item.current_period_end = start + timedelta(days=30)
    item.status = "ACTIVE"


def handle_lss_payment_webhook(db: Session, event: str, payment: dict) -> SaaSSubscription | None:
    item = _find_subscription_for_payment(db, payment)
    if not item:
        return None

    payment_id = str(payment.get("id") or "").strip() or None
    payment_status = str(payment.get("status") or "").strip() or None
    if payment_id:
        item.last_payment_id = payment_id
    if payment_status:
        item.last_payment_status = payment_status
    checkout = str(payment.get("invoiceUrl") or payment.get("bankSlipUrl") or "").strip()
    if checkout:
        item.payment_checkout_url = checkout

    if event in PAYMENT_CONFIRMED_EVENTS:
        _apply_payment_period(item, payment)
    elif event in PAYMENT_OVERDUE_EVENTS:
        if item.status not in {"CANCELLATION_SCHEDULED", "CANCELLED"}:
            item.status = "PAST_DUE"
    elif event == "PAYMENT_CREATED" and item.status == "ACTIVE":
        item.status = "PAST_DUE" if payment_status == "OVERDUE" else item.status

    db.flush()
    return item


def evaluate_subscription_billing(item: SaaSSubscription, as_of: datetime | None = None) -> SaaSSubscription:
    now = as_of or datetime.now(UTC)
    period_end = _aware(item.current_period_end)
    grace = timedelta(days=settings.lss_billing_grace_days)

    if item.status == "CANCELLATION_SCHEDULED" and now > period_end:
        item.status = "CANCELLED"
        cancel_asaas_subscription(item)
        return item

    if item.asaas_subscription_id:
        if item.status in {"ACTIVE", "PAST_DUE", "PENDING_PAYMENT"} and now > period_end + grace:
            item.status = "SUSPENDED"
        elif item.status == "ACTIVE" and now > period_end:
            item.status = "PAST_DUE"
        return item

    if item.status in {"ACTIVE_SANDBOX", "PAST_DUE"} and now > period_end + grace:
        item.status = "SUSPENDED_PAST_DUE_SANDBOX"
    elif item.status == "ACTIVE_SANDBOX" and now > period_end:
        item.status = "PAST_DUE"
    return item


def run_lss_billing_evaluation_job(db: Session) -> dict:
    items = list(db.scalars(select(SaaSSubscription).order_by(SaaSSubscription.created_at.desc())))
    processed: list[dict] = []
    for item in items:
        before = item.status
        evaluate_subscription_billing(item)
        if before != item.status:
            processed.append({"subscription_id": item.id, "from": before, "to": item.status})
    return {
        "processed": len(processed),
        "items": processed,
        "enabled": settings.lss_billing_enabled,
        "synced_at": datetime.now(UTC).isoformat(),
    }
