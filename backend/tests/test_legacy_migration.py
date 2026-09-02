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


def test_legacy_migration_apply_leads(client, auth_headers):
    payload = {
        "legacy_source": "letter_v1_apply_leads",
        "entities": {
            "users": [
                {
                    "legacy_id": "affiliate-owner-8",
                    "name": "Parceiro Owner",
                    "email": "owner.lead.apply@example.com",
                    "role": "PARTNER",
                }
            ],
            "leads": [
                {
                    "legacy_id": "customer-100",
                    "name": "Cliente Legacy Lead",
                    "phone": "33991988170",
                    "status": "QUALIFIED",
                    "product_interest": "MARKETPLACE",
                    "owner_user_legacy_id": "affiliate-owner-8",
                    "legacy_document": "03825956539",
                }
            ],
        },
    }
    response = client.post("/api/v1/admin/migration/apply", headers=auth_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["summary"]["created"]["users"] == 1
    assert body["summary"]["created"]["leads"] == 1

    leads = client.get("/api/v1/leads", headers=auth_headers).json()
    migrated = next(item for item in leads if item["name"] == "Cliente Legacy Lead")
    assert migrated["status"] == "QUALIFIED"
    assert migrated["product_interest"] == "MARKETPLACE"
    assert migrated["phone"] == "33991988170"

    maps = client.get(
        "/api/v1/admin/migration/id-map",
        headers=auth_headers,
        params={"legacy_source": "letter_v1_apply_leads", "entity_type": "leads", "legacy_id": "customer-100"},
    )
    assert maps.status_code == 200
    assert len(maps.json()) == 1


def test_legacy_migration_apply_quotas(client, auth_headers):
    payload = {
        "legacy_source": "letter_v1_apply_quotas",
        "entities": {
            "administrators": [
                {
                    "legacy_id": "legacy-adm-quota",
                    "name": "Adm Quota Legacy",
                    "code": "ADM_QUOTA_LEGACY",
                    "document": "77665544000133",
                }
            ],
            "users": [
                {
                    "legacy_id": "supplier-1",
                    "name": "Fornecedor Quota",
                    "email": "supplier.quota.apply@example.com",
                    "role": "QUOTA_SELLER",
                }
            ],
            "quotas": [
                {
                    "legacy_id": "quota-9001",
                    "administrator_legacy_id": "legacy-adm-quota",
                    "group_code": "4696",
                    "quota_code": "9001",
                    "category": "VEHICLE",
                    "credit_value": "51071.00",
                    "outstanding_balance": "52140.00",
                    "premium_value": "18540.00",
                    "installment_due_date": "2026-09-10",
                    "status": "AVAILABLE",
                    "seller_user_legacy_id": "supplier-1",
                }
            ],
        },
    }
    response = client.post("/api/v1/admin/migration/apply", headers=auth_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["summary"]["created"]["quotas"] == 1

    quotas = client.get("/api/v1/quotas", headers=auth_headers).json()
    migrated = next(item for item in quotas if item["group_code"] == "4696" and item["quota_code"] == "9001")
    assert migrated["category"] == "VEHICLE"
    assert float(migrated["credit_value"]) == 51071.0

    maps = client.get(
        "/api/v1/admin/migration/id-map",
        headers=auth_headers,
        params={"legacy_source": "letter_v1_apply_quotas", "entity_type": "quotas", "legacy_id": "quota-9001"},
    )
    assert maps.status_code == 200
    assert len(maps.json()) == 1


def test_legacy_migration_apply_network_nodes(client, auth_headers):
    payload = {
        "legacy_source": "letter_v1_apply_nodes",
        "entities": {
            "users": [
                {
                    "legacy_id": "affiliate-sponsor-1",
                    "name": "Patrocinador Legacy",
                    "email": "sponsor.node.apply@example.com",
                    "role": "PARTNER",
                },
                {
                    "legacy_id": "affiliate-downline-2",
                    "name": "Indicado Legacy",
                    "email": "downline.node.apply@example.com",
                    "role": "PARTNER",
                    "sponsor_legacy_id": "affiliate-sponsor-1",
                },
            ],
            "network_nodes": [
                {
                    "legacy_id": "node-sponsor-1",
                    "user_legacy_id": "affiliate-sponsor-1",
                    "tree_type": "SALES",
                    "referral_code": "SPONSORLEGACY",
                },
                {
                    "legacy_id": "node-downline-2",
                    "user_legacy_id": "affiliate-downline-2",
                    "tree_type": "SALES",
                    "sponsor_user_legacy_id": "affiliate-sponsor-1",
                    "referral_code": "DOWNLINELEGACY",
                },
            ],
        },
    }
    response = client.post("/api/v1/admin/migration/apply", headers=auth_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["summary"]["created"]["users"] == 2
    assert body["summary"]["created"]["network_nodes"] == 2

    nodes = client.get("/api/v1/network/nodes", headers=auth_headers, params={"tree_type": "SALES"}).json()
    sponsor_node = next(item for item in nodes if item["referral_code"] == "SPONSORLEGACY")
    downline_node = next(item for item in nodes if item["referral_code"] == "DOWNLINELEGACY")
    assert sponsor_node["sponsor_user_id"] is None
    assert downline_node["sponsor_user_id"] == sponsor_node["user_id"]

    maps = client.get(
        "/api/v1/admin/migration/id-map",
        headers=auth_headers,
        params={
            "legacy_source": "letter_v1_apply_nodes",
            "entity_type": "network_nodes",
            "legacy_id": "node-downline-2",
        },
    )
    assert maps.status_code == 200
    assert len(maps.json()) == 1


def test_legacy_migration_apply_network_nodes_reuses_user_with_duplicate_email(client, auth_headers):
    payload = {
        "legacy_source": "letter_v1_apply_nodes_dup",
        "entities": {
            "users": [
                {
                    "legacy_id": "supplier-dup-1",
                    "name": "Fornecedor Dup",
                    "email": "dup.network@example.com",
                    "role": "QUOTA_SELLER",
                },
                {
                    "legacy_id": "affiliate-dup-2",
                    "name": "Afiliado Dup",
                    "email": "dup.network@example.com",
                    "role": "PARTNER",
                },
            ],
            "network_nodes": [
                {
                    "legacy_id": "node-supplier-dup-1",
                    "user_legacy_id": "supplier-dup-1",
                    "referral_code": "SUPPLIERDUP",
                },
                {
                    "legacy_id": "node-affiliate-dup-2",
                    "user_legacy_id": "affiliate-dup-2",
                    "referral_code": "AFFILIATEDUP",
                },
            ],
        },
    }
    response = client.post("/api/v1/admin/migration/apply", headers=auth_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["summary"]["created"]["users"] == 1
    assert body["summary"]["reused"]["users"] == 1
    assert body["summary"]["created"]["network_nodes"] == 1
    assert body["summary"]["reused"]["network_nodes"] == 1


def test_legacy_migration_apply_proposals(client, auth_headers):
    payload = {
        "legacy_source": "letter_v1_apply_proposals",
        "entities": {
            "leads": [
                {
                    "legacy_id": "customer-proposal-1",
                    "name": "Cliente Com Proposta",
                    "phone": "33999990001",
                    "status": "QUALIFIED",
                    "product_interest": "MARKETPLACE",
                }
            ],
            "proposals": [
                {
                    "legacy_id": "proposal-customer-1",
                    "product": "MARKETPLACE",
                    "lead_legacy_id": "customer-proposal-1",
                    "requested_amount": "51071.00",
                    "legacy_status_code": 2,
                }
            ],
        },
    }
    response = client.post("/api/v1/admin/migration/apply", headers=auth_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["summary"]["created"]["leads"] == 1
    assert body["summary"]["created"]["proposals"] == 1

    proposals = client.get("/api/v1/proposals", headers=auth_headers).json()
    migrated = next(item for item in proposals if item["product"] == "MARKETPLACE" and float(item["requested_amount"]) == 51071.0)
    assert migrated["status"] == "SUBMITTED"

    maps = client.get(
        "/api/v1/admin/migration/id-map",
        headers=auth_headers,
        params={
            "legacy_source": "letter_v1_apply_proposals",
            "entity_type": "proposals",
            "legacy_id": "proposal-customer-1",
        },
    )
    assert maps.status_code == 200
    assert len(maps.json()) == 1
