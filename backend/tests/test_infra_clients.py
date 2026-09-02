import json

import httpx

from app.infra_clients import FipeCloudClient, InfoSimplesCndClient, OnrSerpClient, SerasaQsaClient


def test_infosimples_cnd_production_bundle(monkeypatch):
    monkeypatch.setattr("app.infra_clients.settings.infosimples_api_token", "test-token")

    calls: list[tuple[str, dict]] = []

    def handler(request: httpx.Request):
        body = json.loads(request.content.decode())
        assert body["token"] == "test-token"
        path = request.url.path
        calls.append((path, body))
        if path.endswith("/receita-federal/pgfn"):
            return httpx.Response(200, json={
                "code": 200,
                "data": {"conseguiu_emitir_certidao_negativa": True, "validade": "31/12/2026"},
            })
        if path.endswith("/caixa/regularidade"):
            return httpx.Response(200, json={
                "code": 200,
                "data": {"situacao": "REGULAR", "validade_fim_data": "31/12/2026"},
            })
        if path.endswith("/tst/cndt"):
            return httpx.Response(200, json={
                "code": 200,
                "data": {"conseguiu_emitir_certidao_negativa": True, "validade": "31/12/2026"},
            })
        return httpx.Response(404, json={"code": 404})

    transport = httpx.MockTransport(handler)
    original_post = httpx.post

    def mock_post(url, **kwargs):
        with httpx.Client(transport=transport) as client:
            return client.post(url, **kwargs)

    monkeypatch.setattr("app.infra_http.httpx.post", mock_post)

    client = InfoSimplesCndClient()
    result = client.query(context={"company_document": "57255607000130"})
    assert result.mode == "PRODUCTION"
    assert result.status == "PRODUCTION_OK"
    assert len(result.payload["cnds"]) == 3
    assert calls


def test_fipe_production_by_plate(monkeypatch):
    monkeypatch.setattr("app.infra_clients.settings.fipe_api_token", "fipe-key")

    def fake_get_json(url: str, *, headers=None):
        assert "ABC1D23" in url
        assert "key=fipe-key" in url
        return {"marca": "VW", "modelo": "GOL", "fipe": "45000.00"}

    monkeypatch.setattr("app.infra_clients.http_get_json", fake_get_json)

    client = FipeCloudClient()
    result = client.query(context={"plate": "ABC1D23"})
    assert result.mode == "PRODUCTION"
    assert result.payload["fipe_value_brl"] == "45000.00"


def test_onr_production_via_infosimples(monkeypatch):
    monkeypatch.setattr("app.infra_clients.settings.infosimples_api_token", "test-token")

    def fake_consult_registry(*, context):
        assert context.get("registry_number") == "12345"
        return {
            "registry_number": "12345",
            "encumbrances": [],
            "certificate_status": "CLEAR",
            "provider": "INFOSIMPLES_ONR",
        }

    monkeypatch.setattr("app.infra_clients.consult_registry", fake_consult_registry)
    client = OnrSerpClient()
    result = client.query(context={"registry_number": "12345"})
    assert result.mode == "PRODUCTION"
    assert result.payload["provider"] == "INFOSIMPLES_ONR"


def test_serasa_production_qsa(monkeypatch):
    monkeypatch.setattr("app.infra_clients.settings.serasa_api_key", "Basic abc")

    def fake_consult_qsa(*, cnpj: str):
        assert len(cnpj) == 14
        return {
            "company_document": cnpj,
            "partners_screened": 2,
            "partners": [{"name": "Socio A", "document": "11111111111", "role": "ADMIN"}],
            "restrictions_found": 0,
            "score_band": "SCORE_750",
            "provider": "SERASA_EXPERIAN",
        }

    monkeypatch.setattr("app.infra_clients.consult_qsa", fake_consult_qsa)
    client = SerasaQsaClient()
    result = client.query(context={"company_document": "57255607000130"})
    assert result.mode == "PRODUCTION"
    assert result.payload["partners_screened"] == 2


def test_onr_without_credentials_uses_sandbox():
    client = OnrSerpClient()
    result = client.query(context={"registry_number": "999"})
    assert result.mode == "SANDBOX"
