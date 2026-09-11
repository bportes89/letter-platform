"""Emissão de boleto Marketplace (Inter real ou MOCK) persistido em proposal.terms_json."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cadastro_service import SIT_AGUARDANDO, SIT_CANCELADO, SIT_CANCELADO_FALTA, seed_marketplace_lifecycle
from app.core.config import settings
from app.inter_common import inter_configured, inter_vencimento_dias
from app.models import Lead, Proposal, Quota, User
from app.network_visibility import get_lead_for_user
from app.services import money


def _parse_json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _digits(value: str | None) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def seu_numero_for_proposal(proposal_id: str, suffix: str = "P") -> str:
    compact = proposal_id.replace("-", "")[:12]
    return f"{compact}-{suffix}"[:15]


def boleto_public_token(lead_id: str) -> str:
    digest = hmac.new(
        settings.secret_key.encode("utf-8"),
        f"boleto-{lead_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def verify_boleto_public_token(lead_id: str, token: str) -> bool:
    expected = boleto_public_token(lead_id)
    return hmac.compare_digest(expected, (token or "").strip())


def resolve_entrada_amount(terms: dict, snap: dict | None = None) -> Decimal:
    snap = snap or {}
    for key in ("total_entrada", "total_entrada_base"):
        raw = terms.get(key)
        if raw not in (None, ""):
            try:
                return money(Decimal(str(raw)))
            except (InvalidOperation, ValueError):
                pass
    pricing = snap.get("pricing") if isinstance(snap.get("pricing"), dict) else {}
    raw = pricing.get("entrada_final")
    if raw not in (None, ""):
        try:
            return money(Decimal(str(raw)))
        except (InvalidOperation, ValueError):
            pass
    total = Decimal("0")
    for row in terms.get("quotas") or []:
        if not isinstance(row, dict):
            continue
        raw = row.get("entrada_final") or row.get("entrada")
        if raw not in (None, ""):
            total += Decimal(str(raw))
    if total > 0:
        return money(total)
    return Decimal("0.00")


def _snapshot_from_lead(lead: Lead) -> dict:
    detail = _parse_json(lead.scr_detail_json)
    for key in ("venda_direta_manual", "venda_direta_robo", "chat", "cadastro"):
        snap = detail.get(key)
        if isinstance(snap, dict) and snap:
            return snap
    return {}


def _marketplace_proposal(db: Session, lead: Lead) -> Proposal | None:
    return db.scalar(
        select(Proposal)
        .where(
            Proposal.lead_id == lead.id,
            Proposal.organization_id == lead.organization_id,
            Proposal.product == "MARKETPLACE",
        )
        .order_by(Proposal.created_at.desc())
    )


def _pagador_from_lead(lead: Lead, terms: dict, snap: dict) -> dict:
    person = str(snap.get("person_type") or terms.get("person_type") or "PF").upper()
    doc = _digits(lead.document or snap.get("document") or "")
    address = snap.get("address") if isinstance(snap.get("address"), dict) else {}
    email = str(snap.get("email") or terms.get("client_email") or "").strip() or "noreply@letter.app.br"
    phone = _digits(lead.phone)
    ddd = phone[:2] if len(phone) >= 10 else "11"
    tel = phone[2:] if len(phone) >= 10 else (phone or "999999999")
    nome = lead.name
    if person == "PJ":
        nome = str(snap.get("razao_social") or lead.name)
    tipo = "JURIDICA" if person == "PJ" else "FISICA"
    if person == "PJ" and len(doc) != 14:
        doc = doc.zfill(14)[:14] if doc else "00000000000191"
    if person != "PJ" and len(doc) != 11:
        doc = doc.zfill(11)[:11] if doc else "00000000000"
    return {
        "cpfCnpj": doc,
        "tipoPessoa": tipo,
        "nome": nome[:100],
        "email": email[:80],
        "ddd": ddd,
        "telefone": tel[:9],
        "cep": _digits(address.get("zipcode"))[:8] or "29090130",
        "numero": str(address.get("number") or "0")[:10],
        "complemento": str(address.get("complement") or "")[:30],
        "bairro": str(address.get("neighborhood") or "Centro")[:60],
        "cidade": str(address.get("city") or settings.company_city or "Vitoria")[:60],
        "uf": str(address.get("uf") or settings.company_state or "ES")[:2].upper(),
        "endereco": str(address.get("street") or settings.company_street or "Rua")[:90],
    }


def _write_mock_pdf(proposal_id: str, amount: Decimal, seu_numero: str) -> str:
    root = Path(settings.storage_path) / "boleto"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"MOCK_{proposal_id.replace('-', '')[:12]}.pdf"
    # PDF mínimo válido o bastante para download em testes
    content = (
        b"%PDF-1.1\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
        b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
        b"4 0 obj<< /Length 68 >>stream\n"
        b"BT /F1 12 Tf 20 100 Td (LETTER MOCK BOLETO) Tj ET\n"
        b"endstream\nendobj\n"
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"trailer<< /Size 6 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n"
    )
    path.write_bytes(content)
    # metadados em sidecar para inspeção
    meta = root / f"MOCK_{proposal_id.replace('-', '')[:12]}.json"
    meta.write_text(
        json.dumps(
            {"proposal_id": proposal_id, "amount": str(amount), "seu_numero": seu_numero},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return str(path)


def boleto_view_from_terms(terms: dict, *, lead_id: str | None = None) -> dict | None:
    boleto = terms.get("boleto")
    if not isinstance(boleto, dict) or not boleto.get("codigo_solicitacao"):
        return None
    out = {
        "provider": boleto.get("provider"),
        "codigo_solicitacao": boleto.get("codigo_solicitacao"),
        "seu_numero": boleto.get("seu_numero"),
        "amount": boleto.get("amount"),
        "issued_at": boleto.get("issued_at"),
        "due_date": boleto.get("due_date"),
        "pdf_url": boleto.get("pdf_url") or boleto.get("url"),
        "download_token": boleto_public_token(lead_id) if lead_id else None,
    }
    return out


def issue_marketplace_boleto(
    db: Session,
    actor: User,
    lead_id: str,
    *,
    force_new: bool = False,
) -> dict:
    lead = get_lead_for_user(db, actor, lead_id)
    proposal = _marketplace_proposal(db, lead)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposta Marketplace não encontrada para este cadastro")

    terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json))
    life = terms.get("lifecycle") if isinstance(terms.get("lifecycle"), dict) else {}
    situation = str(life.get("situation") or SIT_AGUARDANDO).upper()
    if situation in {SIT_CANCELADO, SIT_CANCELADO_FALTA, "CANCELADA"}:
        raise HTTPException(status_code=409, detail="Não é possível emitir boleto para venda cancelada")

    existing = terms.get("boleto") if isinstance(terms.get("boleto"), dict) else None
    if existing and existing.get("codigo_solicitacao") and not force_new:
        view = boleto_view_from_terms(terms, lead_id=lead.id)
        return {"boleto": view, "created": False, "proposal_id": proposal.id}

    snap = _snapshot_from_lead(lead)
    amount = resolve_entrada_amount(terms, snap)
    if amount <= 0:
        # tenta recalcular das cotas
        quota_ids = [str(x) for x in (terms.get("quota_ids") or []) if x]
        if not quota_ids and terms.get("quota_id"):
            quota_ids = [str(terms["quota_id"])]
        if quota_ids:
            from app.marketplace_service import pricing_for_quota
            from app.quota_supplier_service import suppliers_index

            suppliers = suppliers_index(db, proposal.organization_id)
            quotas = list(db.scalars(select(Quota).where(Quota.id.in_(quota_ids))))
            amount = money(sum((pricing_for_quota(q, suppliers=suppliers)["entrada_final"] for q in quotas), Decimal("0")))
            terms["total_entrada"] = str(amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Valor de entrada indisponível para emitir boleto")

    seu_numero = seu_numero_for_proposal(proposal.id, "P")
    issued_at = datetime.now(UTC).isoformat()

    from datetime import date, timedelta

    due_date = (date.today() + timedelta(days=inter_vencimento_dias())).isoformat()

    if inter_configured():
        from app.inter_client import InterClient

        client = InterClient()
        pagador = _pagador_from_lead(lead, terms, snap)
        cobranca = client.create_cobranca(
            seu_numero=seu_numero,
            valor=amount,
            pagador=pagador,
            mensagem_linhas=[
                "LETTER — entrada Marketplace",
                f"Proposta {proposal.id[:8]}",
            ],
        )
        codigo = str(cobranca["codigoSolicitacao"])
        pdf_b64 = client.download_pdf_base64(codigo)
        root = Path(settings.storage_path) / "boleto"
        root.mkdir(parents=True, exist_ok=True)
        pdf_path = root / f"INTER_{codigo}.pdf"
        import base64

        pdf_path.write_bytes(base64.b64decode(pdf_b64))
        provider = "INTER"
        pdf_url = f"/api/v1/marketplace/cadastros/{lead.id}/boleto/{boleto_public_token(lead.id)}"
        local_path = str(pdf_path)
    else:
        codigo = f"DEV-{proposal.id}"
        local_path = _write_mock_pdf(proposal.id, amount, seu_numero)
        provider = "MOCK"
        pdf_url = f"/api/v1/marketplace/cadastros/{lead.id}/boleto/{boleto_public_token(lead.id)}"

    terms["boleto"] = {
        "provider": provider,
        "codigo_solicitacao": codigo,
        "seu_numero": seu_numero,
        "amount": str(amount),
        "issued_at": issued_at,
        "due_date": due_date,
        "pdf_url": pdf_url,
        "local_path": local_path,
    }
    if not terms.get("total_entrada"):
        terms["total_entrada"] = str(amount)
    proposal.terms_json = json.dumps(terms, ensure_ascii=False)
    db.flush()
    view = boleto_view_from_terms(terms, lead_id=lead.id)
    from app.marketplace_notification_service import dispatch_boleto_issued_notifications

    dispatch_boleto_issued_notifications(db, actor, lead, proposal, terms, boleto=view)
    return {
        "boleto": view,
        "created": True,
        "proposal_id": proposal.id,
    }


def read_boleto_pdf_bytes(db: Session, lead_id: str, token: str) -> tuple[bytes, str]:
    if not verify_boleto_public_token(lead_id, token):
        raise HTTPException(status_code=403, detail="Token de boleto inválido")
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Cadastro não encontrado")
    proposal = _marketplace_proposal(db, lead)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json))
    boleto = terms.get("boleto") if isinstance(terms.get("boleto"), dict) else None
    if not boleto or not boleto.get("local_path"):
        # emissão lazy (como Paulo)
        admin = db.scalar(
            select(User).where(
                User.organization_id == lead.organization_id,
                User.active.is_(True),
            ).order_by(User.created_at.asc())
        )
        if not admin:
            raise HTTPException(status_code=503, detail="Sem usuário para emitir boleto")
        issue_marketplace_boleto(db, admin, lead.id)
        db.flush()
        terms = seed_marketplace_lifecycle(_parse_json(proposal.terms_json))
        boleto = terms.get("boleto") if isinstance(terms.get("boleto"), dict) else None
    if not boleto or not boleto.get("local_path"):
        raise HTTPException(status_code=404, detail="PDF do boleto indisponível")
    path = Path(str(boleto["local_path"]))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo do boleto não encontrado")
    filename = f"boleto-{lead_id[:8]}.pdf"
    return path.read_bytes(), filename
