import json
from decimal import Decimal

import httpx
import pytest
from fastapi import HTTPException

from app.sefaz_client import consult_nfe, infosimples_configured


def test_consult_nfe_sandbox_authorizes_valid_key():
    result = consult_nfe("35250801234567890123456789012345678901234567")
    assert result.status == "AUTHORIZED"
    assert result.mode == "SANDBOX"
    assert result.provider == "SEFAZ_SANDBOX"


def test_consult_nfe_sandbox_canceled_suffix():
    result = consult_nfe("35250801234567890123456789012345600000000000")
    assert result.status == "CANCELED"


def test_consult_nfe_production_requires_infosimples(monkeypatch):
    monkeypatch.setattr("app.sefaz_client.settings.env", "production")
    monkeypatch.setattr("app.sefaz_client.settings.infosimples_api_token", None)
    with pytest.raises(HTTPException) as exc:
        consult_nfe("35250801234567890123456789012345678901234567")
    assert exc.value.status_code == 503


def test_consult_nfe_infosimples_post_and_parse(monkeypatch):
    monkeypatch.setattr("app.sefaz_client.settings.infosimples_api_token", "test-token")
    key = "35250801234567890123456789012345678901234567"

    def handler(request: httpx.Request):
        assert request.method == "POST"
        assert request.url.path.endswith("/consultas/sefaz-nfe")
        body = json.loads(request.content.decode())
        assert body["token"] == "test-token"
        assert body["nfe"] == key
        return httpx.Response(
            200,
            json={
                "code": 200,
                "code_message": "Consulta realizada com sucesso",
                "data": {
                    "chave_acesso": key,
                    "nfe": {
                        "situacao": "Autorizada",
                        "valor_total": "7500.50",
                        "data_emissao": "31/08/2026",
                        "emitente": {
                            "cnpj": "12345678000199",
                            "nome_razao_social": "Parceiro LTDA",
                        },
                    },
                },
            },
        )

    transport = httpx.MockTransport(handler)
    original_post = httpx.post

    def mock_post(url, **kwargs):
        with httpx.Client(transport=transport) as client:
            return client.post(url, **kwargs)

    monkeypatch.setattr("app.sefaz_client.httpx.post", mock_post)
    result = consult_nfe(key)
    assert result.status == "AUTHORIZED"
    assert result.mode == "PRODUCTION"
    assert result.provider == "INFOSIMPLES_SEFAZ"
    assert result.gross_amount == Decimal("7500.50")
    assert result.issuer_document == "12345678000199"
    assert result.issuer_name == "Parceiro LTDA"


def test_infosimples_configured_trims_token(monkeypatch):
    monkeypatch.setattr("app.sefaz_client.settings.infosimples_api_token", "  abc  ")
    assert infosimples_configured() is True
