"""E-mails transacionais Marketplace — boleto emitido e pagamento confirmado (D+0, mock em dev)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.inter_boleto_service import boleto_public_token
from app.models import CommunicationTemplate, Lead, Proposal, User
from app.tax_communication_service import mock_deliver, queue_delivery


BOLETO_CLIENT_KEY = "MARKETPLACE_BOLETO_CLIENT"
PAYMENT_CLIENT_KEY = "MARKETPLACE_PAYMENT_CLIENT"
PAYMENT_PARTNER_KEY = "MARKETPLACE_PAYMENT_PARTNER"


def _parse_json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _snapshot_email(lead: Lead, terms: dict) -> str:
    detail = _parse_json(lead.scr_detail_json)
    for key in ("chat", "venda_direta_manual", "venda_direta_robo", "cadastro"):
        snap = detail.get(key)
        if isinstance(snap, dict):
            email = str(snap.get("email") or "").strip()
            if email:
                return email
    return str(terms.get("client_email") or "").strip()


def _boleto_link(lead_id: str) -> str:
    token = boleto_public_token(lead_id)
    return f"/api/v1/marketplace/cadastros/{lead_id}/boleto/{token}"


def _ensure_email_template(
    db: Session,
    user: User,
    *,
    key: str,
    subject: str,
    body: str,
) -> CommunicationTemplate:
    item = db.scalar(
        select(CommunicationTemplate).where(
            CommunicationTemplate.organization_id == user.organization_id,
            CommunicationTemplate.key == key,
            CommunicationTemplate.channel == "EMAIL",
            CommunicationTemplate.active.is_(True),
        )
    )
    if item:
        return item
    current = db.scalar(
        select(CommunicationTemplate.version).where(
            CommunicationTemplate.organization_id == user.organization_id,
            CommunicationTemplate.key == key,
            CommunicationTemplate.channel == "EMAIL",
        )
    ) or 0
    item = CommunicationTemplate(
        organization_id=user.organization_id,
        key=key,
        channel="EMAIL",
        version=current + 1,
        subject=subject,
        body=body,
        purpose="TRANSACTIONAL",
        active=True,
    )
    db.add(item)
    db.flush()
    return item


def _queue_and_deliver(
    db: Session,
    actor: User,
    *,
    template: CommunicationTemplate,
    subject_type: str,
    subject_id: str,
    destination: str,
    idempotency_key: str,
    variables: dict[str, Any],
) -> dict | None:
    if not destination or "@" not in destination:
        return None
    try:
        delivery, created = queue_delivery(
            db,
            actor,
            template,
            subject_type=subject_type,
            subject_id=subject_id,
            destination=destination,
            idempotency_key=idempotency_key,
            variables=variables,
        )
        if created:
            mock_deliver(delivery)
        return {
            "key": template.key,
            "destination": delivery.destination_masked,
            "status": delivery.status,
            "created": created,
        }
    except Exception:
        return {"key": template.key, "destination": destination, "status": "FAILED", "created": False}


def dispatch_boleto_issued_notifications(
    db: Session,
    actor: User,
    lead: Lead,
    proposal: Proposal,
    terms: dict,
    *,
    boleto: dict | None = None,
) -> dict:
    """Cliente recebe link do boleto/PIX da entrada (idempotente por proposta)."""
    life = terms.get("lifecycle") if isinstance(terms.get("lifecycle"), dict) else {}
    if life.get("boleto_email_sent_at"):
        return {"trigger_email_automatico": "ALREADY_SENT", "deliveries": []}

    email = _snapshot_email(lead, terms)
    amount = (boleto or {}).get("amount") or terms.get("total_entrada") or ""
    credit = terms.get("total_credit") or str(proposal.requested_amount or "")
    template = _ensure_email_template(
        db,
        actor,
        key=BOLETO_CLIENT_KEY,
        subject="Boleto da entrada — LETTER Marketplace",
        body=(
            "Olá {{client_name}},\n\n"
            "Sua compra de carta contemplada está aguardando o pagamento da entrada.\n"
            "Valor da entrada: R$ {{entrada_amount}}\n"
            "Crédito: R$ {{credit_value}}\n\n"
            "Baixe o boleto (com PIX) em: {{boleto_link}}\n"
            "Ou acesse sua conta em {{portal_hint}}.\n\n"
            "LETTER — {{site_name}}"
        ),
    )
    variables = {
        "client_name": lead.name,
        "entrada_amount": amount,
        "credit_value": credit,
        "boleto_link": _boleto_link(lead.id),
        "portal_hint": settings.company_trade_name,
        "site_name": settings.company_trade_name,
    }
    delivery = _queue_and_deliver(
        db,
        actor,
        template=template,
        subject_type="MARKETPLACE_PROPOSAL",
        subject_id=proposal.id,
        destination=email,
        idempotency_key=f"mkt-boleto-{proposal.id}-client",
        variables=variables,
    )
    deliveries = [d for d in [delivery] if d]
    if deliveries and any(d.get("status") == "DELIVERED" for d in deliveries):
        life["boleto_email_sent_at"] = terms.get("boleto", {}).get("issued_at")
        terms["lifecycle"] = life
        proposal.terms_json = json.dumps(terms, ensure_ascii=False)
        db.flush()
    return {"trigger_email_automatico": "SENT_D+0" if deliveries else "SKIPPED", "deliveries": deliveries}


def dispatch_payment_received_notifications(
    db: Session,
    actor: User,
    lead: Lead,
    proposal: Proposal,
) -> dict:
    """Cliente e parceiro originador recebem confirmação de pagamento (idempotente)."""
    terms = _parse_json(proposal.terms_json)
    life = terms.get("lifecycle") if isinstance(terms.get("lifecycle"), dict) else {}
    if life.get("payment_email_sent_at"):
        return {"trigger_email_automatico": "ALREADY_SENT", "deliveries": []}

    client_email = _snapshot_email(lead, terms)
    partner_id = terms.get("partner_user_id")
    partner = db.get(User, partner_id) if partner_id else None
    amount = terms.get("total_entrada") or ""
    credit = terms.get("total_credit") or str(proposal.requested_amount or "")

    client_tpl = _ensure_email_template(
        db,
        actor,
        key=PAYMENT_CLIENT_KEY,
        subject="Pagamento confirmado — LETTER Marketplace",
        body=(
            "Olá {{client_name}},\n\n"
            "Recebemos o pagamento da entrada da sua compra.\n"
            "Valor: R$ {{entrada_amount}} · Crédito: R$ {{credit_value}}\n\n"
            "Sua venda segue em processamento. Acompanhe em {{portal_hint}}.\n\n"
            "LETTER"
        ),
    )
    partner_tpl = _ensure_email_template(
        db,
        actor,
        key=PAYMENT_PARTNER_KEY,
        subject="Cliente pagou entrada — {{client_name}}",
        body=(
            "Olá {{partner_name}},\n\n"
            "O cliente {{client_name}} confirmou o pagamento da entrada (R$ {{entrada_amount}}).\n"
            "Crédito da operação: R$ {{credit_value}}.\n\n"
            "Cadastro: {{lead_id}}\n"
            "LETTER"
        ),
    )
    base_vars = {
        "client_name": lead.name,
        "entrada_amount": amount,
        "credit_value": credit,
        "portal_hint": settings.company_trade_name,
        "lead_id": lead.id,
    }
    deliveries: list[dict] = []
    client_delivery = _queue_and_deliver(
        db,
        actor,
        template=client_tpl,
        subject_type="MARKETPLACE_PROPOSAL",
        subject_id=proposal.id,
        destination=client_email,
        idempotency_key=f"mkt-pago-{proposal.id}-client",
        variables=base_vars,
    )
    if client_delivery:
        deliveries.append(client_delivery)
    if partner and partner.email:
        partner_delivery = _queue_and_deliver(
            db,
            actor,
            template=partner_tpl,
            subject_type="MARKETPLACE_PROPOSAL",
            subject_id=proposal.id,
            destination=partner.email.strip().lower(),
            idempotency_key=f"mkt-pago-{proposal.id}-partner-{partner.id}",
            variables={**base_vars, "partner_name": partner.name},
        )
        if partner_delivery:
            deliveries.append(partner_delivery)

    if deliveries and any(d.get("status") == "DELIVERED" for d in deliveries):
        life["payment_email_sent_at"] = life.get("paid_at")
        terms["lifecycle"] = life
        proposal.terms_json = json.dumps(terms, ensure_ascii=False)
        db.flush()
    return {"trigger_email_automatico": "SENT_D+0" if deliveries else "SKIPPED", "deliveries": deliveries}
