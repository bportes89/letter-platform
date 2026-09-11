"""Auto-cadastro público de fornecedor (cotas) + login no portal."""

from __future__ import annotations

import re
import unicodedata

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_uniqueness import assert_valid_cpf_or_cnpj, find_user_by_email
from app.core.security import hash_password, verify_password
from app.models import QuotaSupplier
from app.public_site_service import headquarters_org
from app.quota_supplier_service import normalize_source_key
from app.supplier_portal_auth import issue_portal_token


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _validate_supplier_password(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Senha deve ter no mínimo 8 caracteres.")
    if not re.search(r"[A-Za-z]", password):
        raise HTTPException(status_code=422, detail="Senha deve conter letras.")
    if not re.search(r"\d", password):
        raise HTTPException(status_code=422, detail="Senha deve conter números.")


def _slug_source_key(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    parts = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text.upper()).strip("_").split("_")
    base = "_".join([p for p in parts if p])[:24] or "FORNECEDOR"
    return f"FORN_{base}"


def _unique_source_key(db: Session, organization_id: str, name: str) -> str:
    base = normalize_source_key(_slug_source_key(name))
    candidate = base
    suffix = 2
    while db.scalar(
        select(QuotaSupplier.id).where(
            QuotaSupplier.organization_id == organization_id,
            QuotaSupplier.source_key == candidate,
        )
    ):
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def register_public_supplier(
    db: Session,
    *,
    person_type: str,
    name: str,
    trade_name: str | None,
    document: str,
    email: str,
    phone: str,
    password: str,
    terms_accepted: bool,
) -> dict:
    if not terms_accepted:
        raise HTTPException(status_code=422, detail="Aceite os termos de uso para continuar.")
    _validate_supplier_password(password)

    org = headquarters_org(db)
    person = person_type.strip().upper()
    if person not in {"PF", "PJ"}:
        raise HTTPException(status_code=422, detail="person_type deve ser PF ou PJ.")

    doc_digits = _digits(document)
    if person == "PF":
        doc_digits = assert_valid_cpf_or_cnpj(doc_digits, field_label="CPF")
        if len(doc_digits) != 11:
            raise HTTPException(status_code=422, detail="CPF inválido.")
    else:
        doc_digits = assert_valid_cpf_or_cnpj(doc_digits, field_label="CNPJ")
        if len(doc_digits) != 14:
            raise HTTPException(status_code=422, detail="CNPJ inválido.")

    normalized_email = email.strip().lower()
    if find_user_by_email(db, normalized_email):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado em outra conta LETTER.")
    existing_supplier = db.scalar(
        select(QuotaSupplier).where(
            QuotaSupplier.organization_id == org.id,
            QuotaSupplier.email == normalized_email,
        )
    )
    if existing_supplier:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado como fornecedor.")

    doc_conflict = db.scalar(
        select(QuotaSupplier).where(
            QuotaSupplier.organization_id == org.id,
            QuotaSupplier.document == doc_digits,
        )
    )
    if doc_conflict:
        raise HTTPException(status_code=409, detail="Documento já cadastrado como fornecedor.")

    phone_digits = _digits(phone)
    if len(phone_digits) < 10:
        raise HTTPException(status_code=422, detail="Telefone inválido.")

    display_name = name.strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="Nome obrigatório.")

    supplier = QuotaSupplier(
        organization_id=org.id,
        active=True,
        person_type=person,
        name=display_name,
        trade_name=(trade_name or "").strip() or None,
        document=doc_digits,
        email=normalized_email,
        phone=phone.strip(),
        source_key=_unique_source_key(db, org.id, trade_name or display_name),
        markup_percent=3,
        quem_paga_comissao=0,
        platform_fee_percent=0,
        sync_mode="NONE",
        password_hash=hash_password(password),
    )
    db.add(supplier)
    db.flush()
    portal_token = issue_portal_token(supplier)
    db.flush()
    return {
        "supplier_id": supplier.id,
        "source_key": supplier.source_key,
        "portal_token": portal_token,
        "portal_url": f"/portal-fornecedor?token={portal_token}",
        "name": supplier.name,
        "email": supplier.email,
    }


def login_supplier_portal(db: Session, *, email: str, password: str) -> dict:
    org = headquarters_org(db)
    normalized_email = email.strip().lower()
    supplier = db.scalar(
        select(QuotaSupplier).where(
            QuotaSupplier.organization_id == org.id,
            QuotaSupplier.email == normalized_email,
            QuotaSupplier.active.is_(True),
        )
    )
    if not supplier or not supplier.password_hash or not verify_password(password, supplier.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    portal_token = issue_portal_token(supplier)
    db.flush()
    return {
        "supplier_id": supplier.id,
        "source_key": supplier.source_key,
        "portal_token": portal_token,
        "portal_url": f"/portal-fornecedor?token={portal_token}",
        "name": supplier.name,
        "email": supplier.email,
    }
