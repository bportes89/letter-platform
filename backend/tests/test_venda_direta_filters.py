from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.venda_direta_filters import quota_client_profile_blockers, quota_matches_category_tree


def test_quota_matches_category_tree_without_filter():
    db = MagicMock()
    quota = MagicMock(quota_category_id="cat-1")
    assert quota_matches_category_tree(db, "org", quota, None) is True


def test_quota_client_profile_dirty_name_blocks():
    db = MagicMock()
    quota = MagicMock(quota_category_id=None, administrator_id="adm-1")
    admin = MagicMock()
    admin.name = "Banco X"
    admin.id = "adm-1"
    admin.rules_json = "{}"

    with patch(
        "app.administrator_marketplace_profile.administrator_accepts_dirty_name",
        return_value=False,
    ):
        blockers = quota_client_profile_blockers(
            db,
            "org",
            quota,
            admin,
            category="REAL_ESTATE",
            has_credit_restriction=True,
        )
    assert blockers
    assert "SPC" in blockers[0] or "restrição" in blockers[0]


def test_combo_client_profile_requires_income():
    from app.venda_direta_filters import combo_client_profile_blockers

    db = MagicMock()
    quota = MagicMock(administrator_id="adm-1", quota_category_id=None)
    db.get.return_value = MagicMock(name="Admin", authorization_status="AUTHORIZED", rules_json="{}")
    with patch(
        "app.venda_direta_filters.quota_client_profile_blockers",
        return_value=[],
    ):
        blockers = combo_client_profile_blockers(
            db,
            "org",
            [quota],
            category="REAL_ESTATE",
            asset_year=2020,
            asset_is_zero_km=False,
            has_credit_restriction=False,
            monthly_income=Decimal("0"),
            asset_value=Decimal("500000"),
            credit_total=Decimal("400000"),
            installment_total=Decimal("3000"),
        )
    assert any("renda" in b.lower() for b in blockers)
