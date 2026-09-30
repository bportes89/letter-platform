from unittest.mock import MagicMock

from app.marketplace_option_display import (
    chat_option_from_match_row,
    enrich_match_row_display,
    format_parcela_legacy,
    installment_due_hints,
)


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


def test_enrich_match_row_display_parcela():
    row = {
        "administrator_name": "Test Admin",
        "quotas": [
            {
                "remaining_installments": 48,
                "installment_value": "2800",
                "installment_due_date": "2026-09-10",
            }
        ],
    }
    db = MagicMock()
    out = enrich_match_row_display(db, "org-1", row, category="REAL_ESTATE")
    assert "48x" in (out.get("parcela_legacy") or "")
    assert out.get("vencimento_dia") == "10"
    assert out.get("tipo_credito") == "Imóvel"


def test_chat_option_from_match_row_fields():
    row = {
        "quota_ids": ["q1"],
        "total_credit": "400000",
        "total_entrada": "80000",
        "administrator_name": "HS",
        "quotas": [
            {
                "quota_id": "q1",
                "remaining_installments": 60,
                "installment_value": "2500",
                "installment_due_date": "2026-10-15",
            }
        ],
    }
    db = MagicMock()
    db.scalar.return_value = None
    db.get.return_value = None

    def brl(v):
        return f"R$ {v}"

    opt = chat_option_from_match_row(
        db, "org-1", row, lane_label="Crédito", category="REAL_ESTATE", brl_fn=brl
    )
    assert opt["administradora"] == "HS"
    assert opt["lane"] == "Crédito"
    assert "60x" in (opt.get("price_parcela") or "")
    assert opt.get("vencimento_dia") == "15"
