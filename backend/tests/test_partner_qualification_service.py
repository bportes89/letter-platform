from decimal import Decimal

from app.partner_qualification_service import resolve_tier_for_amount


class _Tier:
    def __init__(self, price_init, price_final, name="T"):
        self.price_init = price_init
        self.price_final = price_final
        self.name = name
        self.active = True
        self.organization_id = "org"


def test_resolve_tier_for_amount_picks_first_matching_band():
    tiers = [_Tier(0, 1000, "A"), _Tier(1000.01, 5000, "B")]

    class FakeScalars:
        def all(self):
            return tiers

    class FakeSession:
        def scalars(self, _q):
            return FakeScalars()

    tier = resolve_tier_for_amount(FakeSession(), "org", Decimal("500"))
    assert tier.name == "A"
    tier2 = resolve_tier_for_amount(FakeSession(), "org", Decimal("2500"))
    assert tier2.name == "B"

