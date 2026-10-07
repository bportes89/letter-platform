import json
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    FlashSolicitation,
    Lead,
    Proposal,
    QuitConSolicitation,
    SdcSolicitation,
    User,
)
from app.partner_qualification_service import (
    _sales_volume_by_franchise,
    resolve_tier_for_amount,
)
from app.sdc_desk_service import STATUS_APPROVED as SDC_STATUS_APPROVED
from app.flash_desk_service import STATUS_APPROVED as FLASH_STATUS_APPROVED
from app.quitcon_desk_service import STATUS_APPROVED as QUITCON_STATUS_APPROVED


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


def test_sales_volume_by_franchise_sums_sdc_marketplace_flash_and_quitcon():
    with SessionLocal() as db:
        partner = db.scalar(select(User).where(User.email == "parceiro@letter.com.br"))
        assert partner is not None
        org_id = partner.organization_id
        franchise_id = partner.id
        now = datetime.now(timezone.utc)
        period_start = date(now.year, now.month, 1)
        period_end = date(now.year, now.month, 28)

        db.add(
            SdcSolicitation(
                organization_id=org_id,
                partner_user_id=partner.id,
                status=SDC_STATUS_APPROVED,
                contact_name="Cliente SDC",
                contact_email="sdc@test.local",
                asset_type="imovel",
                asset_value=100_000,
                credit_estimated=1_000,
                created_at=now,
            )
        )
        db.add(
            FlashSolicitation(
                organization_id=org_id,
                partner_user_id=partner.id,
                status=FLASH_STATUS_APPROVED,
                contact_name="Cliente Flash",
                contact_email="flash@test.local",
                asset_type="imovel",
                asset_value=200_000,
                principal=2_000,
                created_at=now,
            )
        )
        db.add(
            QuitConSolicitation(
                organization_id=org_id,
                partner_user_id=partner.id,
                status=QUITCON_STATUS_APPROVED,
                contact_name="Cliente QuitCon",
                contact_email="quitcon@test.local",
                outstanding_balance=50_000,
                quitacao_vp_amount=3_000,
                registry_number="REG-1",
                registry_office="Cartório Teste",
                created_at=now,
            )
        )
        lead = Lead(
            organization_id=org_id,
            owner_id=partner.id,
            name="Cliente Marketplace",
            phone="32999990001",
            product_interest="MARKETPLACE",
            status="QUALIFIED",
        )
        db.add(lead)
        db.flush()
        db.add(
            Proposal(
                organization_id=org_id,
                lead_id=lead.id,
                product="MARKETPLACE",
                requested_amount=Decimal("4000"),
                commission_originator_id=partner.id,
                terms_json=json.dumps({"lifecycle": {"situation": "CONCLUIDO"}}),
                created_at=now,
            )
        )
        db.commit()

        totals = _sales_volume_by_franchise(db, org_id, period_start, period_end)
        assert totals.get(franchise_id) == Decimal("10000.00")
