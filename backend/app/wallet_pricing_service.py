"""Tabela de precificação LETTER — mensalidade Escrow e taxas por transação."""

from __future__ import annotations

from decimal import Decimal

from app.core.config import settings
from app.services import money


def pricing_table() -> list[dict]:
    return [
        {
            "code": "ESCROW_MONTHLY",
            "label": "Mensalidade plataforma Escrow",
            "customer_amount": str(money(Decimal(str(settings.wallet_escrow_monthly_fee)))),
            "applies_to": "ESCROW_ONLY",
            "billing_cycle_days": settings.wallet_billing_cycle_days,
        },
        {
            "code": "PIX",
            "label": "Recebimento Pix",
            "customer_amount": str(money(Decimal(str(settings.wallet_fee_pix)))),
            "applies_to": "ALL_ACCOUNTS",
        },
        {
            "code": "BOLETO",
            "label": "Recebimento boleto",
            "customer_amount": str(money(Decimal(str(settings.wallet_fee_boleto)))),
            "applies_to": "ALL_ACCOUNTS",
        },
        {
            "code": "CARD",
            "label": "Recebimento cartão",
            "customer_amount": f"{settings.wallet_fee_card_percent}% + R$ {settings.wallet_fee_card_fixed:.2f}",
            "applies_to": "ALL_ACCOUNTS",
        },
        {
            "code": "TRANSFER",
            "label": "Saque / transferência Pix",
            "customer_amount": str(money(Decimal(str(settings.wallet_fee_transfer)))),
            "applies_to": "ALL_ACCOUNTS",
        },
        {
            "code": "BILL_PAYMENT",
            "label": "Pagamento de contas",
            "customer_amount": str(money(Decimal(str(settings.wallet_fee_bill_payment)))),
            "applies_to": "ALL_ACCOUNTS",
        },
    ]


def customer_fee_for(event_type: str, gross_amount: Decimal) -> Decimal:
    code = (event_type or "").upper()
    if code in {"PAYMENT_RECEIVED", "PIX", "FUNDS_CONFIRMED"}:
        return money(Decimal(str(settings.wallet_fee_pix)))
    if code == "BOLETO":
        return money(Decimal(str(settings.wallet_fee_boleto)))
    if code == "CARD":
        percent = Decimal(str(settings.wallet_fee_card_percent)) / Decimal("100")
        fixed = Decimal(str(settings.wallet_fee_card_fixed))
        return money(gross_amount * percent + fixed)
    if code in {"TRANSFER", "TRANSFER_SENT"}:
        return money(Decimal(str(settings.wallet_fee_transfer)))
    if code == "BILL_PAYMENT":
        return money(Decimal(str(settings.wallet_fee_bill_payment)))
    return Decimal("0")
