from decimal import Decimal

from app.partner_legacy_wallet_service import withdrawal_blocked_reason


def test_withdrawal_blocked_while_fiscal_hold():
    reason = withdrawal_blocked_reason(
        pending_fiscal=Decimal("150.00"),
        pending_receipt=Decimal("0"),
        withdrawable=Decimal("50"),
        amount=Decimal("50"),
    )
    assert reason is not None
    assert "NF-e" in reason


def test_withdrawal_allowed_when_no_hold():
    reason = withdrawal_blocked_reason(
        pending_fiscal=Decimal("0"),
        pending_receipt=Decimal("0"),
        withdrawable=Decimal("100"),
        amount=Decimal("40"),
    )
    assert reason is None


def test_withdrawal_blocked_on_receipt_hold():
    reason = withdrawal_blocked_reason(
        pending_fiscal=Decimal("0"),
        pending_receipt=Decimal("25"),
        withdrawable=Decimal("0"),
        amount=Decimal("10"),
    )
    assert reason is not None
    assert "comprovante" in reason
