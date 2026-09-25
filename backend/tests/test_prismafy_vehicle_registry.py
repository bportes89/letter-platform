from app.prismafy_vehicle_registry import restrictions_from_prismafy_results
from app.vehicle_registry_service import query_vehicle_registry


def test_restrictions_from_gravame_block():
    rows = restrictions_from_prismafy_results(
        {"gravame": {"possuiGravame": True, "situacao": "Gravame ativo"}}
    )
    assert any(r["type"] == "FIDUCIARY_LIEN" for r in rows)


def test_query_vehicle_registry_uses_prismafy_when_configured(monkeypatch):
    monkeypatch.setattr("app.vehicle_registry_service.valid_stamp_consult_configured", lambda: True)

    def fake_prismafy(**kwargs):
        return {
            "plate": kwargs["plate"],
            "uf": kwargs["uf"],
            "vehicle_class": kwargs["vehicle_class"],
            "registry_source": "PRISMAFY_VALID_STAMP",
            "queried_at": "2026-01-01T00:00:00+00:00",
            "restrictions": [],
            "blocking_restrictions": [],
            "cleared": True,
            "note": "ok",
            "prismafy_executions": [],
            "prismafy_results": {},
        }

    monkeypatch.setattr(
        "app.prismafy_vehicle_registry.query_vehicle_registry_prismafy",
        fake_prismafy,
    )
    out = query_vehicle_registry(plate="ABC1D23", uf="MG", vehicle_class="LIGHT", mode="auto")
    assert out["registry_source"] == "PRISMAFY_VALID_STAMP"
    assert out["cleared"] is True
