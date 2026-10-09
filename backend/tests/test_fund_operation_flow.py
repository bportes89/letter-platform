"""Escritório do fundo — acompanhamento de operação Flash institucional."""

from __future__ import annotations


def _store_institutional_flash(client, auth_headers, partner_headers):
    ok = client.post(
        "/api/v1/flash/desk/evaluate",
        headers=auth_headers,
        json={
            "asset_type": "imovel",
            "asset_value": "1000000",
            "asset_paid_off": True,
            "asset_has_lien": False,
            "docs_complete": True,
            "term_months": 36,
            "capital_source": "INSTITUTIONAL",
            "operation_type": "IMOVEL_PROPRIO",
        },
    )
    assert ok.status_code == 200 and ok.json()["result"]["viable"] is True
    stored = client.post(
        "/api/v1/flash/desk/solicitations",
        headers=partner_headers,
        json={
            "asset_type": "imovel",
            "asset_value": "1000000",
            "asset_paid_off": True,
            "asset_has_lien": False,
            "docs_complete": True,
            "term_months": 36,
            "capital_source": "INSTITUTIONAL",
            "operation_type": "IMOVEL_PROPRIO",
            "contact_name": "Cliente Fundo Nordeste",
            "contact_email": "cliente.fundo@example.com",
            "contact_phone": "31988776655",
            "document": "12345678909",
            "person_type": "PF",
        },
    )
    assert stored.status_code == 201, stored.text
    return stored.json()


def test_fund_operation_flow_starts_at_term_sheet(client, auth_headers, partner_headers):
    body = _store_institutional_flash(client, auth_headers, partner_headers)
    flow = body.get("fund_operation_flow")
    assert flow is not None
    steps = flow["steps"]
    assert len(steps) == 8
    assert steps[0]["code"] == "TERM_SHEET"
    assert steps[0]["status"] == "IN_PROGRESS"
    assert steps[1]["code"] == "DOCS_COMPLIANCE"
    assert steps[1]["status"] == "PENDING"
    assert all(s["code"] != "CARTA_PAULO" for s in steps)


def test_fund_office_lists_and_advances_flow(client, auth_headers, partner_headers):
    body = _store_institutional_flash(client, auth_headers, partner_headers)
    sid = body["id"]

    fund_login = client.post(
        "/api/v1/auth/login",
        json={"email": "fundo@letter.com.br", "password": "Letter@123"},
    ).json()
    fund_headers = {"Authorization": f"Bearer {fund_login['access_token']}"}

    listed = client.get("/api/v1/funding/fund-office/operations", headers=fund_headers)
    assert listed.status_code == 200
    row = next((r for r in listed.json() if r["id"] == sid), None)
    assert row is not None
    assert row["current_step_code"] == "TERM_SHEET"

    detail = client.get(f"/api/v1/funding/fund-office/operations/{sid}", headers=fund_headers)
    assert detail.status_code == 200
    assert detail.json()["fund_operation_flow"]["steps"][0]["status"] == "IN_PROGRESS"

    patched = client.patch(
        f"/api/v1/flash/desk/solicitations/{sid}/fund-operation-flow",
        headers=fund_headers,
        json={"step_code": "TERM_SHEET", "status": "COMPLETED", "advance_next": True},
    )
    assert patched.status_code == 200
    flow = patched.json()["fund_operation_flow"]
    assert flow["steps"][0]["status"] == "COMPLETED"
    assert flow["steps"][1]["code"] == "DOCS_COMPLIANCE"
    assert flow["steps"][1]["status"] == "IN_PROGRESS"
