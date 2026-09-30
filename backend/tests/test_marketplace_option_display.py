from app.marketplace_option_display import format_parcela_legacy, installment_due_hints


def test_format_parcela_legacy_joins_groups():
    quotas = [
        {"remaining_installments": 124, "installment_value": "3827.08"},
        {"remaining_installments": 44, "installment_value": "2450.00"},
    ]
    text = format_parcela_legacy(quotas)
    assert "124x" in text
    assert "44x" in text
    assert " mais " in text


def test_installment_due_hints():
    day, nxt = installment_due_hints([{"installment_due_date": "2038-11-10"}])
    assert day == "10"
    assert nxt == "10/11/2038"
