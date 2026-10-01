"""Emissão de cobrança Inter (boleto + PIX) reutilizável — TAPAF, LSS, etc."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from decimal import Decimal
from pathlib import Path

from app.core.config import settings
from app.inter_common import inter_configured, inter_vencimento_dias
from app.models import User
from app.services import money


def _digits(value: str | None) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def pagador_from_user(user: User) -> dict:
    doc = _digits(getattr(user, "document", None) or "")
    if len(doc) not in {11, 14}:
        doc = "00000000000"
    person = "JURIDICA" if len(doc) == 14 else "FISICA"
    phone = _digits(getattr(user, "phone", None) or "")
    ddd = phone[:2] if len(phone) >= 10 else "11"
    tel = phone[2:] if len(phone) >= 10 else "999999999"
    return {
        "cpfCnpj": doc,
        "tipoPessoa": person,
        "nome": (user.name or "Cliente LETTER")[:100],
        "email": (user.email or "noreply@letter.app.br")[:80],
        "ddd": ddd,
        "telefone": tel[:9],
        "cep": _digits(getattr(settings, "company_zipcode", None))[:8] or "29090130",
        "numero": "0",
        "complemento": "",
        "bairro": "Centro",
        "cidade": (settings.company_city or "Vitoria")[:60],
        "uf": (settings.company_state or "ES")[:2].upper(),
        "endereco": (settings.company_street or "Rua")[:90],
    }


def _pix_from_cobranca_body(body: dict) -> tuple[str | None, str | None]:
    if not isinstance(body, dict):
        return None, None
    for key in ("pixCopiaECola", "pix_copy_paste", "emv"):
        if body.get(key):
            return str(body[key]), body.get("txid")
    pix = body.get("pix")
    if isinstance(pix, dict):
        copy = pix.get("pixCopiaECola") or pix.get("emv")
        if copy:
            return str(copy), pix.get("txid")
    cob = body.get("cobranca") or body.get("raw")
    if isinstance(cob, dict):
        return _pix_from_cobranca_body(cob)
    return None, None


def issue_inter_charge(
    *,
    user: User,
    amount: Decimal,
    seu_numero: str,
    mensagem_linhas: list[str],
    pdf_filename_prefix: str,
) -> dict:
    if not inter_configured():
        raise RuntimeError("Inter não configurado")
    from app.inter_client import InterClient

    client = InterClient()
    cobranca = client.create_cobranca(
        seu_numero=seu_numero[:15],
        valor=money(amount),
        pagador=pagador_from_user(user),
        mensagem_linhas=mensagem_linhas,
    )
    codigo = str(cobranca["codigoSolicitacao"])
    raw = cobranca.get("raw") if isinstance(cobranca.get("raw"), dict) else {}
    pix_copy, pix_txid = _pix_from_cobranca_body(raw)
    if not pix_copy:
        try:
            detail = client.get_cobranca(codigo)
            pix_copy, pix_txid = _pix_from_cobranca_body(detail)
        except Exception:
            pix_copy = None

    pdf_b64 = client.download_pdf_base64(codigo)
    root = Path(settings.storage_path) / "boleto"
    root.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w\-]", "_", pdf_filename_prefix)[:40]
    pdf_path = root / f"{safe}_{codigo}.pdf"
    pdf_path.write_bytes(base64.b64decode(pdf_b64))

    return {
        "codigo_solicitacao": codigo,
        "seu_numero": seu_numero[:15],
        "amount": str(money(amount)),
        "due_date_days": inter_vencimento_dias(),
        "pix_copy_paste": pix_copy,
        "pix_txid": pix_txid,
        "local_pdf_path": str(pdf_path),
        "duplicated": bool(cobranca.get("duplicated")),
    }


def tapaf_boleto_public_token(pauta_id: str) -> str:
    digest = hmac.new(
        settings.secret_key.encode("utf-8"),
        f"tapaf-boleto-{pauta_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def verify_tapaf_boleto_token(pauta_id: str, token: str) -> bool:
    return hmac.compare_digest(tapaf_boleto_public_token(pauta_id), (token or "").strip())
