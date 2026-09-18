"""Validação de documentos e contatos (Brasil)."""

from __future__ import annotations

import re

_DIGITS = re.compile(r"\D+")


def only_digits(value: str | None) -> str:
    return _DIGITS.sub("", value or "")


def is_valid_email(value: str | None) -> bool:
    text = (value or "").strip()
    if not text or len(text) > 254:
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text))


def is_valid_phone_br(value: str | None) -> bool:
    digits = only_digits(value)
    return len(digits) in {10, 11}


def _cpf_checksum(digits: list[int], factor: int) -> int:
    total = sum(n * f for n, f in zip(digits, range(factor, 1, -1), strict=False))
    rest = (total * 10) % 11
    return 0 if rest == 10 else rest


def is_valid_cpf(value: str | None) -> bool:
    digits = only_digits(value)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    nums = [int(c) for c in digits]
    if _cpf_checksum(nums[:9], 10) != nums[9]:
        return False
    if _cpf_checksum(nums[:10], 11) != nums[10]:
        return False
    return True


def _cnpj_checksum(digits: list[int], weights: list[int]) -> int:
    total = sum(n * w for n, w in zip(digits, weights, strict=False))
    rest = total % 11
    return 0 if rest < 2 else 11 - rest


def is_valid_cnpj(value: str | None) -> bool:
    digits = only_digits(value)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    nums = [int(c) for c in digits]
    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6] + w1
    if _cnpj_checksum(nums[:12], w1) != nums[12]:
        return False
    if _cnpj_checksum(nums[:13], w2) != nums[13]:
        return False
    return True


def is_valid_cpf_or_cnpj(value: str | None) -> bool:
    digits = only_digits(value)
    if len(digits) == 11:
        return is_valid_cpf(digits)
    if len(digits) == 14:
        return is_valid_cnpj(digits)
    return False


def contact_validation_errors(
    *,
    document: str | None,
    email: str | None,
    phone: str | None,
    person_type: str | None = "PF",
) -> list[str]:
    errors: list[str] = []
    person = (person_type or "PF").upper()
    digits = only_digits(document)
    if person == "PJ":
        if not is_valid_cnpj(digits):
            errors.append("CNPJ inválido.")
    else:
        if not is_valid_cpf(digits):
            errors.append("CPF inválido.")
    if not is_valid_email(email):
        errors.append("E-mail inválido.")
    if not is_valid_phone_br(phone):
        errors.append("Telefone inválido (10 ou 11 dígitos).")
    return errors


def assert_valid_contact(
    *,
    document: str | None,
    email: str | None,
    phone: str | None,
    person_type: str | None = "PF",
) -> None:
    from fastapi import HTTPException

    errors = contact_validation_errors(
        document=document, email=email, phone=phone, person_type=person_type
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors[0])
