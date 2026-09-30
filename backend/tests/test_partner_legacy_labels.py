from app.partner_legacy_wallet_service import (
    commission_status_label,
    withdrawal_blocked_reason,
    withdrawal_status_label,
)


def test_commission_status_labels_pt():
    assert commission_status_label("AVAILABLE") == "Liberada para saque"
    assert commission_status_label("PENDING_FISCAL") == "Aguardando NF-e"
    assert commission_status_label("WITHDRAWN") == "Sacada"


def test_withdrawal_status_labels_pt():
    assert withdrawal_status_label("PENDING") == "Em análise"
    assert withdrawal_status_label("PAID") == "Pago"
    assert withdrawal_status_label("CANCELLED") == "Cancelado"


def test_withdrawal_blocked_reason_unchanged():
    from decimal import Decimal

    reason = withdrawal_blocked_reason(
        pending_fiscal=Decimal("10"),
        pending_receipt=Decimal("0"),
        withdrawable=Decimal("0"),
        amount=Decimal("1"),
    )
    assert reason is not None
    assert "NF-e" in reason
