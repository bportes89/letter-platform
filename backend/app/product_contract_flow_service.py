"""Quando emitir contrato e quando disparar ZapSign por produto (regra comercial LETTER)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import FlashSolicitation, Lead, Proposal, QuitConOperacao, SdcSolicitation, User
from app.marketplace_zapsign_service import ensure_marketplace_zapsign

POLICY_MARKETPLACE = "MARKETPLACE_COMPRA_ENTRADA_ZAPSIGN"
POLICY_SDC_CAP_GIRO = "SDC_VENDA_CAP_GIRO_ZAPSIGN"
POLICY_TAPAF_THEN_ZAPSIGN = "TAPAF_EMITIDO_PAGO_ZAPSIGN"


def _parse_json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _save_terms(proposal: Proposal, terms: dict) -> None:
    proposal.terms_json = json.dumps(terms, ensure_ascii=False)


def _dispatch_meta(terms: dict) -> dict:
    block = terms.get("contract_dispatch")
    return block if isinstance(block, dict) else {}


def _set_dispatch(terms: dict, **fields) -> None:
    block = _dispatch_meta(terms)
    block.update(fields)
    terms["contract_dispatch"] = block


def _mark_zapsign_dispatched(proposal: Proposal) -> None:
    """Atualiza contract_dispatch sem sobrescrever o bloco zapsign gravado por ensure_*."""
    terms = _parse_json(proposal.terms_json)
    _set_dispatch(terms, zapsign_sent_at=datetime.now(UTC).isoformat())
    _save_terms(proposal, terms)


def build_desk_contract_html(product: str, context: dict) -> str:
    nome = str(context.get("contact_name") or "—")
    doc = str(context.get("document") or "—")
    prod_label = {
        "SDC": "SDC — Capital de Giro",
        "FLASH": "Flash Capital",
        "QUITCON": "QuitCon",
    }.get(product.upper(), product)
    valor = str(context.get("amount_label") or context.get("credit") or "—")
    bem = str(context.get("asset_label") or "—")
    return (
        f'<div class="letter-contract-body"><p><strong>LETTER BANK LTDA</strong> — Contrato {prod_label}</p>'
        f"<p><strong>Contratante:</strong> {nome}<br/><strong>Documento:</strong> {doc}</p>"
        f"<p><strong>Objeto:</strong> {bem}<br/><strong>Valor de referência:</strong> {valor}</p>"
        "<p>Este documento complementa a taxa TAPAF e a esteira operacional LETTER. "
        "A assinatura eletrônica via ZapSign será solicitada após a confirmação do pagamento TAPAF, "
        "exceto no fluxo SDC Capital de Giro (envio na etapa de venda).</p>"
        f"<p>Emitido em {datetime.now(UTC).strftime('%d/%m/%Y %H:%M')} UTC.</p></div>"
    )


def emit_desk_contract_on_tapaf(
    db: Session,
    proposal: Proposal,
    *,
    product: str,
    context: dict,
) -> dict:
    """Flash / QuitCon / SDC (TAPAF): contrato junto com abertura TAPAF; ZapSign só após liquidação."""
    terms = _parse_json(proposal.terms_json)
    html = build_desk_contract_html(product, context)
    terms["desk_contract_html"] = html
    terms["contract_html"] = html
    _set_dispatch(
        terms,
        policy=POLICY_TAPAF_THEN_ZAPSIGN,
        product=product.upper(),
        contract_emitted_at=datetime.now(UTC).isoformat(),
        zapsign_trigger="AFTER_TAPAF_PAID",
        zapsign_sent_at=terms.get("contract_dispatch", {}).get("zapsign_sent_at"),
    )
    _save_terms(proposal, terms)
    db.flush()
    return {"html": html, "policy": POLICY_TAPAF_THEN_ZAPSIGN}


def emit_sdc_cap_giro_contract_and_zapsign(
    db: Session,
    user: User,
    item: SdcSolicitation,
    proposal: Proposal,
    lead: Lead | None,
) -> dict | None:
    """SDC: na etapa Venda Cap Giro — emite contrato e envia ZapSign."""
    terms = _parse_json(proposal.terms_json)
    html = build_desk_contract_html(
        "SDC",
        {
            "contact_name": item.contact_name,
            "document": item.document,
            "amount_label": f"R$ {item.credit_estimated}",
            "asset_label": item.asset_type,
        },
    )
    terms["desk_contract_html"] = html
    terms["contract_html"] = html
    ack = {
        "accepted_at": datetime.now(UTC).isoformat(),
        "channel": "SDC_DESK_CAP_GIRO",
        "provider": "SDC_SALE_STEP",
    }
    terms["contract_ack"] = ack
    _set_dispatch(
        terms,
        policy=POLICY_SDC_CAP_GIRO,
        product="SDC",
        contract_emitted_at=datetime.now(UTC).isoformat(),
        zapsign_trigger="ON_CAP_GIRO_SALE",
    )
    _save_terms(proposal, terms)
    db.flush()
    if not lead:
        lead = db.get(Lead, proposal.lead_id) if proposal.lead_id else None
    if not lead:
        return None
    signer_email = (item.contact_email or "").strip().lower()
    block = ensure_marketplace_zapsign(
        db,
        lead=lead,
        proposal=proposal,
        html=html,
        ack=ack,
        signer_email=signer_email,
        signer_name=item.contact_name,
    )
    if block and block.get("status") == "SENT":
        _mark_zapsign_dispatched(proposal)
        db.flush()
    return block


def mark_marketplace_contract_at_purchase(terms: dict) -> None:
    ack = terms.get("contract_ack") if isinstance(terms.get("contract_ack"), dict) else {}
    _set_dispatch(
        terms,
        policy=POLICY_MARKETPLACE,
        product="MARKETPLACE",
        contract_emitted_at=ack.get("accepted_at"),
        zapsign_trigger="AFTER_ENTRADA_PAID",
    )


def send_marketplace_zapsign_after_entrada_paid(
    db: Session,
    lead: Lead,
    proposal: Proposal,
) -> dict | None:
    if proposal.product != "MARKETPLACE":
        return None
    terms = _parse_json(proposal.terms_json)
    from app.cadastro_service import _snapshot_from_lead
    from app.marketplace_contract_docs_service import site_contract_meta

    snap = _snapshot_from_lead(lead)
    meta = site_contract_meta(terms, snap)
    if not meta.get("has_site_contract"):
        return None
    html = str(terms.get("contract_html") or snap.get("contract_html") or "").strip()
    ack = meta.get("contract_ack") if isinstance(meta.get("contract_ack"), dict) else {}
    if html and html != str(terms.get("contract_html") or "").strip():
        terms["contract_html"] = html
        terms["contract_ack"] = ack
        _save_terms(proposal, terms)
        db.flush()
    dispatch = _dispatch_meta(terms)
    if dispatch.get("zapsign_sent_at"):
        return None
    email = str(
        snap.get("email") or terms.get("client_email") or lead.email or ""
    ).strip().lower()
    block = ensure_marketplace_zapsign(
        db,
        lead=lead,
        proposal=proposal,
        html=html,
        ack=ack,
        signer_email=email,
        signer_name=lead.name,
    )
    if block and block.get("status") == "SENT":
        _mark_zapsign_dispatched(proposal)
        db.flush()
    return block


def send_zapsign_after_tapaf_paid(db: Session, proposal: Proposal) -> dict | None:
    terms = _parse_json(proposal.terms_json)
    dispatch = _dispatch_meta(terms)
    if dispatch.get("zapsign_sent_at"):
        return None
    if dispatch.get("policy") != POLICY_TAPAF_THEN_ZAPSIGN:
        return None
    html = str(terms.get("desk_contract_html") or terms.get("contract_html") or "").strip()
    if not html:
        return None
    lead = db.get(Lead, proposal.lead_id) if proposal.lead_id else None
    if not lead:
        return None
    ack = {
        "accepted_at": datetime.now(UTC).isoformat(),
        "channel": "DESK_TAPAF_PAID",
        "provider": "TAPAF_PAYMENT",
    }
    terms["contract_ack"] = ack
    _save_terms(proposal, terms)
    email = (lead.email or "").strip().lower()
    if not email and isinstance(terms.get("contact_email"), str):
        email = terms["contact_email"].strip().lower()
    block = ensure_marketplace_zapsign(
        db,
        lead=lead,
        proposal=proposal,
        html=html,
        ack=ack,
        signer_email=email or f"cliente+{lead.id[:8]}@letter.local",
        signer_name=lead.name,
    )
    if block and block.get("status") == "SENT":
        _mark_zapsign_dispatched(proposal)
        db.flush()
    return block


def send_quitcon_zapsign_after_tapaf(db: Session, operacao: QuitConOperacao) -> dict | None:
    proposal = db.get(Proposal, operacao.proposal_id)
    if not proposal:
        return None
    return send_zapsign_after_tapaf_paid(db, proposal)


def flash_context_from_solicitation(item: FlashSolicitation) -> dict:
    return {
        "contact_name": item.contact_name,
        "document": item.document,
        "amount_label": f"R$ {item.principal}",
        "asset_label": f"{item.asset_category} — {item.asset_type}",
    }


def sdc_tapaf_context(item: SdcSolicitation) -> dict:
    return {
        "contact_name": item.contact_name,
        "document": item.document,
        "amount_label": f"R$ {item.credit_estimated}",
        "asset_label": item.asset_type,
    }
