"""TAPAF desk (QuitCon, Lease Equity) via Banco Inter — cobrança + webhook."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.inter_common import inter_configured
from app.inter_cobranca_helpers import issue_inter_charge, pagador_from_pj, pagador_from_user
from app.models import LeaseEquityPauta, QuitConOperacao, User
from app.services import money

TAPAF_INTER_KEY = "tapaf_inter_billing"


def _boleto_token(scope: str, entity_id: str) -> str:
    digest = hmac.new(
        settings.secret_key.encode("utf-8"),
        f"tapaf-boleto-{scope}-{entity_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def verify_tapaf_boleto_token(scope: str, entity_id: str, token: str) -> bool:
    return hmac.compare_digest(_boleto_token(scope, entity_id), (token or "").strip())


def _public_boleto_url(scope: str, entity_id: str) -> str | None:
    public = (settings.api_public_url or "").rstrip("/")
    if not public:
        return None
    tok = _boleto_token(scope, entity_id)
    if scope == "quitcon":
        return f"{public}/finops/quitcon/tapaf-boleto/{entity_id}/{tok}"
    if scope == "lease-equity":
        return f"{public}/finops/lease-equity/tapaf-boleto/{entity_id}/{tok}"
    return None


def issue_tapaf_inter(
    *,
    user: User,
    amount: Decimal,
    entity_id: str,
    scope: str,
    mensagem: list[str],
    pagador: dict | None = None,
) -> dict:
    if not inter_configured():
        raise HTTPException(status_code=503, detail="Banco Inter não configurado")
    prefix = "Q" if scope == "quitcon" else "E"
    seu = f"{entity_id.replace('-', '')[:11]}{prefix}"[:15]
    issued = issue_inter_charge(
        user=user if not pagador else None,
        pagador=pagador,
        amount=amount,
        seu_numero=seu,
        mensagem_linhas=mensagem,
        pdf_filename_prefix=f"TAPAF_{scope}_{entity_id[:8]}",
    )
    checkout_url = _public_boleto_url(scope, entity_id)
    return {
        "checkout_mode": "INTER",
        "codigo_solicitacao": issued["codigo_solicitacao"],
        "seu_numero": issued.get("seu_numero"),
        "amount": str(money(amount)),
        "payment_checkout_url": checkout_url,
        "pix_copy_paste": issued.get("pix_copy_paste") or checkout_url,
        "gateway_baas_pix_qrcode": issued.get("pix_copy_paste") or checkout_url,
    }


def _load_inter_block(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    block = data.get(TAPAF_INTER_KEY) if isinstance(data, dict) else None
    return block if isinstance(block, dict) else {}


def save_quitcon_inter_block(operacao: QuitConOperacao, block: dict) -> None:
    snap = json.loads(operacao.product_snapshot_json or "{}")
    if not isinstance(snap, dict):
        snap = {}
    snap[TAPAF_INTER_KEY] = block
    operacao.product_snapshot_json = json.dumps(snap, ensure_ascii=False)


def quitcon_inter_block(operacao: QuitConOperacao) -> dict:
    return _load_inter_block(operacao.product_snapshot_json)


def save_lease_inter_block(pauta: LeaseEquityPauta, block: dict) -> None:
    snap = json.loads(pauta.tokenization_json or "{}")
    if not isinstance(snap, dict):
        snap = {}
    snap[TAPAF_INTER_KEY] = block
    pauta.tokenization_json = json.dumps(snap, ensure_ascii=False)


def lease_inter_block(pauta: LeaseEquityPauta) -> dict:
    return _load_inter_block(pauta.tokenization_json)


def read_tapaf_boleto_pdf(scope: str, entity_id: str, token: str, codigo: str) -> tuple[bytes, str]:
    if not verify_tapaf_boleto_token(scope, entity_id, token):
        raise HTTPException(status_code=403, detail="Token de boleto TAPAF inválido")
    if not codigo or not inter_configured():
        raise HTTPException(status_code=404, detail="PDF TAPAF indisponível")
    from app.inter_client import InterClient

    client = InterClient()
    pdf_b64 = client.download_pdf_base64(codigo)
    return base64.b64decode(pdf_b64), f"tapaf-{entity_id[:8]}.pdf"


def find_quitcon_by_inter_codigo(db: Session, codigo: str) -> QuitConOperacao | None:
    rows = list(
        db.scalars(
            select(QuitConOperacao).order_by(QuitConOperacao.created_at.desc()).limit(300)
        )
    )
    for row in rows:
        block = quitcon_inter_block(row)
        if str(block.get("codigo_solicitacao") or "") == codigo:
            return row
    return None


def find_lease_by_inter_codigo(db: Session, codigo: str) -> LeaseEquityPauta | None:
    rows = list(
        db.scalars(
            select(LeaseEquityPauta).order_by(LeaseEquityPauta.created_at.desc()).limit(300)
        )
    )
    for row in rows:
        block = lease_inter_block(row)
        if str(block.get("codigo_solicitacao") or "") == codigo:
            return row
    return None
