"""E-mails transacionais Marketplace — boleto emitido e pagamento confirmado (D+0, mock em dev)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.inter_boleto_service import boleto_public_token
from app.models import CommunicationTemplate, Lead, Proposal, Quota, User
from app.tax_communication_service import deliver_communication, queue_delivery


from app.marketplace_cms_email_service import (
    MARKETPLACE_BOLETO_CLIENT as BOLETO_CLIENT_KEY,
    MARKETPLACE_CONCLUDE_CLIENT,
    MARKETPLACE_CONCLUDE_PARTNER,
    MARKETPLACE_CONCLUDE_PLATFORM,
    MARKETPLACE_CONCLUDE_SUPPLIER,
    MARKETPLACE_DOCUMENT_CLIENT,
    MARKETPLACE_PAYMENT_CLIENT as PAYMENT_CLIENT_KEY,
    MARKETPLACE_PAYMENT_PARTNER as PAYMENT_PARTNER_KEY,
    MARKETPLACE_WELCOME_CLIENT,
    resolve_marketplace_email_template,
)
from app.quota_supplier_service import normalize_supplier_key, suppliers_index


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


def _proposal_for_lead(db: Session, lead: Lead) -> Proposal | None:
    return db.scalar(
        select(Proposal).where(
            Proposal.lead_id == lead.id,
            Proposal.organization_id == lead.organization_id,
            Proposal.product == "MARKETPLACE",
        ).order_by(Proposal.created_at.desc())
    )


def _base_sale_variables(lead: Lead, proposal: Proposal, terms: dict) -> dict[str, Any]:
    return {
        "client_name": lead.name,
        "client_email": _snapshot_email(lead, terms),
        "entrada_amount": terms.get("total_entrada") or "",
        "credit_value": terms.get("total_credit") or str(proposal.requested_amount or ""),
        "portal_hint": settings.company_trade_name,
        "site_name": settings.company_trade_name,
        "site_domain": settings.public_app_url or "",
        "portal_link": settings.public_app_url or "/login",
        "lead_id": lead.id,
        "purchase_date": (
            (terms.get("lifecycle") or {}).get("paid_at")
            if isinstance(terms.get("lifecycle"), dict)
            else ""
        )
        or "",
        "installments": "",
        "administrator_name": "",
        "supplier_name": "",
    }


def _supplier_contacts(db: Session, organization_id: str, terms: dict) -> list[tuple[str, str]]:
    quota_ids = [str(x) for x in (terms.get("quota_ids") or [])]
    if not quota_ids:
        for row in terms.get("quotas") or []:
            if isinstance(row, dict) and row.get("quota_id"):
                quota_ids.append(str(row["quota_id"]))
    if not quota_ids:
        return []
    quotas = list(db.scalars(select(Quota).where(Quota.id.in_(quota_ids))))
    suppliers = suppliers_index(db, organization_id)
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for quota in quotas:
        key = normalize_supplier_key(quota.supplier_source or "")
        if not key or key in seen:
            continue
        seen.add(key)
        supplier = suppliers.get(key)
        if supplier and supplier.email:
            out.append((supplier.name, supplier.email.strip().lower()))
    return out


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
        item.subject = subject
        item.body = body
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
            deliver_communication(delivery, destination, template.subject, template.channel)
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
    boleto_subject, boleto_body = resolve_marketplace_email_template(
        db,
        actor.organization_id,
        BOLETO_CLIENT_KEY,
        default_subject="Boleto da entrada — LETTER Marketplace",
        default_body=(
            "Olá {{client_name}},\n\n"
            "Sua compra de carta contemplada está aguardando o pagamento da entrada.\n"
            "Valor da entrada: R$ {{entrada_amount}}\n"
            "Crédito: R$ {{credit_value}}\n\n"
            "Baixe o boleto (com PIX) em: {{boleto_link}}\n"
            "Ou acesse sua conta em {{portal_hint}}.\n\n"
            "LETTER — {{site_name}}"
        ),
    )
    template = _ensure_email_template(
        db,
        actor,
        key=BOLETO_CLIENT_KEY,
        subject=boleto_subject,
        body=boleto_body,
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

    pay_client_subject, pay_client_body = resolve_marketplace_email_template(
        db,
        actor.organization_id,
        PAYMENT_CLIENT_KEY,
        default_subject="Pagamento confirmado — LETTER Marketplace",
        default_body=(
            "Olá {{client_name}},\n\n"
            "Recebemos o pagamento da entrada da sua compra.\n"
            "Valor: R$ {{entrada_amount}} · Crédito: R$ {{credit_value}}\n\n"
            "Sua venda segue em processamento. Acompanhe em {{portal_hint}}.\n\n"
            "LETTER"
        ),
    )
    pay_partner_subject, pay_partner_body = resolve_marketplace_email_template(
        db,
        actor.organization_id,
        PAYMENT_PARTNER_KEY,
        default_subject="Cliente pagou entrada — {{client_name}}",
        default_body=(
            "Olá {{partner_name}},\n\n"
            "O cliente {{client_name}} confirmou o pagamento da entrada (R$ {{entrada_amount}}).\n"
            "Crédito da operação: R$ {{credit_value}}.\n\n"
            "Cadastro: {{lead_id}}\n"
            "LETTER"
        ),
    )
    client_tpl = _ensure_email_template(
        db,
        actor,
        key=PAYMENT_CLIENT_KEY,
        subject=pay_client_subject,
        body=pay_client_body,
    )
    partner_tpl = _ensure_email_template(
        db,
        actor,
        key=PAYMENT_PARTNER_KEY,
        subject=pay_partner_subject,
        body=pay_partner_body,
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


def dispatch_marketplace_welcome_notification(
    db: Session,
    actor: User,
    lead: Lead,
    *,
    client_password: str | None = None,
) -> dict:
    """Conta criada no fluxo marketplace (legado texts id 1017)."""
    proposal = _proposal_for_lead(db, lead)
    if not proposal:
        return {"trigger_email_automatico": "SKIPPED", "deliveries": []}
    terms = _parse_json(proposal.terms_json)
    life = terms.get("lifecycle") if isinstance(terms.get("lifecycle"), dict) else {}
    if life.get("welcome_email_sent_at"):
        return {"trigger_email_automatico": "ALREADY_SENT", "deliveries": []}

    subject, body = resolve_marketplace_email_template(
        db,
        actor.organization_id,
        MARKETPLACE_WELCOME_CLIENT,
        default_subject="Bem-vindo — LETTER Marketplace",
        default_body=(
            "Olá {{client_name}},\n\n"
            "Sua conta no escritório virtual LETTER foi criada.\n"
            "E-mail: {{client_email}}\n"
            "Senha: {{client_password}}\n\n"
            "Acesse: {{portal_link}}\n\n"
            "{{site_name}}"
        ),
    )
    template = _ensure_email_template(db, actor, key=MARKETPLACE_WELCOME_CLIENT, subject=subject, body=body)
    variables = {
        **_base_sale_variables(lead, proposal, terms),
        "client_password": client_password or "(definida por você no cadastro)",
    }
    delivery = _queue_and_deliver(
        db,
        actor,
        template=template,
        subject_type="MARKETPLACE_PROPOSAL",
        subject_id=proposal.id,
        destination=variables["client_email"],
        idempotency_key=f"mkt-welcome-{proposal.id}",
        variables=variables,
    )
    deliveries = [d for d in [delivery] if d]
    if deliveries and any(d.get("status") == "DELIVERED" for d in deliveries):
        life["welcome_email_sent_at"] = life.get("welcome_email_sent_at") or "1"
        terms["lifecycle"] = life
        proposal.terms_json = json.dumps(terms, ensure_ascii=False)
        db.flush()
    return {"trigger_email_automatico": "SENT_D+0" if deliveries else "SKIPPED", "deliveries": deliveries}


def dispatch_marketplace_document_uploaded_notification(
    db: Session,
    actor: User,
    lead: Lead,
    *,
    document_id: str,
    document_kind: str,
) -> dict:
    """Cliente enviou documento no escritório (legado texts id 1009)."""
    proposal = _proposal_for_lead(db, lead)
    if not proposal:
        return {"trigger_email_automatico": "SKIPPED", "deliveries": []}
    terms = _parse_json(proposal.terms_json)
    subject, body = resolve_marketplace_email_template(
        db,
        actor.organization_id,
        MARKETPLACE_DOCUMENT_CLIENT,
        default_subject="Documento recebido — LETTER",
        default_body=(
            "Olá {{client_name}},\n\n"
            "Recebemos o documento {{document_name}} da sua compra.\n"
            "Crédito: R$ {{credit_value}}\n\n"
            "Acompanhe em {{portal_link}}.\n\n"
            "{{site_name}}"
        ),
    )
    template = _ensure_email_template(db, actor, key=MARKETPLACE_DOCUMENT_CLIENT, subject=subject, body=body)
    variables = {
        **_base_sale_variables(lead, proposal, terms),
        "document_name": document_kind.replace("_", " ").title(),
    }
    delivery = _queue_and_deliver(
        db,
        actor,
        template=template,
        subject_type="MARKETPLACE_DOCUMENT",
        subject_id=document_id,
        destination=variables["client_email"],
        idempotency_key=f"mkt-doc-{document_id}-client",
        variables=variables,
    )
    deliveries = [d for d in [delivery] if d]
    return {"trigger_email_automatico": "SENT_D+0" if deliveries else "SKIPPED", "deliveries": deliveries}


def dispatch_marketplace_concluded_notifications(
    db: Session,
    actor: User,
    lead: Lead,
    proposal: Proposal,
) -> dict:
    """Venda concluída — cliente, fornecedor, parceiro e plataforma (legado 1013–1016)."""
    terms = _parse_json(proposal.terms_json)
    life = terms.get("lifecycle") if isinstance(terms.get("lifecycle"), dict) else {}
    if life.get("conclude_email_sent_at"):
        return {"trigger_email_automatico": "ALREADY_SENT", "deliveries": []}

    base_vars = _base_sale_variables(lead, proposal, terms)
    partner_id = terms.get("partner_user_id")
    partner = db.get(User, partner_id) if partner_id else None
    platform_dest = (settings.company_email or "comercial@letter.app.br").strip().lower()

    specs: list[tuple[str, str, str, str]] = [
        (
            MARKETPLACE_CONCLUDE_CLIENT,
            "Processo concluído — LETTER",
            "Olá {{client_name}},\n\nSua compra foi concluída com sucesso.\nCrédito: R$ {{credit_value}}\n\n{{site_name}}",
            base_vars["client_email"],
        ),
        (
            MARKETPLACE_CONCLUDE_PARTNER,
            "Venda concluída — {{client_name}}",
            "Olá {{partner_name}},\n\nA venda do cliente {{client_name}} foi concluída.\nCrédito: R$ {{credit_value}}\n\nLETTER",
            partner.email.strip().lower() if partner and partner.email else "",
        ),
        (
            MARKETPLACE_CONCLUDE_PLATFORM,
            "Venda marketplace concluída — {{client_name}}",
            "Cadastro {{lead_id}} concluído.\nCliente: {{client_name}}\nCrédito: R$ {{credit_value}}",
            platform_dest,
        ),
    ]
    deliveries: list[dict] = []
    for comm_key, default_subject, default_body, dest in specs:
        if not dest:
            continue
        subject, body = resolve_marketplace_email_template(
            db, actor.organization_id, comm_key, default_subject=default_subject, default_body=default_body
        )
        template = _ensure_email_template(db, actor, key=comm_key, subject=subject, body=body)
        vars_ = dict(base_vars)
        if comm_key == MARKETPLACE_CONCLUDE_PARTNER and partner:
            vars_["partner_name"] = partner.name
        delivery = _queue_and_deliver(
            db,
            actor,
            template=template,
            subject_type="MARKETPLACE_PROPOSAL",
            subject_id=proposal.id,
            destination=dest,
            idempotency_key=f"mkt-conclude-{proposal.id}-{comm_key}",
            variables=vars_,
        )
        if delivery:
            deliveries.append(delivery)

    supplier_subject, supplier_body = resolve_marketplace_email_template(
        db,
        actor.organization_id,
        MARKETPLACE_CONCLUDE_SUPPLIER,
        default_subject="Transferência concluída — {{client_name}}",
        default_body=(
            "Olá {{supplier_name}},\n\n"
            "A venda vinculada ao fornecedor foi concluída.\n"
            "Cliente: {{client_name}} · Crédito: R$ {{credit_value}}\n\n"
            "LETTER"
        ),
    )
    supplier_tpl = _ensure_email_template(
        db, actor, key=MARKETPLACE_CONCLUDE_SUPPLIER, subject=supplier_subject, body=supplier_body
    )
    for supplier_name, supplier_email in _supplier_contacts(db, actor.organization_id, terms):
        delivery = _queue_and_deliver(
            db,
            actor,
            template=supplier_tpl,
            subject_type="MARKETPLACE_PROPOSAL",
            subject_id=proposal.id,
            destination=supplier_email,
            idempotency_key=f"mkt-conclude-{proposal.id}-supplier-{supplier_email}",
            variables={**base_vars, "supplier_name": supplier_name},
        )
        if delivery:
            deliveries.append(delivery)

    if deliveries and any(d.get("status") == "DELIVERED" for d in deliveries):
        life["conclude_email_sent_at"] = life.get("commission_released_at")
        terms["lifecycle"] = life
        proposal.terms_json = json.dumps(terms, ensure_ascii=False)
        db.flush()
    return {"trigger_email_automatico": "SENT_D+0" if deliveries else "SKIPPED", "deliveries": deliveries}
