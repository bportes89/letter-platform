from decimal import Decimal

from app.public_site_service import format_public_pipeline_display, public_spe_ledger
from app.vender_cota_service import default_organization_id


def test_format_public_pipeline_display_millions():
    assert format_public_pipeline_display(Decimal("297000000")) == "R$ 297 mi"
    assert format_public_pipeline_display(Decimal("1500000")) == "R$ 1,5 mi"


def test_public_spe_ledger_sums_sdc_and_flash(client, auth_headers):
    sdc_store = client.post(
        "/api/v1/sdc/desk/solicitations",
        headers=auth_headers,
        json={
            "asset_type": "imovel",
            "asset_value": "500000",
            "asset_paid_off": True,
            "asset_has_lien": False,
            "docs_complete": True,
            "contact_name": "Pipeline Ledger SDC",
            "contact_email": "ledger.sdc@letter.test",
            "contact_phone": "32999990001",
            "document": "39053344705",
            "person_type": "PF",
            "marital_status": "SOLTEIRO",
            "income_value": "15000",
        },
    )
    assert sdc_store.status_code == 201, sdc_store.text

    flash_store = client.post(
        "/api/v1/flash/desk/solicitations",
        headers=auth_headers,
        json={
            "asset_type": "imovel",
            "asset_value": "1000000",
            "asset_paid_off": True,
            "asset_has_lien": False,
            "docs_complete": True,
            "term_months": 36,
            "capital_source": "RETAIL",
            "contact_name": "Pipeline Ledger Flash",
            "contact_email": "ledger.flash@letter.test",
            "contact_phone": "32999990002",
            "document": "57255607000130",
            "person_type": "PJ",
        },
    )
    assert flash_store.status_code == 201, flash_store.text

    res = client.get("/api/v1/public/site/spe-ledger")
    assert res.status_code == 200
    body = res.json()
    assert body["estimated_crivo_percent"] == "30"
    assert body["max_ltv_percent"] == "40"
    assert Decimal(body["sdc_pipeline_brl"]) >= Decimal("175000")
    assert Decimal(body["flash_pipeline_brl"]) >= Decimal("400000")
    assert Decimal(body["pipeline_total_brl"]) == Decimal(body["sdc_pipeline_brl"]) + Decimal(
        body["flash_pipeline_brl"]
    )
    assert body["operation_count"] >= 2
    assert body["pipeline_display"].startswith("R$")


def test_public_spe_ledger_service_matches_org(client):
    from app.db import SessionLocal

    with SessionLocal() as db:
        org_id = default_organization_id(db)
        payload = public_spe_ledger(db, org_id)
    assert payload["estimated_crivo_percent"] == "30"
