from uuid import uuid4

from app.client_propagator_service import CLIENT_TREE_TYPE, resolve_commercial_anchor


def test_client_propagator_referral_and_chain(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.public_app_url", "https://plataformaletter.com.br")

    partner_login = client.post("/api/v1/auth/login", json={"email": "parceiro@letter.com.br", "password": "Letter@123"})
    partner_headers = {"Authorization": f"Bearer {partner_login.json()['access_token']}"}
    partner_referral = client.get("/api/v1/network/me/referral", headers=partner_headers)
    partner_code = partner_referral.json()["referral_code"]

    suffix = uuid4().hex[:8]
    client_email = f"propagador.{suffix}@letter.com.br"
    registered = client.post("/api/v1/public/site/auth/register", json={
        "name": "Cliente Propagador",
        "email": client_email,
        "phone": "27966664444",
        "password": "ClienteMmn1!",
        "document": "52998224725",
        "referral_code": partner_code,
        "terms_accepted": True,
    })
    assert registered.status_code == 201, registered.text

    client_login = client.post("/api/v1/auth/login", json={"email": client_email, "password": "ClienteMmn1!"})
    client_headers = {"Authorization": f"Bearer {client_login.json()['access_token']}"}

    propagator_referral = client.get("/api/v1/network/me/referral", headers=client_headers)
    assert propagator_referral.status_code == 200, propagator_referral.text
    body = propagator_referral.json()
    assert body["referral_code"].startswith("LTR-CLI-")
    assert body["tree_type"] == CLIENT_TREE_TYPE
    assert body["propagator_mode"] is True

    invited_email = f"indicado.{suffix}@letter.com.br"
    invited = client.post("/api/v1/public/site/auth/register", json={
        "name": "Indicado do Propagador",
        "email": invited_email,
        "phone": "27966663333",
        "password": "ClienteMmn1!",
        "document": "11144477735",
        "referral_code": body["referral_code"],
        "terms_accepted": True,
    })
    assert invited.status_code == 201, invited.text

    invited_login = client.post("/api/v1/auth/login", json={"email": invited_email, "password": "ClienteMmn1!"})
    invited_headers = {"Authorization": f"Bearer {invited_login.json()['access_token']}"}
    proposal = client.post("/api/v1/proposals", headers=invited_headers, json={
        "product": "MARKETPLACE",
        "requested_amount": "500000",
        "terms": {"channel": "SELF_SERVICE"},
    })
    assert proposal.status_code == 201
    partner = client.get("/api/v1/auth/me", headers=partner_headers).json()
    assert proposal.json()["commission_originator_id"] == partner["id"]
