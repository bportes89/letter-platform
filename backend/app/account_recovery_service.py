"""Recuperação de acesso — localizar e-mail cadastrado por CPF e celular."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.account_uniqueness import find_user_by_cpf, normalize_digits
from app.models import User

GENERIC_NOT_FOUND_MESSAGE = (
    "Não encontramos uma conta com esse CPF e celular. "
    "Revise os dados ou entre em contato com o suporte LETTER."
)


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    if len(local) <= 1:
        masked_local = "*"
    else:
        masked_local = f"{local[0]}{'*' * min(len(local) - 1, 6)}"
    return f"{masked_local}@{domain}"


def phones_match(stored: str | None, provided: str) -> bool:
    stored_digits = normalize_digits(stored)
    provided_digits = normalize_digits(provided)
    if len(stored_digits) < 10 or len(provided_digits) < 10:
        return False
    # Aceita com ou sem DDD extra / últimos 10–11 dígitos alinhados
    return (
        stored_digits == provided_digits
        or stored_digits.endswith(provided_digits[-10:])
        or provided_digits.endswith(stored_digits[-10:])
    )


def lookup_account_email(db: Session, *, document: str, phone: str) -> dict:
    cpf = normalize_digits(document)
    if len(cpf) != 11:
        return {"found": False, "masked_email": None, "message": GENERIC_NOT_FOUND_MESSAGE}

    user = find_user_by_cpf(db, cpf)
    if not user or not user.active:
        return {"found": False, "masked_email": None, "message": GENERIC_NOT_FOUND_MESSAGE}

    if not phones_match(user.phone, phone):
        return {"found": False, "masked_email": None, "message": GENERIC_NOT_FOUND_MESSAGE}

    return {
        "found": True,
        "masked_email": mask_email(user.email),
        "message": "Conta localizada. Use o e-mail abaixo para entrar ou redefinir sua senha.",
    }
