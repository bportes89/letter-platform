"""Cobrança LSS SaaS via Banco Inter (mensalidade — boleto/PIX)."""

from __future__ import annotations

import base64
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.inter_common import inter_configured
from app.inter_cobranca_helpers import (
    issue_inter_charge,
    lss_boleto_public_token,
    pagador_from_pj,
    verify_lss_boleto_token,
)
from app.models import SaaSPlan, SaaSSubscription
from app.services import money

LSS_INTER_REF = "INTER"


def provision_inter_lss_invoice(
    db: Session,
    item: SaaSSubscription,
    plan: SaaSPlan,
    *,
    company_cnpj: str,
    subscriber_email: str,
    subscriber_phone: str | None,
) -> SaaSSubscription:
    if not inter_configured():
        raise HTTPException(status_code=503, detail="Banco Inter não configurado para LSS")

    amount = money(Decimal(str(plan.monthly_price)))
    seu = f"{item.id.replace('-', '')[:11]}L"[:15]
    pagador = pagador_from_pj(
        company_name=item.subscriber_company_name,
        cnpj=company_cnpj,
        email=subscriber_email,
        phone=subscriber_phone,
    )
    issued = issue_inter_charge(
        pagador=pagador,
        amount=amount,
        seu_numero=seu,
        mensagem_linhas=[f"LSS {plan.name}", f"Assinatura {item.id[:8]}"],
        pdf_filename_prefix=f"LSS_{item.id[:8]}",
    )
    token = lss_boleto_public_token(item.id)
    public = (settings.api_public_url or "").rstrip("/")
    boleto_url = f"{public}/lss/subscriptions/{item.id}/boleto/{token}" if public else None

    cnpj_digits = "".join(x for x in company_cnpj if x.isdigit())
    item.billing_type = "INTER"
    item.payment_method_reference = LSS_INTER_REF
    item.asaas_customer_id = cnpj_digits[:14] if len(cnpj_digits) >= 14 else cnpj_digits
    item.asaas_subscription_id = None
    item.subscriber_email = subscriber_email.strip()
    item.status = "PENDING_PAYMENT"
    item.last_payment_id = issued["codigo_solicitacao"]
    item.last_payment_status = "PENDING"
    item.payment_checkout_url = boleto_url
    item.recurring_authorized = True
    db.flush()
    return item


def read_lss_boleto_pdf_bytes(db: Session, subscription_id: str, token: str) -> tuple[bytes, str]:
    if not verify_lss_boleto_token(subscription_id, token):
        raise HTTPException(status_code=403, detail="Token de boleto LSS inválido")
    item = db.get(SaaSSubscription, subscription_id)
    if not item or item.payment_method_reference != LSS_INTER_REF:
        raise HTTPException(status_code=404, detail="Assinatura LSS não encontrada")
    codigo = (item.last_payment_id or "").strip()
    if not codigo or not inter_configured():
        raise HTTPException(status_code=404, detail="PDF LSS indisponível")
    from app.inter_client import InterClient

    client = InterClient()
    pdf_b64 = client.download_pdf_base64(codigo)
    return base64.b64decode(pdf_b64), f"lss-{subscription_id[:8]}.pdf"


def handle_lss_inter_payment_webhook(
    db: Session,
    *,
    codigo_solicitacao: str,
    valor_recebido: Decimal | str | float,
) -> SaaSSubscription | None:
    from app.lss_billing_service import _apply_payment_period, _record_lss_recurring_accrual

    codigo = str(codigo_solicitacao or "").strip()
    if not codigo:
        return None
    item = db.scalar(
        select(SaaSSubscription).where(
            SaaSSubscription.last_payment_id == codigo,
            SaaSSubscription.payment_method_reference == LSS_INTER_REF,
        )
    )
    if not item:
        return None
    if (
        item.last_payment_id == codigo
        and item.last_payment_status == "CONFIRMED"
        and item.status == "ACTIVE"
    ):
        return item

    plan = db.get(SaaSPlan, item.plan_id)
    expected = money(Decimal(str(plan.monthly_price))) if plan else Decimal("0")
    received = money(Decimal(str(valor_recebido)))
    if expected <= 0 or abs(expected - received) > Decimal("0.01"):
        return None

    item.last_payment_status = "CONFIRMED"
    payment = {
        "id": codigo,
        "status": "CONFIRMED",
        "dueDate": item.current_period_start.date().isoformat() if item.current_period_start else None,
        "value": float(received),
    }
    _apply_payment_period(item, payment)
    _record_lss_recurring_accrual(db, item, payment)
    db.flush()
    return item


def maybe_issue_inter_lss_renewal(db: Session, item: SaaSSubscription, plan: SaaSPlan) -> bool:
    """Emite nova cobrança Inter quando o período venceu (substitui recorrência Asaas)."""
    if item.payment_method_reference != LSS_INTER_REF:
        return False
    if item.status not in {"ACTIVE", "PAST_DUE"}:
        return False
    if item.last_payment_status == "PENDING" and item.payment_checkout_url:
        return False
    if not inter_configured():
        return False
    cnpj = (item.asaas_customer_id or "").strip()
    if len(cnpj) != 14:
        return False
    provision_inter_lss_invoice(
        db,
        item,
        plan,
        company_cnpj=cnpj,
        subscriber_email=item.subscriber_email or "financeiro@letter.app.br",
        subscriber_phone=None,
    )
    return True
