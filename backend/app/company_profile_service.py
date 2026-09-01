"""Dados cadastrais da franqueadora (contratos, rodapé e assinaturas)."""

from __future__ import annotations

from app.core.config import settings


def company_profile() -> dict:
    street = settings.company_street.strip()
    number = settings.company_number.strip()
    address_line = f"{street}, {number}" if street and number else street or number
    city_state = ", ".join(part for part in (settings.company_city.strip(), settings.company_state.strip()) if part)
    postal = settings.company_postal_code.strip()
    if postal and len("".join(ch for ch in postal if ch.isdigit())) == 8:
        digits = "".join(ch for ch in postal if ch.isdigit())
        postal = f"{digits[:5]}-{digits[5:]}"
    district = settings.company_district.strip()
    footer_parts = [
        settings.company_legal_name.strip(),
        f"CNPJ {settings.company_cnpj.strip()}",
        address_line,
        " — ".join(part for part in (district, city_state, f"CEP {postal}" if postal else "") if part),
    ]
    return {
        "legal_name": settings.company_legal_name.strip(),
        "trade_name": settings.company_trade_name.strip(),
        "cnpj": settings.company_cnpj.strip(),
        "cnpj_digits": "".join(ch for ch in settings.company_cnpj if ch.isdigit()),
        "email": settings.company_email.strip().lower(),
        "phone": settings.company_phone.strip(),
        "street": street,
        "number": number,
        "district": district,
        "city": settings.company_city.strip(),
        "state": settings.company_state.strip(),
        "postal_code": postal,
        "opened_at": settings.company_opened_at.strip(),
        "address_line": address_line,
        "city_state": city_state,
        "footer_line": " · ".join(part for part in footer_parts if part),
        "contract_party_block": (
            f"<b>{settings.company_legal_name.strip()}</b>, pessoa jurídica de direito privado, "
            f"inscrita no CNPJ sob nº <b>{settings.company_cnpj.strip()}</b>, "
            f"com sede em {address_line}, {district}, {city_state}, CEP {postal}, "
            f"e-mail <b>{settings.company_email.strip().lower()}</b>, "
            f"telefone <b>{settings.company_phone.strip()}</b>, "
            f"doravante denominada <b>CONTRATADA</b>."
        ),
    }
