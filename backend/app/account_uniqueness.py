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


def is_valid_cpf(digits: str) -> bool:
    if len(digits) != CPF_LENGTH or digits == digits[0] * CPF_LENGTH:
        return False

    def check(body: str) -> int:
        total = sum(int(body[i]) * (len(body) + 1 - i) for i in range(len(body)))
        remainder = (total * 10) % 11
        return 0 if remainder == 10 else remainder

    return check(digits[:9]) == int(digits[9]) and check(digits[:10]) == int(digits[10])


def is_valid_cnpj(digits: str) -> bool:
    if len(digits) != CNPJ_LENGTH or digits == digits[0] * CNPJ_LENGTH:
        return False

    def check(body: str, weights: tuple[int, ...]) -> int:
        total = sum(int(body[i]) * weights[i] for i in range(len(body)))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder

    first_weights = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    second_weights = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    return (
        check(digits[:12], first_weights) == int(digits[12])
        and check(digits[:13], second_weights) == int(digits[13])
    )


def resolve_cpf_cnpj_fields(
    *,
    document: str | None = None,
    company_cnpj: str | None = None,
    field_label: str = "CPF/CNPJ",
) -> tuple[str | None, str | None]:
    """Normaliza CPF (11) e CNPJ (14) a partir dos campos de cadastro."""
    normalized_cpf: str | None = None
    normalized_cnpj: str | None = None

    if document:
        digits = assert_valid_cpf_or_cnpj(document, field_label=field_label)
        if len(digits) == CPF_LENGTH:
            normalized_cpf = digits
        else:
            normalized_cnpj = digits

    if company_cnpj:
        cnpj_digits = assert_valid_cpf_or_cnpj(company_cnpj, field_label="CNPJ")
        if normalized_cnpj and normalized_cnpj != cnpj_digits:
            raise HTTPException(status_code=422, detail="CNPJ informado em campos diferentes não coincide.")
        normalized_cnpj = cnpj_digits

    return normalized_cpf, normalized_cnpj


def assert_valid_cpf_or_cnpj(value: str | None, *, field_label: str = "CPF/CNPJ") -> str:
    digits = normalize_digits(value)
    if len(digits) == CPF_LENGTH:
        if not is_valid_cpf(digits):
            raise HTTPException(
                status_code=422,
                detail=f"{field_label} inválido. Atualize seu cadastro com um CPF válido antes de concluir o KYC.",
            )
        return digits
    if len(digits) == CNPJ_LENGTH:
        if not is_valid_cnpj(digits):
            raise HTTPException(
                status_code=422,
                detail=f"{field_label} inválido. Atualize seu cadastro com um CNPJ válido antes de concluir o KYC.",
            )
        return digits
    raise HTTPException(
        status_code=422,
        detail=f"{field_label} obrigatório com 11 (CPF) ou 14 (CNPJ) dígitos válidos.",
    )

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
    normalized_cpf, normalized_cnpj = resolve_cpf_cnpj_fields(
        document=document,
        company_cnpj=company_cnpj,
    )

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
