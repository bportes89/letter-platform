"""Garante uma conta por e-mail, CPF e CNPJ."""

from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User

CPF_LENGTH = 11
CNPJ_LENGTH = 14


def normalize_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_cpf(value: str | None) -> str | None:
    digits = normalize_digits(value)
    if not digits:
        return None
    if len(digits) != CPF_LENGTH:
        raise HTTPException(status_code=422, detail="CPF inválido")
    return digits


def normalize_cnpj(value: str | None) -> str | None:
    digits = normalize_digits(value)
    if not digits:
        return None
    if len(digits) != CNPJ_LENGTH:
        raise HTTPException(status_code=422, detail="CNPJ inválido")
    return digits


def find_user_by_email(db: Session, email: str, *, exclude_user_id: str | None = None) -> User | None:
    normalized = normalize_email(email)
    query = select(User).where(func.lower(User.email) == normalized)
    if exclude_user_id:
        query = query.where(User.id != exclude_user_id)
    return db.scalar(query)


def _find_user_by_field_digits(
    db: Session,
    field: str,
    digits: str,
    *,
    exclude_user_id: str | None = None,
) -> User | None:
    if not digits:
        return None
    query = select(User)
    if exclude_user_id:
        query = query.where(User.id != exclude_user_id)
    for user in db.scalars(query):
        stored = normalize_digits(getattr(user, field))
        if stored and stored == digits:
            return user
    return None


def find_user_by_cpf(db: Session, document: str | None, *, exclude_user_id: str | None = None) -> User | None:
    digits = normalize_digits(document)
    if len(digits) != CPF_LENGTH:
        return None
    return _find_user_by_field_digits(db, "document", digits, exclude_user_id=exclude_user_id)


def find_user_by_cnpj(db: Session, company_cnpj: str | None, *, exclude_user_id: str | None = None) -> User | None:
    digits = normalize_digits(company_cnpj)
    if len(digits) != CNPJ_LENGTH:
        return None
    return _find_user_by_field_digits(db, "company_cnpj", digits, exclude_user_id=exclude_user_id)


def ensure_unique_account_fields(
    db: Session,
    *,
    email: str,
    document: str | None = None,
    company_cnpj: str | None = None,
    exclude_user_id: str | None = None,
) -> tuple[str, str | None, str | None]:
    normalized_email = normalize_email(email)
    normalized_cpf = normalize_cpf(document)
    normalized_cnpj = normalize_cnpj(company_cnpj)

    if find_user_by_email(db, normalized_email, exclude_user_id=exclude_user_id):
        raise HTTPException(
            status_code=409,
            detail="E-mail já cadastrado. Faça login ou recupere sua senha.",
        )
    if normalized_cpf and find_user_by_cpf(db, normalized_cpf, exclude_user_id=exclude_user_id):
        raise HTTPException(status_code=409, detail="CPF já cadastrado em outra conta.")
    if normalized_cnpj and find_user_by_cnpj(db, normalized_cnpj, exclude_user_id=exclude_user_id):
        raise HTTPException(status_code=409, detail="CNPJ já cadastrado em outra conta.")

    return normalized_email, normalized_cpf, normalized_cnpj
