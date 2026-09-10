"""Webhook Banco Inter — RECEBIDO → situação PAGO no Cadastro Marketplace."""

from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cadastro_service import SIT_AGUARDANDO, SIT_PAGO, apply_situation_transition, seed_marketplace_lifecycle
from app.models import Lead, Proposal, Role, User
from app.services import money

logger = logging.getLogger(__name__)


def _parse_json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _normalize_items(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        if "codigoSolicitacao" in payload or "situacao" in payload:
            return [payload]
        nested = payload.get("data") or payload.get("items") or payload.get("cobrancas")
        if isinstance(nested, list):
            return [x for x in nested if isinstance(x, dict)]
    return []


def _org_actor(db: Session, organization_id: str) -> User | None:
    admin = db.scalar(
        select(User).where(
            User.organization_id == organization_id,
            User.role == Role.PLATFORM_ADMIN,
            User.active.is_(True),
        )
    )
    if admin:
        return admin
    return db.scalar(
        select(User).where(
            User.organization_id == organization_id,
            User.active.is_(True),
        )
    )


def _amount_close(expected: Decimal, received: Decimal) -> bool:
    return abs(expected - received) <= Decimal("0.01")


def find_proposal_by_boleto_codigo(db: Session, codigo: str) -> Proposal | None:
    # SQLite/Postgres: varre propostas MARKETPLACE recentes (MVP sem índice dedicado)
    proposals = list(
        db.scalars(
            select(Proposal)
            .where(Proposal.product == "MARKETPLACE")
            .order_by(Proposal.created_at.desc())
            .limit(500)
        )
    )
    for proposal in proposals:
        terms = _parse_json(proposal.terms_json)
        boleto = terms.get("boleto") if isinstance(terms.get("boleto"), dict) else None
        if boleto and str(boleto.get("codigo_solicitacao") or "") == codigo:
            return proposal
    return None


def apply_inter_payment_received(
    db: Session,
    *,
    codigo_solicitacao: str,
    valor_recebido: Decimal | str | float,
    seu_numero: str | None = None,
    data_hora: str | None = None,
) -> dict:
    codigo = str(codigo_solicitacao or "").strip()
    if not codigo:
        return {"processed": False, "reason": "codigo_vazio"}

    try:
        received = money(Decimal(str(valor_recebido)))
    except (InvalidOperation, ValueError):
        return {"processed": False, "reason": "valor_invalido"}

    proposal = find_proposal_by_boleto_codigo(db, codigo)
    if not proposal:
        return {"processed": False, "reason": "proposta_nao_encontrada", "codigo_solicitacao": codigo}

    terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json))
    boleto = terms.get("boleto") if isinstance(terms.get("boleto"), dict) else {}
    expected = money(Decimal(str(boleto.get("amount") or terms.get("total_entrada") or 0)))
    if expected <= 0 or not _amount_close(expected, received):
        return {
            "processed": False,
            "reason": "valor_divergente",
            "expected": str(expected),
            "received": str(received),
            "proposal_id": proposal.id,
        }

    life = terms.get("lifecycle") if isinstance(terms.get("lifecycle"), dict) else {}
    situation = str(life.get("situation") or SIT_AGUARDANDO).upper()
    if situation == SIT_PAGO or situation in {"CONCLUIDO", "CONCLUIDA"}:
        return {
            "processed": False,
            "reason": "ja_pago_ou_concluido",
            "situation": situation,
            "proposal_id": proposal.id,
            "idempotent": True,
        }
    if situation != SIT_AGUARDANDO:
        return {
            "processed": False,
            "reason": "situacao_invalida",
            "situation": situation,
            "proposal_id": proposal.id,
        }

    lead = db.get(Lead, proposal.lead_id) if proposal.lead_id else None
    if not lead:
        return {"processed": False, "reason": "lead_ausente", "proposal_id": proposal.id}

    actor = _org_actor(db, proposal.organization_id)
    if not actor:
        return {"processed": False, "reason": "sem_ator", "proposal_id": proposal.id}

    # anota recebimento no boleto antes da transição
    boleto = dict(boleto)
    boleto["paid_at"] = data_hora or None
    boleto["valor_recebido"] = str(received)
    if seu_numero:
        boleto["seu_numero_webhook"] = seu_numero
    terms["boleto"] = boleto
    proposal.terms_json = json.dumps(terms, ensure_ascii=False)
    db.flush()

    apply_situation_transition(db, actor, lead, proposal, SIT_PAGO)
    return {
        "processed": True,
        "proposal_id": proposal.id,
        "lead_id": lead.id,
        "situation": SIT_PAGO,
        "codigo_solicitacao": codigo,
        "amount": str(received),
    }


def handle_inter_webhook(db: Session, payload: object) -> dict:
    items = _normalize_items(payload)
    stats = {"total": len(items), "paid": 0, "skipped": 0, "results": []}
    for item in items:
        situacao = str(item.get("situacao") or "").upper()
        codigo = str(item.get("codigoSolicitacao") or item.get("codigo_solicitacao") or "").strip()
        seu_numero = str(item.get("seuNumero") or item.get("seu_numero") or "").strip()
        valor = item.get("valorTotalRecebido")
        if valor is None:
            valor = item.get("valor_recebido") or item.get("valor")
        data_hora = item.get("dataHoraSituacao") or item.get("data_hora")

        if situacao != "RECEBIDO" or not codigo:
            stats["skipped"] += 1
            stats["results"].append(
                {
                    "processed": False,
                    "reason": "ignorado",
                    "situacao": situacao,
                    "codigo_solicitacao": codigo or None,
                }
            )
            continue

        result = apply_inter_payment_received(
            db,
            codigo_solicitacao=codigo,
            valor_recebido=valor or 0,
            seu_numero=seu_numero or None,
            data_hora=str(data_hora) if data_hora else None,
        )
        if result.get("processed"):
            stats["paid"] += 1
        else:
            stats["skipped"] += 1
        stats["results"].append(result)
        logger.info("[InterWebhook] item resultado=%s", result)
    return stats
