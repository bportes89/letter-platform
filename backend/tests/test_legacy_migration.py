import json
from pathlib import Path


SAMPLE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "legacy_migration_sample.json"


def test_legacy_migration_dry_run_endpoint(client, auth_headers):
    payload = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    response = client.post("/api/v1/admin/migration/dry-run", headers=auth_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "DRY_RUN"
    assert body["legacy_source"] == "letter_v1"
    assert body["status"] == "COMPLETED"
    assert body["summary"]["ready"] is True
    assert body["summary"]["entity_counts"]["users"] == 1


def test_legacy_migration_dry_run_detects_duplicate_email(client, auth_headers):
    payload = {
        "legacy_source": "letter_v1",
        "entities": {
            "users": [
                {
                    "legacy_id": "dup-1",
                    "name": "Admin Duplicado",
                    "email": "admin@letter.com.br",
                    "role": "PARTNER",
                }
            ]
        },
    }
    response = client.post("/api/v1/admin/migration/dry-run", headers=auth_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["summary"]["ready"] is False
    assert any("E-mail já existe" in issue["message"] for issue in body["summary"]["issues"])


def test_legacy_migration_runs_list(client, auth_headers):
    payload = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    client.post("/api/v1/admin/migration/dry-run", headers=auth_headers, json=payload)
    runs = client.get("/api/v1/admin/migration/runs", headers=auth_headers)
    assert runs.status_code == 200
    assert len(runs.json()) >= 1


def test_legacy_migration_apply_organizations_only(client, auth_headers):
    payload = {
        "legacy_source": "letter_v1_apply",
        "entities": {
            "organizations": [
                {
                    "legacy_id": "org-apply-1",
                    "name": "Org Apply Test",
                    "document": "11222333000144",
                }
            ]
        },
    }
    response = client.post("/api/v1/admin/migration/apply", headers=auth_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "APPLY"
    assert body["status"] == "COMPLETED"
    assert body["summary"]["created"]["organizations"] == 1

    maps = client.get(
        "/api/v1/admin/migration/id-map",
        headers=auth_headers,
        params={"legacy_source": "letter_v1_apply", "entity_type": "organizations", "legacy_id": "org-apply-1"},
    )
    assert maps.status_code == 200
    assert len(maps.json()) == 1
    assert maps.json()[0]["legacy_id"] == "org-apply-1"


def test_legacy_migration_apply_administrators_and_users(client, auth_headers):
    payload = {
        "legacy_source": "letter_v1_apply_users",
        "entities": {
            "administrators": [
                {
                    "legacy_id": "legacy-adm-77",
                    "name": "Administradora Legacy Apply",
                    "code": "LEGACY_APPLY_ADM",
                    "document": "88776655000144",
                }
            ],
            "users": [
                {
                    "legacy_id": "legacy-user-88",
                    "name": "Parceiro Legacy Apply",
                    "email": "parceiro.legacy.apply@example.com",
                    "document": "12312312387",
                    "role": "PARTNER",
                }
            ],
        },
    }
    response = client.post("/api/v1/admin/migration/apply", headers=auth_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["summary"]["created"]["administrators"] == 1
    assert body["summary"]["created"]["users"] == 1
    assert "password_policy" in body["summary"]

    users = client.get("/api/v1/admin/users", headers=auth_headers).json()
    assert any(u["email"] == "parceiro.legacy.apply@example.com" for u in users)

    maps = client.get(
        "/api/v1/admin/migration/id-map",
        headers=auth_headers,
        params={"legacy_source": "letter_v1_apply_users", "entity_type": "users", "legacy_id": "legacy-user-88"},
    )
    assert maps.status_code == 200
    assert len(maps.json()) == 1


def test_legacy_migration_apply_reuses_existing_administrator_code(client, auth_headers):
    payload = {
        "legacy_source": "letter_v1_apply_reuse",
        "entities": {
            "administrators": [
                {
                    "legacy_id": "legacy-adm-embracon",
                    "name": "Embracon Legacy",
                    "code": "EMBRACON",
                    "document": "99000000000001",
                }
            ]
        },
    }
    response = client.post("/api/v1/admin/migration/apply", headers=auth_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["reused"]["administrators"] == 1
    assert body["summary"]["created"].get("administrators", 0) == 0
