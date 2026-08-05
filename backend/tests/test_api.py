from datetime import UTC, datetime, timedelta
from decimal import Decimal


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_and_dashboard(client, auth_headers):
    me = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["role"] == "PLATFORM_ADMIN"
    dashboard = client.get("/api/v1/dashboard", headers=auth_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["modules"] >= 18


def test_financial_guard(client, auth_headers):
    response = client.post("/api/v1/payments/payout", headers=auth_headers)
    assert response.status_code == 503


def test_nina_blocks_mixed_categories(client, auth_headers):
    administrators = client.get("/api/v1/administrators", headers=auth_headers).json()
    administrator_id = administrators[0]["id"]
    vehicle = client.post("/api/v1/quotas", headers=auth_headers, json={
        "administrator_id": administrator_id, "group_code": "2000", "quota_code": "003",
        "category": "VEHICLE", "credit_value": "100000", "outstanding_balance": "50000", "premium_value": "10000"
    }).json()
    real_estate = next(q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["category"] == "REAL_ESTATE")
    response = client.post(
        "/api/v1/nina/validate-combination?target_amount=500000",
        headers=auth_headers, json=[vehicle["id"], real_estate["id"]],
    )
    assert response.status_code == 422
    assert "categoria" in response.json()["detail"].lower()


def test_quota_reservation_blocks_duplicate(client, auth_headers):
    quota = next(q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["status"] == "AVAILABLE")
    first = client.post("/api/v1/reservations", headers=auth_headers, json={"quota_id": quota["id"], "ttl_minutes": 30})
    assert first.status_code == 201
    duplicate = client.post("/api/v1/reservations", headers=auth_headers, json={"quota_id": quota["id"], "ttl_minutes": 30})
    assert duplicate.status_code == 409
    released = client.post(f"/api/v1/reservations/{first.json()['id']}/release", headers=auth_headers)
    assert released.status_code == 200
    assert released.json()["status"] == "RELEASED"


def test_calculation_contract_and_acceptance(client, auth_headers):
    proposal = client.get("/api/v1/proposals", headers=auth_headers).json()[0]
    quotas = [q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["category"] == "REAL_ESTATE"][:2]
    calculation = client.post(f"/api/v1/proposals/{proposal['id']}/calculate", headers=auth_headers, json={
        "quota_ids": [q["id"] for q in quotas], "fee_percent": "10", "start_fee": "1500"
    })
    assert calculation.status_code == 201
    assert calculation.json()["output"]["credit_total"] == "800000.00"
    contract = client.post(f"/api/v1/proposals/{proposal['id']}/contracts", headers=auth_headers, json={
        "calculation_memory_id": calculation.json()["id"]
    })
    assert contract.status_code == 201
    accepted = client.post(f"/api/v1/contracts/{contract.json()['id']}/accept", headers=auth_headers, json={
        "confirmation": True, "ip_address": "127.0.0.1", "user_agent": "pytest"
    })
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"


def test_double_entry_is_balanced_and_idempotent(client, auth_headers):
    payload = {
        "reference": "TEST-LEDGER-001", "event_type": "DEMO_DEPOSIT", "description": "Lançamento de teste",
        "debit_account": "ESCROW_AVAILABLE", "credit_account": "CLIENT_PAYABLE", "amount": "1500.00"
    }
    first = client.post("/api/v1/ledger/transactions", headers=auth_headers, json=payload)
    assert first.status_code == 201
    assert first.json()["amount"] == "1500.00"
    duplicate = client.post("/api/v1/ledger/transactions", headers=auth_headers, json=payload)
    assert duplicate.status_code == 409


def test_lead_update_and_protected_delete(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    updated = client.patch(f"/api/v1/leads/{lead['id']}", headers=auth_headers, json={"status": "PROPOSAL"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "PROPOSAL"
    blocked = client.delete(f"/api/v1/leads/{lead['id']}", headers=auth_headers)
    assert blocked.status_code == 409


def test_contract_pdf_document_and_signature(client, auth_headers):
    contract = client.get("/api/v1/contracts", headers=auth_headers).json()[0]
    pdf = client.get(f"/api/v1/contracts/{contract['id']}/pdf", headers=auth_headers)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    uploaded = client.post("/api/v1/documents", headers=auth_headers, data={
        "entity_type": "contract", "entity_id": contract["id"], "kind": "CONTRACT_PDF"
    }, files={"file": ("contrato.pdf", pdf.content, "application/pdf")})
    assert uploaded.status_code == 201
    assert uploaded.json()["status"] == "QUARANTINED"
    scanned = client.post(f"/api/v1/documents/{uploaded.json()['id']}/mock-scan", headers=auth_headers)
    assert scanned.status_code == 200
    assert scanned.json()["status"] == "CLEAN"
    envelope = client.post(f"/api/v1/contracts/{contract['id']}/signature", headers=auth_headers, json={"signer_email":"cliente@exemplo.com.br"})
    assert envelope.status_code == 201
    signed = client.post(f"/api/v1/signatures/{envelope.json()['id']}/mock-complete", headers=auth_headers, json={"confirmation":True,"ip_address":"127.0.0.1"})
    assert signed.status_code == 200
    assert signed.json()["status"] == "SIGNED"


def test_escrow_webhook_is_idempotent(client, auth_headers):
    account = client.post("/api/v1/escrow/accounts", headers=auth_headers, json={}).json()
    payload = {"event_id":"evt_test_deposit_001","event_type":"FUNDS_CONFIRMED","amount":"10000.00","metadata":{"source":"pytest"}}
    first = client.post(f"/api/v1/escrow/accounts/{account['id']}/mock-webhook", headers=auth_headers, json=payload)
    second = client.post(f"/api/v1/escrow/accounts/{account['id']}/mock-webhook", headers=auth_headers, json=payload)
    assert first.status_code == 200 and first.json()["processed"] is True
    assert second.status_code == 200 and second.json()["processed"] is False
    current = client.get("/api/v1/escrow/accounts", headers=auth_headers).json()[0]
    assert current["available_balance"] == "10000.00"


def test_payout_requires_two_distinct_approvers(client, auth_headers):
    account = client.get("/api/v1/escrow/accounts", headers=auth_headers).json()[0]
    payout = client.post("/api/v1/payouts", headers=auth_headers, json={
        "escrow_account_id":account["id"],"beneficiary_name":"Vendedor Piloto","beneficiary_document":"55555555555",
        "pix_key":"vendedor@pix.com","amount":"2500.00","condition_evidence":{"transfer_confirmed":True,"review_id":"pytest"}
    })
    assert payout.status_code == 201
    assert client.post("/api/v1/auth/step-up", headers=auth_headers, json={"password":"Letter@123"}).status_code == 200
    own = client.post(f"/api/v1/payouts/{payout.json()['id']}/approve", headers=auth_headers, json={"decision":"APPROVE"})
    assert own.status_code == 403
    def login(email):
        token=client.post("/api/v1/auth/login",json={"email":email,"password":"Letter@123"}).json()["access_token"]
        headers={"Authorization":f"Bearer {token}"}
        stepped=client.post("/api/v1/auth/step-up",headers=headers,json={"password":"Letter@123"})
        assert stepped.status_code == 200
        return headers
    first=client.post(f"/api/v1/payouts/{payout.json()['id']}/approve",headers=login("revisor1@letter.com.br"),json={"decision":"APPROVE","comment":"Documentos conferidos"})
    assert first.status_code==200 and first.json()["status"]=="PARTIALLY_APPROVED"
    second=client.post(f"/api/v1/payouts/{payout.json()['id']}/approve",headers=login("revisor2@letter.com.br"),json={"decision":"APPROVE","comment":"Condição precedente confirmada"})
    assert second.status_code==200 and second.json()["status"]=="READY_FOR_PROVIDER"
    assert second.json()["approval_count"]==2


def test_chart_balances_reflect_escrow_and_lock(client, auth_headers):
    balances={item["code"]:item["balance"] for item in client.get("/api/v1/ledger/balances",headers=auth_headers).json()}
    assert balances["ESCROW_CASH"] == "7500.00"
    assert balances["ESCROW_LOCKED"] == "2500.00"
    assert balances["CLIENT_FUNDS_PAYABLE"] == "10000.00"


def test_refresh_token_rotates_and_old_token_is_rejected(client):
    login = client.post("/api/v1/auth/login", json={"email":"parceiro@letter.com.br","password":"Letter@123"})
    assert login.status_code == 200
    old_refresh = login.json()["refresh_token"]
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token":old_refresh})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != old_refresh
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token":old_refresh})
    assert replay.status_code == 401


def test_branch_invitation_and_acceptance(client, auth_headers):
    branch = client.post("/api/v1/admin/branches", headers=auth_headers, json={"name":"Filial Campinas","code":"CPS"})
    assert branch.status_code == 201
    invite = client.post("/api/v1/admin/invitations", headers=auth_headers, json={
        "email":"gestor.campinas@letter.com.br","role":"MANAGER","branch_id":branch.json()["id"]
    })
    assert invite.status_code == 201 and invite.json()["token"]
    accepted = client.post("/api/v1/auth/invitations/accept", json={
        "token":invite.json()["token"],"name":"Gestor Campinas","document":"12345678901","password":"NovaSenha@123"
    })
    assert accepted.status_code == 200
    assert accepted.json()["branch_id"] == branch.json()["id"]


def test_mfa_activation_and_login_challenge(client, auth_headers):
    import pyotp
    setup = client.post("/api/v1/auth/mfa/setup", headers=auth_headers)
    assert setup.status_code == 200
    otp = pyotp.TOTP(setup.json()["secret"]).now()
    assert client.post("/api/v1/auth/mfa/enable", headers=auth_headers, json={"otp":otp}).status_code == 200
    blocked = client.post("/api/v1/auth/login", json={"email":"admin@letter.com.br","password":"Letter@123"})
    assert blocked.status_code == 428
    otp = pyotp.TOTP(setup.json()["secret"]).now()
    allowed = client.post("/api/v1/auth/login", json={"email":"admin@letter.com.br","password":"Letter@123","otp":otp})
    assert allowed.status_code == 200
    otp = pyotp.TOTP(setup.json()["secret"]).now()
    assert client.post("/api/v1/auth/mfa/disable", headers=auth_headers, json={"otp":otp}).status_code == 200


def test_kyc_mock_workflow(client, auth_headers):
    created = client.post("/api/v1/kyc/cases", headers=auth_headers, json={"subject_type":"PERSON","subject_id":"lead-demo"})
    assert created.status_code == 201 and created.json()["status"] == "PENDING"
    decided = client.post(f"/api/v1/kyc/cases/{created.json()['id']}/mock-decision", headers=auth_headers, json={"status":"APPROVED","risk_level":"LOW","notes":"Validação simulada"})
    assert decided.status_code == 200
    assert decided.json()["status"] == "APPROVED" and decided.json()["risk_level"] == "LOW"


def test_sdc_bullet_engine_uses_documented_splits(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id":lead["id"],"product":"SDC","requested_amount":"800000","terms":{}
    }).json()
    quotas = [q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["category"] == "REAL_ESTATE"][:2]
    calculated = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-sdc", headers=auth_headers, json={
        "quota_ids":[q["id"] for q in quotas],"duration_months":12
    })
    assert calculated.status_code == 201
    output = calculated.json()["output"]
    assert calculated.json()["formula_version"] == "sdc-bullet-v1"
    assert output["principal"] == "800000.00"
    assert output["total_interest"] == "432000.00"
    assert output["investor_interest"] == "240000.00"
    assert output["platform_spread"] == "192000.00"
    assert output["start_fee_milestone_1"] == "1500.00"
    assert output["start_fee_milestone_2"] == "22500.00"
    contract = client.post(f"/api/v1/proposals/{proposal['id']}/contracts", headers=auth_headers, json={"calculation_memory_id":calculated.json()["id"]})
    assert contract.status_code == 201
    assert contract.json()["template_version"] == "sdc-bullet-v1"
    assert client.get(f"/api/v1/contracts/{contract.json()['id']}/pdf", headers=auth_headers).content.startswith(b"%PDF")


def test_flash_credit_retail_price_and_balloon(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id":lead["id"],"product":"FLASH_CREDIT","requested_amount":"200000","terms":{}
    }).json()
    calculated = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-flash-credit", headers=auth_headers, json={
        "asset_value":"500000","capital_source":"RETAIL","term_months":60,"ipca_annual_percent":"0"
    })
    assert calculated.status_code == 201
    output = calculated.json()["output"]
    assert output["ltv_percent"] == "40.00"
    assert output["amortization"] == "PRICE"
    assert output["balloon_month"] == 36
    assert float(output["balloon_payment"]) > 0
    assert output["investor_rate_percent"] == "1.60"
    assert output["platform_spread_rate_percent"] == "0.90"


def test_flash_credit_institutional_and_ltv_guard(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id":lead["id"],"product":"FLASH_CREDIT","requested_amount":"200000","terms":{}
    }).json()
    calculated = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-flash-credit", headers=auth_headers, json={
        "asset_value":"800000","capital_source":"INSTITUTIONAL","term_months":36,"ipca_annual_percent":"4.5"
    })
    assert calculated.status_code == 201
    output = calculated.json()["output"]
    assert output["combined_rate_annual_percent"] == "18.50"
    assert output["total_interest"] == "111000.00"
    assert output["management_fee_total"] == "3000.00"
    blocked = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-flash-credit", headers=auth_headers, json={
        "asset_value":"400000","capital_source":"RETAIL","term_months":36,"ipca_annual_percent":"0"
    })
    assert blocked.status_code == 422
    assert "LTV" in blocked.json()["detail"]


def test_five_level_commission_allocation_and_fiscal_hold(client, auth_headers):
    users = client.get("/api/v1/admin/users", headers=auth_headers).json()
    admin = next(u for u in users if u["email"] == "admin@letter.com.br")
    partner = next(u for u in users if u["email"] == "parceiro@letter.com.br")
    root = client.post("/api/v1/network/nodes", headers=auth_headers, json={"user_id":admin["id"],"tree_type":"SALES"})
    assert root.status_code == 201
    child = client.post("/api/v1/network/nodes", headers=auth_headers, json={"user_id":partner["id"],"sponsor_user_id":admin["id"],"tree_type":"SALES"})
    assert child.status_code == 201
    rule = client.post("/api/v1/commission-rules", headers=auth_headers, json={
        "product":"MARKETPLACE","commission_type":"SALES","pool_rate_percent":"10","base_type":"LETTER_FEE"
    })
    assert rule.status_code == 201 and rule.json()["version"] == 1
    entries = client.post("/api/v1/commissions/allocate", headers=auth_headers, json={
        "originator_id":partner["id"],"reference":"SALE-MMN-001","product":"MARKETPLACE",
        "commission_type":"SALES","calculation_base":"100000"
    })
    assert entries.status_code == 201
    assert len(entries.json()) == 2
    assert entries.json()[0]["level"] == 1 and entries.json()[0]["amount"] == "5000.00"
    assert entries.json()[1]["level"] == 2 and entries.json()[1]["amount"] == "2000.00"
    login = client.post("/api/v1/auth/login", json={"email":"parceiro@letter.com.br","password":"Letter@123"}).json()
    partner_headers = {"Authorization":f"Bearer {login['access_token']}"}
    wallet = client.get("/api/v1/wallet/commissions", headers=partner_headers)
    assert wallet.status_code == 200 and wallet.json()[0]["status"] == "PENDING_FISCAL"
    released = client.post("/api/v1/wallet/commissions/release-fiscal", headers=partner_headers, json={
        "reference_month":"2026-08","document_content":"<NFS-e>documento fiscal simulado válido</NFS-e>"
    })
    assert released.status_code == 200 and released.json()["available_balance"] == "5000.00"
    summary = client.get("/api/v1/network/me/summary", headers=partner_headers)
    assert summary.json()["privacy_mode"] == "AGGREGATED"
    assert "names" not in summary.json()


def test_funding_reservation_confirmation_and_profile_guard(client, auth_headers):
    opportunity = client.post("/api/v1/funding/opportunities", headers=auth_headers, json={
        "title":"Pool SDC Piloto","product":"SDC","capital_source":"RETAIL",
        "target_amount":"10000","min_investment":"1000","annual_return_reference":"30"
    })
    assert opportunity.status_code == 201
    investor_login = client.post("/api/v1/auth/login", json={"email":"investidor@letter.com.br","password":"Letter@123"}).json()
    investor_headers = {"Authorization":f"Bearer {investor_login['access_token']}"}
    reservation = client.post(f"/api/v1/funding/opportunities/{opportunity.json()['id']}/reserve", headers=investor_headers, json={"amount":"4000"})
    assert reservation.status_code == 201 and reservation.json()["status"] == "RESERVED"
    confirmed = client.post(f"/api/v1/funding/reservations/{reservation.json()['id']}/mock-confirm", headers=auth_headers)
    assert confirmed.status_code == 200
    assert confirmed.json()["principal"] == "4000.00"
    positions = client.get("/api/v1/funding/positions", headers=investor_headers)
    assert positions.status_code == 200 and len(positions.json()) == 1
    partner_login = client.post("/api/v1/auth/login", json={"email":"parceiro@letter.com.br","password":"Letter@123"}).json()
    partner_headers = {"Authorization":f"Bearer {partner_login['access_token']}"}
    blocked = client.post(f"/api/v1/funding/opportunities/{opportunity.json()['id']}/reserve", headers=partner_headers, json={"amount":"1000"})
    assert blocked.status_code == 403


def test_sdc_billing_schedule_and_idempotent_payment(client, auth_headers):
    contract = next(c for c in client.get("/api/v1/contracts", headers=auth_headers).json() if c["template_version"] == "sdc-bullet-v1")
    schedule = client.post(f"/api/v1/contracts/{contract['id']}/billing", headers=auth_headers, json={"start_date":"2026-01-01"})
    assert schedule.status_code == 201
    assert len(schedule.json()) == 3
    kinds = {row["kind"]:row for row in schedule.json()}
    assert kinds["START_1"]["total_amount"] == "1500.00"
    assert kinds["START_2"]["total_amount"] == "22500.00"
    assert kinds["BULLET"]["total_amount"] == "1232000.00"
    invoice = kinds["START_1"]
    payload = {"event_id":"evt_invoice_start_001","amount":"1500","metadata":{"provider":"pytest"}}
    first = client.post(f"/api/v1/invoices/{invoice['id']}/mock-payment-webhook", headers=auth_headers, json=payload)
    replay = client.post(f"/api/v1/invoices/{invoice['id']}/mock-payment-webhook", headers=auth_headers, json=payload)
    assert first.status_code == 200 and first.json()["processed"] is True and first.json()["invoice_status"] == "PAID"
    assert replay.status_code == 200 and replay.json()["processed"] is False


def test_csv_reconciliation_creates_resolvable_divergence(client, auth_headers):
    invoice = next(i for i in client.get("/api/v1/invoices", headers=auth_headers).json() if i["kind"] == "START_2")
    csv_data = f"invoice_number,amount,payment_date,external_id\n{invoice['invoice_number']},22000.00,2026-02-01,bank_csv_001\n"
    imported = client.post("/api/v1/reconciliation/import", headers=auth_headers, files={"file":("conciliacao.csv",csv_data.encode(),"text/csv")})
    assert imported.status_code == 201
    assert imported.json()["status"] == "DIVERGENT" and imported.json()["divergent_records"] == 1
    items = client.get("/api/v1/reconciliation/items?status=DIVERGENT", headers=auth_headers).json()
    item = next(x for x in items if x["external_event_id"] == "bank_csv_001")
    assert item["reason"] == "AMOUNT_MISMATCH"
    assert client.post("/api/v1/auth/step-up", headers=auth_headers, json={"password":"Letter@123"}).status_code == 200
    resolved = client.post(f"/api/v1/reconciliation/items/{item['id']}/resolve", headers=auth_headers, json={"decision":"IGNORE","note":"Divergência bancária confirmada no piloto"})
    assert resolved.status_code == 200 and resolved.json()["status"] == "RESOLVED"


def test_flash_credit_delinquency_marks_caducity_after_sixty_days(client, auth_headers):
    proposal = next(p for p in client.get("/api/v1/proposals", headers=auth_headers).json() if p["product"] == "FLASH_CREDIT")
    calculation = next(c for c in client.get(f"/api/v1/proposals/{proposal['id']}/calculations", headers=auth_headers).json() if c["formula_version"] == "flash-credit-v1")
    contract = client.post(f"/api/v1/proposals/{proposal['id']}/contracts", headers=auth_headers, json={"calculation_memory_id":calculation["id"]})
    assert contract.status_code == 201
    schedule = client.post(f"/api/v1/contracts/{contract.json()['id']}/billing", headers=auth_headers, json={"start_date":"2026-01-01"})
    assert schedule.status_code == 201 and len(schedule.json()) >= 36
    refreshed = client.post("/api/v1/collections/refresh?as_of=2026-05-05", headers=auth_headers)
    assert refreshed.status_code == 200
    assert any(case["caducity_eligible"] is True and case["days_overdue"] > 60 for case in refreshed.json())
    repeated = client.post("/api/v1/collections/refresh?as_of=2026-05-06", headers=auth_headers)
    assert repeated.status_code == 200
    assert any(case["days_overdue"] > 60 for case in repeated.json())
    actions = client.get("/api/v1/collections/actions", headers=auth_headers)
    assert actions.status_code == 200 and any(a["action_type"] == "OVERDUE_D60" for a in actions.json())


def test_auction_gated_bid_idempotency_and_waterfall(client, auth_headers):
    asset = client.post("/api/v1/recovered-assets", headers=auth_headers, json={
        "title":"Imóvel recuperado piloto","asset_type":"REAL_ESTATE",
        "public_description":"Imóvel residencial disponível para liquidação simulada.",
        "gated_details":{"registry":"Matrícula simulada 123","address":"Endereço restrito"},
        "appraisal_value":"150000","debt_balance":"90000","recovery_costs":"5000",
        "custody_reference":"CUSTODY-AUCTION-001"
    })
    assert asset.status_code == 201 and asset.json()["status"] == "READY"
    now = datetime.now(UTC)
    lot = client.post("/api/v1/auction-lots", headers=auth_headers, json={
        "asset_id":asset.json()["id"],"opening_price":"80000","reserve_price":"100000",
        "min_increment":"5000","platform_fee_percent":"5",
        "starts_at":(now-timedelta(minutes=1)).isoformat(),
        "ends_at":(now+timedelta(minutes=2)).isoformat(),"extension_minutes":5
    })
    assert lot.status_code == 201
    lot_id = lot.json()["id"]
    assert client.post(f"/api/v1/auction-lots/{lot_id}/activate", headers=auth_headers).status_code == 200
    investor_login = client.post("/api/v1/auth/login", json={"email":"investidor@letter.com.br","password":"Letter@123"}).json()
    investor_headers = {"Authorization":f"Bearer {investor_login['access_token']}"}
    assert client.get(f"/api/v1/auction-lots/{lot_id}/gated-details", headers=investor_headers).status_code == 403
    qualified = client.post(f"/api/v1/auction-lots/{lot_id}/qualify", headers=investor_headers, json={"confirmation":True})
    assert qualified.status_code == 201 and qualified.json()["status"] == "APPROVED"
    assert client.get(f"/api/v1/auction-lots/{lot_id}/gated-details", headers=investor_headers).json()["registry"] == "Matrícula simulada 123"
    payload={"amount":"110000","idempotency_key":"auction-bid-event-001"}
    first=client.post(f"/api/v1/auction-lots/{lot_id}/bids",headers=investor_headers,json=payload)
    replay=client.post(f"/api/v1/auction-lots/{lot_id}/bids",headers=investor_headers,json=payload)
    assert first.status_code == 201 and replay.status_code == 201 and first.json()["id"] == replay.json()["id"]
    extended=next(x for x in client.get("/api/v1/auction-lots",headers=auth_headers).json() if x["id"]==lot_id)
    extended_end=datetime.fromisoformat(extended["ends_at"])
    if extended_end.tzinfo is None: extended_end=extended_end.replace(tzinfo=UTC)
    assert extended_end > now + timedelta(minutes=5)
    assert client.post("/api/v1/auth/step-up",headers=auth_headers,json={"password":"Letter@123"}).status_code == 200
    settled=client.post(f"/api/v1/auction-lots/{lot_id}/mock-settle",headers=auth_headers)
    assert settled.status_code == 200
    assert settled.json()["gross_amount"] == "110000.00"
    assert settled.json()["recovery_costs"] == "5000.00"
    assert settled.json()["platform_fee"] == "5500.00"
    assert settled.json()["debt_paid"] == "90000.00"
    assert settled.json()["owner_surplus"] == "9500.00"


def test_tax_closing_creates_exception_for_undocumented_commission(client, auth_headers):
    partner=next(u for u in client.get("/api/v1/admin/users",headers=auth_headers).json() if u["email"]=="parceiro@letter.com.br")
    document=client.post("/api/v1/tax/documents",headers=auth_headers,json={
        "user_id":partner["id"],"reference_month":"2026-08","gross_amount":"5000",
        "tax_amount":"250","content":"<NFS-e>comissão de agosto documento piloto único</NFS-e>"
    })
    assert document.status_code==201 and document.json()["status"]=="VALIDATED"
    closing=client.post("/api/v1/tax/closings",headers=auth_headers,json={"reference_month":"2026-08"})
    assert closing.status_code==201
    assert closing.json()["gross_commissions"]=="7000.00"
    assert closing.json()["documented_amount"]=="5000.00"
    assert closing.json()["eligible_payout"]=="5000.00"
    assert closing.json()["exception_count"]==1
    exceptions=client.get("/api/v1/tax/exceptions",headers=auth_headers).json()
    assert any(x["reason"]=="MISSING_OR_INSUFFICIENT_NFSE" and x["amount"]=="2000.00" for x in exceptions)


def test_marketing_consent_optout_and_delivery_idempotency(client, auth_headers):
    lead=client.get("/api/v1/leads",headers=auth_headers).json()[0]
    template=client.post("/api/v1/communications/templates",headers=auth_headers,json={
        "key":"campaign_welcome","channel":"WHATSAPP","body":"Olá {{name}}, bem-vindo à LETTER!","purpose":"MARKETING"
    })
    assert template.status_code==201 and template.json()["version"]==1
    send={"template_id":template.json()["id"],"subject_type":"LEAD","subject_id":lead["id"],"destination":lead["phone"],"idempotency_key":"communication-event-001","variables":{"name":lead["name"]}}
    assert client.post("/api/v1/communications/send",headers=auth_headers,json=send).status_code==422
    consent={"subject_type":"LEAD","subject_id":lead["id"],"channel":"WHATSAPP","status":"OPT_IN","source":"FORM","evidence":{"ip":"127.0.0.1"}}
    assert client.post("/api/v1/communications/consents",headers=auth_headers,json=consent).status_code==200
    first=client.post("/api/v1/communications/send",headers=auth_headers,json=send)
    replay=client.post("/api/v1/communications/send",headers=auth_headers,json=send)
    assert first.status_code==201 and first.json()["id"]==replay.json()["id"]
    delivered=client.post(f"/api/v1/communications/deliveries/{first.json()['id']}/mock-deliver",headers=auth_headers)
    assert delivered.status_code==200 and delivered.json()["status"]=="DELIVERED"
    consent["status"]="OPT_OUT"
    assert client.post("/api/v1/communications/consents",headers=auth_headers,json=consent).status_code==200
    send["idempotency_key"]="communication-event-002"
    assert client.post("/api/v1/communications/send",headers=auth_headers,json=send).status_code==422


def test_nina_underwriting_explanation_decision_and_ranking(client, auth_headers):
    policy=client.post("/api/v1/nina/policies",headers=auth_headers,json={
        "product":"MARKETPLACE","minimum_score":650,"manual_review_score":720,
        "maximum_ltv_percent":"40","maximum_commitment_percent":"35","rules":{"model":"deterministic-v1"}
    })
    assert policy.status_code==201 and policy.json()["version"]==1
    proposal=next(p for p in client.get("/api/v1/proposals",headers=auth_headers).json() if p["product"]=="MARKETPLACE")
    assessment=client.post(f"/api/v1/nina/proposals/{proposal['id']}/assess",headers=auth_headers,json={
        "policy_id":policy.json()["id"],"monthly_income":"20000","monthly_commitment":"4000",
        "asset_value":"2000000","external_score":760,"document_completeness_percent":"100","kyc_status":"APPROVED"
    })
    assert assessment.status_code==201
    body=assessment.json()
    assert body["score"]==780 and body["recommendation"]=="APPROVE"
    assert body["explanation"]["policy_version"]==1 and body["explanation"]["factors"][0]["factor"]=="KYC"
    assert client.post("/api/v1/auth/step-up",headers=auth_headers,json={"password":"Letter@123"}).status_code==200
    decision=client.post(f"/api/v1/nina/assessments/{body['id']}/decide",headers=auth_headers,json={"decision":"APPROVE","reason":"Score e garantias dentro da política vigente"})
    assert decision.status_code==200 and decision.json()["decision"]=="APPROVE"
    ranking=client.get("/api/v1/nina/quota-ranking?target_amount=800000&category=REAL_ESTATE",headers=auth_headers)
    assert ranking.status_code==200 and ranking.json()[0]["total_credit"]=="800000.00" and ranking.json()[0]["score"]>=900


def test_bi_summary_and_executive_csv(client, auth_headers):
    summary=client.get("/api/v1/bi/summary",headers=auth_headers)
    assert summary.status_code==200
    assert summary.json()["risk"]["assessments"]>=1
    assert Decimal(summary.json()["portfolio"]["invoiced"])>0
    report=client.get("/api/v1/bi/executive-report.csv",headers=auth_headers)
    assert report.status_code==200 and report.content.startswith("\ufeffsection,metric,value".encode("utf-8"))
    assert b"portfolio,invoiced" in report.content


def test_request_security_headers_readiness_and_durable_job_retry(client, auth_headers):
    health=client.get("/api/v1/health",headers={"X-Request-ID":"pytest-request-001"})
    assert health.headers["x-request-id"]=="pytest-request-001"
    assert health.headers["x-content-type-options"]=="nosniff"
    assert health.headers["x-frame-options"]=="DENY"
    assert float(health.headers["x-response-time-ms"])>=0
    ready=client.get("/api/v1/system/readiness")
    assert ready.status_code==200 and ready.json()["database"]=="UP"
    payload={"job_type":"EXECUTIVE_REPORT","idempotency_key":"durable-job-event-001","payload":{"format":"csv"},"max_attempts":2}
    first=client.post("/api/v1/system/jobs",headers=auth_headers,json=payload)
    replay=client.post("/api/v1/system/jobs",headers=auth_headers,json=payload)
    assert first.status_code==201 and replay.json()["id"]==first.json()["id"]
    failed=client.post(f"/api/v1/system/jobs/{first.json()['id']}/process",headers=auth_headers,json={"simulate_failure":True})
    assert failed.json()["status"]=="RETRY_SCHEDULED" and failed.json()["attempts"]==1
    completed=client.post(f"/api/v1/system/jobs/{first.json()['id']}/process",headers=auth_headers,json={"simulate_failure":False})
    assert completed.json()["status"]=="COMPLETED" and completed.json()["attempts"]==2
    metrics=client.get("/api/v1/system/metrics",headers=auth_headers).json()
    assert metrics["completed"]>=1 and metrics["attempts_total"]>=2


def test_operational_jobs_are_tenant_isolated(client, auth_headers):
    from app.core.security import hash_password
    from app.db import SessionLocal
    from app.models import Organization, Role, User
    with SessionLocal() as db:
        org=Organization(name="Tenant Isolado",document="99999999000199")
        db.add(org);db.flush();db.add(User(organization_id=org.id,name="Admin Isolado",email="isolado@letter.com.br",document="99999999999",password_hash=hash_password("Letter@123"),role=Role.PLATFORM_ADMIN));db.commit()
    token=client.post("/api/v1/auth/login",json={"email":"isolado@letter.com.br","password":"Letter@123"}).json()["access_token"]
    isolated_headers={"Authorization":f"Bearer {token}"}
    assert client.get("/api/v1/system/jobs",headers=isolated_headers).json()==[]
    main_jobs=client.get("/api/v1/system/jobs",headers=auth_headers).json()
    assert any(x["idempotency_key"]=="durable-job-event-001" for x in main_jobs)


def test_worker_batch_and_homologation_report(client, auth_headers):
    created=client.post("/api/v1/system/jobs",headers=auth_headers,json={"job_type":"COLLECTION_REFRESH","idempotency_key":"worker-batch-event-001","payload":{},"max_attempts":3})
    assert created.status_code==201 and created.json()["status"]=="PENDING"
    from app.worker import run_once
    result=run_once()
    assert result["selected"]>=1 and result["completed"]>=1
    item=next(x for x in client.get("/api/v1/system/jobs",headers=auth_headers).json() if x["id"]==created.json()["id"])
    assert item["status"]=="COMPLETED"
    report=client.get("/api/v1/system/homologation",headers=auth_headers)
    assert report.status_code==200
    assert report.json()["status"]=="DEVELOPMENT"
    assert report.json()["checks"]["financial_guard"]=="LOCKED"
    assert report.json()["external_providers"]["baas"]=="NOT_CONFIGURED"


def test_rate_limiter_quota_security_event_and_backup(client, auth_headers, tmp_path):
    from app.security_service import SlidingWindowLimiter
    limiter=SlidingWindowLimiter()
    assert limiter.allow("login:test",2)[0] is True
    assert limiter.allow("login:test",2)[0] is True
    blocked=limiter.allow("login:test",2)
    assert blocked[0] is False and blocked[1]>=1
    failed=client.post("/api/v1/auth/login",json={"email":"admin@letter.com.br","password":"senha-incorreta"})
    assert failed.status_code==401
    events=client.get("/api/v1/system/security-events",headers=auth_headers).json()
    assert any(x["event_type"]=="LOGIN_FAILED" and x["severity"]=="MEDIUM" for x in events)
    quota=client.patch("/api/v1/system/quota",headers=auth_headers,json={"jobs_per_day":1})
    assert quota.status_code==200 and quota.json()["jobs_per_day"]==1
    blocked_job=client.post("/api/v1/system/jobs",headers=auth_headers,json={"job_type":"EXECUTIVE_REPORT","idempotency_key":"quota-block-event-001","payload":{},"max_attempts":2})
    assert blocked_job.status_code==429
    client.patch("/api/v1/system/quota",headers=auth_headers,json={"jobs_per_day":1000})
    from app.backup import create_backup,verify_sqlite_backup
    backup_path=tmp_path/"letter-test-backup.db"
    manifest=create_backup(backup_path);verification=verify_sqlite_backup(backup_path)
    assert manifest["sha256"] and manifest["size_bytes"]>0
    assert verification["valid"] is True and verification["tables"]>0


def test_signed_webhooks_provider_sandbox_retry_and_circuit_breaker(client, auth_headers):
    integration=client.post("/api/v1/system/integrations",headers=auth_headers,json={
        "provider":"LetterPay","category":"BAAS","environment":"SANDBOX",
        "base_url":"https://sandbox.letterpay.example","credential":"sandbox-secret-credential"
    })
    assert integration.status_code==201
    provider=integration.json()
    assert provider["health_status"]=="UNKNOWN" and "credential" not in provider
    probe=client.post(f"/api/v1/system/integrations/{provider['id']}/probe",headers=auth_headers,json={"simulate_status":"UP","latency_ms":32})
    assert probe.status_code==200 and probe.json()["health_status"]=="UP" and probe.json()["latency_ms"]==32
    secret="whsec_test_12345678901234567890"
    endpoint=client.post("/api/v1/system/webhook-endpoints",headers=auth_headers,json={
        "integration_id":provider["id"],"name":"ERP Sandbox","target_url":"mock://erp/webhooks",
        "secret":secret,"subscribed_events":["payment.confirmed"],"max_attempts":3
    })
    assert endpoint.status_code==201 and endpoint.json()["subscribed_events"]==["payment.confirmed"]
    payload={"invoice_id":"inv_001","amount":"1500.00"}
    delivery=client.post(f"/api/v1/system/webhook-endpoints/{endpoint.json()['id']}/dispatch",headers=auth_headers,json={
        "event_id":"evt-signed-webhook-001","event_type":"payment.confirmed","payload":payload,"simulate_failure":True
    })
    assert delivery.status_code==201
    body=delivery.json()
    assert body["status"]=="RETRY_SCHEDULED" and body["attempts"]==1 and body["signature"].startswith("t=")
    verified=client.post("/api/v1/system/webhooks/verify",headers=auth_headers,json={"secret":secret,"signature":body["signature"],"payload":payload})
    assert verified.status_code==200 and verified.json()["valid"] is True
    retry=client.post(f"/api/v1/system/webhook-deliveries/{body['id']}/retry",headers=auth_headers,json={"simulate_failure":False})
    assert retry.status_code==200 and retry.json()["status"]=="DELIVERED" and retry.json()["attempts"]==2
    replay=client.post(f"/api/v1/system/webhook-endpoints/{endpoint.json()['id']}/dispatch",headers=auth_headers,json={
        "event_id":"evt-signed-webhook-001","event_type":"payment.confirmed","payload":payload
    })
    assert replay.status_code==201 and replay.json()["id"]==body["id"] and replay.json()["attempts"]==2
    for _ in range(3):
        down=client.post(f"/api/v1/system/integrations/{provider['id']}/probe",headers=auth_headers,json={"simulate_status":"DOWN","latency_ms":900})
    assert down.json()["circuit_status"]=="OPEN" and down.json()["consecutive_failures"]==3
    blocked=client.post(f"/api/v1/system/webhook-endpoints/{endpoint.json()['id']}/dispatch",headers=auth_headers,json={
        "event_id":"evt-signed-webhook-002","event_type":"payment.confirmed","payload":payload
    })
    assert blocked.status_code==503
    recovered=client.post(f"/api/v1/system/integrations/{provider['id']}/probe",headers=auth_headers,json={"simulate_status":"UP","latency_ms":25})
    assert recovered.json()["circuit_status"]=="CLOSED" and recovered.json()["health_status"]=="UP"
    report=client.get("/api/v1/system/homologation",headers=auth_headers).json()
    assert report["external_providers"]["baas"].startswith("SANDBOX:UP:CLOSED:SLA ")


def test_real_connector_allowlist_rotation_incidents_sla_and_dlq_bulk(client,auth_headers):
    blocked=client.post("/api/v1/system/integrations",headers=auth_headers,json={
        "provider":"UnsafeConnector","category":"CUSTOM","environment":"PRODUCTION",
        "base_url":"https://api.safe.example","credential":"production-credential-v1",
        "allowed_hosts":["other.example"],"sla_latency_ms":100
    })
    assert blocked.status_code==422
    created=client.post("/api/v1/system/integrations",headers=auth_headers,json={
        "provider":"SafeConnector","category":"CUSTOM","environment":"SANDBOX",
        "base_url":"https://connector.example","credential":"sandbox-credential-v1",
        "allowed_hosts":["connector.example"],"sla_latency_ms":100
    })
    assert created.status_code==201
    integration=created.json()
    assert integration["allowed_hosts"]==["connector.example"] and integration["credential_version"]==1
    slow=client.post(f"/api/v1/system/integrations/{integration['id']}/probe",headers=auth_headers,json={"simulate_status":"UP","latency_ms":250})
    assert slow.json()["health_status"]=="DEGRADED" and slow.json()["uptime_percent"]==100
    incidents=client.get("/api/v1/system/provider-incidents",headers=auth_headers).json()
    sla=next(x for x in incidents if x["integration_id"]==integration["id"] and x["incident_type"]=="SLA_LATENCY")
    acknowledged=client.post(f"/api/v1/system/provider-incidents/{sla['id']}/action",headers=auth_headers,json={"action":"ACKNOWLEDGE"})
    assert acknowledged.status_code==200 and acknowledged.json()["status"]=="ACKNOWLEDGED"
    healthy=client.post(f"/api/v1/system/integrations/{integration['id']}/probe",headers=auth_headers,json={"simulate_status":"UP","latency_ms":50})
    assert healthy.json()["health_status"]=="UP" and healthy.json()["uptime_percent"]==100
    assert client.post("/api/v1/auth/step-up",headers=auth_headers,json={"password":"Letter@123"}).status_code==200
    rotated=client.post(f"/api/v1/system/integrations/{integration['id']}/rotate-credential",headers=auth_headers,json={"credential":"sandbox-credential-v2"})
    assert rotated.status_code==200 and rotated.json()["credential_version"]==2 and rotated.json()["credential_rotated_at"]
    import httpx
    from app.db import SessionLocal
    from app.integration_service import execute_provider_request
    from app.models import ProviderIntegration
    seen={}
    def handler(request:httpx.Request):
        seen["authorization"]=request.headers.get("authorization");seen["url"]=str(request.url)
        return httpx.Response(200,json={"status":"ok"})
    with SessionLocal() as db:
        item=db.get(ProviderIntegration,integration["id"])
        with httpx.Client(transport=httpx.MockTransport(handler)) as mock_client:
            log=execute_provider_request(db,item,"POST","/v1/ping",{"ping":True},mock_client)
        db.commit()
        assert log.success is True and log.response_code==200
    assert seen["authorization"]=="Bearer sandbox-credential-v2" and seen["url"]=="https://connector.example/v1/ping"
    logs=client.get("/api/v1/system/provider-requests",headers=auth_headers).json()
    assert any(x["integration_id"]==integration["id"] and x["success"] for x in logs)
    endpoint=client.post("/api/v1/system/webhook-endpoints",headers=auth_headers,json={
        "integration_id":integration["id"],"name":"DLQ Sandbox","target_url":"mock://dlq/webhooks",
        "secret":"whsec_dlq_12345678901234567890","subscribed_events":["dlq.test"],"max_attempts":1
    }).json()
    failed=client.post(f"/api/v1/system/webhook-endpoints/{endpoint['id']}/dispatch",headers=auth_headers,json={
        "event_id":"evt-dead-letter-bulk-001","event_type":"dlq.test","payload":{"test":True},"simulate_failure":True
    })
    assert failed.status_code==201 and failed.json()["status"]=="DEAD_LETTER"
    bulk=client.post("/api/v1/system/webhook-deliveries/reprocess-dead-letter",headers=auth_headers,json={"delivery_ids":[failed.json()["id"]]})
    assert bulk.status_code==200 and bulk.json()=={"requested":1,"requeued":1,"skipped":0}


def test_provider_onboarding_secret_vault_mtls_reconciliation_and_evidence(client,auth_headers):
    integration=client.post("/api/v1/system/integrations",headers=auth_headers,json={
        "provider":"OnboardBank","category":"BAAS","environment":"SANDBOX",
        "base_url":"https://onboard-bank.example","credential":"onboard-bank-token-v1",
        "allowed_hosts":["onboard-bank.example"],"sla_latency_ms":500
    }).json()
    assert client.post("/api/v1/auth/step-up",headers=auth_headers,json={"password":"Letter@123"}).status_code==200
    cert=client.post("/api/v1/system/secrets",headers=auth_headers,json={"name":"onboard-bank-cert","backend":"LOCAL_ENCRYPTED","value":"-----BEGIN CERTIFICATE-----TEST-CERTIFICATE-----END CERTIFICATE-----"})
    key=client.post("/api/v1/system/secrets",headers=auth_headers,json={"name":"onboard-bank-key","backend":"LOCAL_ENCRYPTED","value":"-----BEGIN PRIVATE KEY-----TEST-PRIVATE-KEY-----END PRIVATE KEY-----"})
    assert cert.status_code==201 and key.status_code==201
    assert "value" not in cert.json() and cert.json()["version"]==1
    mtls=client.put(f"/api/v1/system/integrations/{integration['id']}/mtls",headers=auth_headers,json={
        "certificate_secret_id":cert.json()["id"],"private_key_secret_id":key.json()["id"],"verify_peer":True,"enabled":True
    })
    assert mtls.status_code==200 and mtls.json()["enabled"] is True
    profile=client.put(f"/api/v1/system/integrations/{integration['id']}/onboarding",headers=auth_headers,json={
        "api_version":"2026-01","authentication_type":"MTLS","health_path":"/v1/health",
        "reconciliation_mode":"CSV_AND_WEBHOOK","checklist":{"contract_signed":True,"dpo_approved":True}
    })
    assert profile.status_code==200 and profile.json()["checklist"]["contract_signed"] is True
    account=client.post("/api/v1/escrow/accounts",headers=auth_headers,json={}).json()
    event={"event_id":"evt_onboard_reconcile_001","event_type":"FUNDS_CONFIRMED","amount":"4321.00","metadata":{"provider":"OnboardBank"}}
    assert client.post(f"/api/v1/escrow/accounts/{account['id']}/mock-webhook",headers=auth_headers,json=event).status_code==200
    divergent_csv="external_id,event_type,amount,status\nevt_onboard_reconcile_001,FUNDS_CONFIRMED,4321.00,SETTLED\nevt_missing,FUNDS_CONFIRMED,100.00,SETTLED\n"
    divergent=client.post(f"/api/v1/system/integrations/{integration['id']}/reconciliation/import",headers=auth_headers,files={"file":("divergent.csv",divergent_csv,"text/csv")})
    assert divergent.status_code==201 and divergent.json()["divergent_items"]==1
    items=client.get(f"/api/v1/system/reconciliation-runs/{divergent.json()['id']}/items",headers=auth_headers).json()
    assert {x["match_status"] for x in items}=={"MATCHED","DIVERGENT"}
    matched_csv="external_id,event_type,amount,status\nevt_onboard_reconcile_001,FUNDS_CONFIRMED,4321.00,SETTLED\n"
    matched=client.post(f"/api/v1/system/integrations/{integration['id']}/reconciliation/import",headers=auth_headers,files={"file":("matched.csv",matched_csv,"text/csv")})
    assert matched.status_code==201 and matched.json()["status"]=="COMPLETED"
    client.post(f"/api/v1/system/integrations/{integration['id']}/probe",headers=auth_headers,json={"simulate_status":"UP","latency_ms":40})
    evidence=client.post(f"/api/v1/system/integrations/{integration['id']}/evidence",headers=auth_headers)
    assert evidence.status_code==201 and len(evidence.json())==6
    assert all(x["result"]=="PASS" and len(x["evidence_hash"])==64 for x in evidence.json())
    profiles=client.get("/api/v1/system/onboarding-profiles",headers=auth_headers).json()
    assert next(x for x in profiles if x["integration_id"]==integration["id"])["status"]=="READY_FOR_HOMOLOGATION"


def test_sandbox_provider_adapters_registry_execution_and_idempotency(client,auth_headers):
    catalog=client.get("/api/v1/system/adapter-catalog",headers=auth_headers)
    assert catalog.status_code==200
    specs={item["category"]:item for item in catalog.json()}
    assert set(specs)=={"BAAS","KYC","SIGNATURE","COMMUNICATIONS","TAX"}
    cases={
        "BAAS":("create_account",{"document":"12345678901"}),
        "KYC":("start_verification",{"subject_id":"person-001"}),
        "SIGNATURE":("create_envelope",{"signer_email":"signer@example.com"}),
        "COMMUNICATIONS":("send_template",{"destination":"+5511999999999","template":"welcome","channel":"WHATSAPP"}),
        "TAX":("issue_document",{"document":"12345678000199","amount":"1500.00"}),
    }
    created=[]
    for category,(operation,payload) in cases.items():
        host=f"{category.lower()}.adapter.example"
        integration=client.post("/api/v1/system/integrations",headers=auth_headers,json={
            "provider":f"{category} Sandbox Adapter","category":category,"environment":"SANDBOX",
            "base_url":f"https://{host}","credential":f"sandbox-{category.lower()}-credential",
            "allowed_hosts":[host],"sla_latency_ms":1000
        })
        assert integration.status_code==201
        integration_id=integration.json()["id"]
        body={"operation":operation,"payload":payload,"idempotency_key":f"adapter-{category.lower()}-event-001"}
        first=client.post(f"/api/v1/system/integrations/{integration_id}/adapter/execute",headers=auth_headers,json=body)
        second=client.post(f"/api/v1/system/integrations/{integration_id}/adapter/execute",headers=auth_headers,json=body)
        assert first.status_code==201 and second.status_code==201
        assert first.json()["id"]==second.json()["id"]
        assert len(first.json()["input_hash"])==64 and first.json()["adapter_version"]=="sandbox-v1"
        created.append(first.json())
        conflict=client.post(f"/api/v1/system/integrations/{integration_id}/adapter/execute",headers=auth_headers,json={**body,"payload":{"changed":True}})
        assert conflict.status_code==409
    communication=next(x for x in created if x["category"]=="COMMUNICATIONS")
    assert communication["output"]["destination_masked"]=="***9999" and "destination" not in communication["output"]
    executions=client.get("/api/v1/system/adapter-executions",headers=auth_headers)
    assert executions.status_code==200 and len(executions.json())>=5
    invalid=client.post(f"/api/v1/system/integrations/{created[0]['integration_id']}/adapter/execute",headers=auth_headers,json={"operation":"unsupported_operation","payload":{},"idempotency_key":"adapter-invalid-001"})
    assert invalid.status_code==422
    production=client.post("/api/v1/system/integrations",headers=auth_headers,json={
        "provider":"Production Without Official Adapter","category":"KYC","environment":"PRODUCTION",
        "base_url":"https://production.adapter.example","credential":"production-credential-placeholder",
        "allowed_hosts":["production.adapter.example"],"sla_latency_ms":1000
    }).json()
    blocked=client.post(f"/api/v1/system/integrations/{production['id']}/adapter/execute",headers=auth_headers,json={"operation":"start_verification","payload":{"subject_id":"person-002"},"idempotency_key":"adapter-production-001"})
    assert blocked.status_code==409


def test_adapter_certification_approvals_and_go_live_gate(client,auth_headers):
    integration=client.post("/api/v1/system/integrations",headers=auth_headers,json={
        "provider":"GoLive Bank","category":"BAAS","environment":"SANDBOX",
        "base_url":"https://golive-bank.example","credential":"golive-bank-credential",
        "allowed_hosts":["golive-bank.example"],"sla_latency_ms":500
    }).json()
    integration_id=integration["id"]
    first=client.post(f"/api/v1/system/integrations/{integration_id}/certify",headers=auth_headers)
    assert first.status_code==201 and first.json()["status"]=="FAIL"
    assert first.json()["total_checks"]==8 and len(first.json()["report_hash"])==64
    assert first.json()["report"]["checks"]["adapter_contract_registered"] is True
    for area in ("SECURITY","LEGAL","COMPLIANCE","OPERATIONS"):
        approval=client.put(f"/api/v1/system/integrations/{integration_id}/go-live-approval",headers=auth_headers,json={"area":area,"decision":"APPROVED","notes":f"{area} aprovado no sandbox controlado"})
        assert approval.status_code==200 and approval.json()["decision"]=="APPROVED"
    approvals=client.get("/api/v1/system/go-live-approvals",headers=auth_headers).json()
    assert {x["area"] for x in approvals if x["integration_id"]==integration_id}=={"SECURITY","LEGAL","COMPLIANCE","OPERATIONS"}
    invalid=client.put(f"/api/v1/system/integrations/{integration_id}/go-live-approval",headers=auth_headers,json={"area":"FINANCE","decision":"APPROVED","notes":"Área não permitida para este gate"})
    assert invalid.status_code==422
    decision=client.post(f"/api/v1/system/integrations/{integration_id}/go-live/evaluate",headers=auth_headers)
    assert decision.status_code==201 and decision.json()["status"]=="BLOCKED"
    assert "integration_not_production" in decision.json()["blockers"]
    assert "official_adapter_not_registered" in decision.json()["blockers"]
    assert "certification_not_passed" in decision.json()["blockers"]
    decisions=client.get("/api/v1/system/go-live-decisions",headers=auth_headers).json()
    assert any(x["integration_id"]==integration_id and x["status"]=="BLOCKED" for x in decisions)
