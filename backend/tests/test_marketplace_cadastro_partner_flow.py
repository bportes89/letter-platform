"""Esteira 1/2 → cadastro: dados do cliente antes do boleto; parceiro sem fornecedor."""

from __future__ import annotations


def _esteira_lock(client, auth_headers, quota_id: str) -> str:
    profile = {
        "monthly_income": "50000",
        "monthly_commitment": "0",
        "asset_value": "900000",
        "asset_year": 2020,
        "has_credit_restriction": False,
        "asset_is_zero_km": False,
    }
    lock = client.post(
        "/api/v1/marketplace/esteira-1/lock",
        headers=auth_headers,
        json={"quota_ids": [quota_id], "esteira": "SELF_SELECT", **profile},
    )
    assert lock.status_code == 200, lock.text
    return lock.json()["lead_id"]


def test_esteira_lock_starts_incomplete_and_blocks_boleto(client, auth_headers, partner_headers):
    quota = next(q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["status"] == "AVAILABLE")
    lead_id = _esteira_lock(client, partner_headers, quota["id"])

    detail = client.get(f"/api/v1/marketplace/cadastros/{lead_id}", headers=partner_headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["situation"] == "INCOMPLETO"
    assert body["client_registration_complete"] is False
    assert body["can_emit_boleto"] is False
    assert body.get("supplier_sources") == []
    for code in body.get("quota_codes") or []:
        assert "SYNC-" not in code
        assert "Letter/Ref" in code
    assert "fornecedor" not in (body.get("parties") or {})
    assert "fundo" not in (body.get("parties") or {})

    blocked = client.post(f"/api/v1/marketplace/cadastros/{lead_id}/boleto", headers=partner_headers)
    assert blocked.status_code == 422
    assert "cliente" in blocked.json()["detail"].lower()

    saved = client.patch(
        f"/api/v1/marketplace/cadastros/{lead_id}",
        headers=partner_headers,
        json={
            "name": "Maria Marketplace",
            "phone": "31988887777",
            "document": "52998224725",
            "email": "maria.marketplace@letter.test",
        },
    )
    assert saved.status_code == 200, saved.text
    after = saved.json()
    assert after["client_registration_complete"] is True
    assert after["situation"] == "AGUARDANDO_PAGAMENTO"
    assert after["can_emit_boleto"] is True
    assert after.get("has_site_contract") is True

    issued = client.post(f"/api/v1/marketplace/cadastros/{lead_id}/boleto", headers=partner_headers)
    assert issued.status_code == 200, issued.text
