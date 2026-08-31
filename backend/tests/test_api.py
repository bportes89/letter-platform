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
    patch = client.patch(f"/api/v1/quotas/{quota['id']}", headers=auth_headers, json={"installment_due_date": "2026-09-10"})
    assert patch.status_code == 200
    scan = client.post(f"/api/v1/quotas/{quota['id']}/nina-scan", headers=auth_headers)
    assert scan.status_code == 200 and scan.json()["status"] == "CLEARED"
    first = client.post("/api/v1/reservations", headers=auth_headers, json={"quota_id": quota["id"], "ttl_minutes": 60})
    assert first.status_code == 201
    duplicate = client.post("/api/v1/reservations", headers=auth_headers, json={"quota_id": quota["id"], "ttl_minutes": 60})
    assert duplicate.status_code == 409
    released = client.post(f"/api/v1/reservations/{first.json()['id']}/release", headers=auth_headers)
    assert released.status_code == 200
    assert released.json()["status"] == "RELEASED"


def test_marketplace_esteira1_and_esteira2(client, auth_headers):
    quota = next(q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["status"] == "AVAILABLE")
    client.patch(
        f"/api/v1/quotas/{quota['id']}",
        headers=auth_headers,
        json={"installment_due_date": "2026-09-10"},
    )
    profile = {
        "monthly_income": "50000",
        "monthly_commitment": "5000",
        "asset_value": "900000",
        "asset_year": 2020,
    }
    esteira1 = client.post(
        "/api/v1/marketplace/esteira-1/assess",
        headers=auth_headers,
        json={"quota_id": quota["id"], **profile},
    )
    assert esteira1.status_code == 200
    body1 = esteira1.json()
    assert body1["esteira"] == "SELF_SELECT"
    assert body1["quota"]["quota_id"] == quota["id"]
    assert "message" in body1

    esteira2 = client.post(
        "/api/v1/marketplace/esteira-2/match",
        headers=auth_headers,
        json={"target_amount": "800000", "category": "REAL_ESTATE", **profile},
    )
    assert esteira2.status_code == 200
    body2 = esteira2.json()
    assert body2["esteira"] == "NINA_CURATED"
    assert isinstance(body2["matches"], list)


def test_quota_lock_requires_nina_scan(client, auth_headers):
    quota = next(q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["status"] == "AVAILABLE")
    blocked = client.post("/api/v1/reservations", headers=auth_headers, json={"quota_id": quota["id"], "ttl_minutes": 60})
    assert blocked.status_code == 422


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
    quitcon = calculated.json()["quitcon_sdc"]
    assert quitcon is not None
    assert quitcon["card"]["saldo_devedor_atual"] == output["maturity_total"]
    assert len(quitcon["projecao_temporal"]["linhas"]) == 6
    assert quitcon["projecao_temporal"]["tabela"]["quitacao_12_meses"]["valor_quitcon_estimado_vp"] == "1100000.00"
    contract = client.post(f"/api/v1/proposals/{proposal['id']}/contracts", headers=auth_headers, json={"calculation_memory_id":calculated.json()["id"]})
    assert contract.status_code == 201
    assert contract.json()["template_version"] == "sdc-bullet-v1"
    assert client.get(f"/api/v1/contracts/{contract.json()['id']}/pdf", headers=auth_headers).content.startswith(b"%PDF")


def test_sdc_fund_track_passes_full_spread_to_fund(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "SDC", "requested_amount": "800000", "terms": {}
    }).json()
    quotas = [q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["category"] == "REAL_ESTATE"][:2]
    calculated = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-sdc", headers=auth_headers, json={
        "quota_ids": [q["id"] for q in quotas], "duration_months": 12, "capital_source": "FUND"
    })
    assert calculated.status_code == 201
    output = calculated.json()["output"]
    assert calculated.json()["formula_version"] == "sdc-bullet-v2"
    assert output["capital_source"] == "FUND"
    assert output["total_interest"] == "432000.00"
    assert output["investor_interest"] == "432000.00"
    assert output["platform_spread"] == "0.00"


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
    assert len(output["monthly_schedule"]) == 36
    assert output["monthly_schedule"][0]["investor_share"] == "3200.00"
    assert output["monthly_schedule"][0]["platform_share"] == "1800.00"


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
    assert output["monthly_rate_percent"] == "2.50"
    assert output["amortization"] == "PRICE"
    assert output["fruicao_rate_basis"] == "FIXED_2_5_PERCENT_ALL_TRACKS"
    assert output["investor_rate_percent"] == "2.50"
    assert output["platform_spread_rate_percent"] == "0.00"
    assert output["monthly_schedule"][0]["interest"] == "5000.00"
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
    sefaz_status = client.get("/api/v1/wallet/commissions/sefaz/status", headers=partner_headers)
    assert sefaz_status.status_code == 200 and sefaz_status.json()["enabled"] is True
    nf_xml = (
        '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
        "<chNFe>35250801234567890123456789012345678901234567</chNFe>"
        "<xNome>Parceiro Demonstracao</xNome></NFe>"
    )
    released = client.post("/api/v1/wallet/commissions/release-fiscal", headers=partner_headers, json={
        "reference_month": "2026-08",
        "document_content": nf_xml,
        "gross_amount": "5000.00",
    })
    assert released.status_code == 200 and released.json()["available_balance"] == "5000.00"
    assert released.json()["access_key"] == "35250801234567890123456789012345678901234567"
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
    assert "invoice_processor" in first.json()
    assert first.json()["invoice_processor"]["status"] == "SUCCESS"
    receipts = client.get(f"/api/v1/contracts/{contract['id']}/receipts", headers=auth_headers)
    assert receipts.status_code == 200 and len(receipts.json()) >= 1
    receipt = receipts.json()[0]
    assert receipt["vault_s3_uri"].startswith("s3://letter-vault-private/partners/")
    assert receipt["email_status"] == "SENT_D+0"
    processor = first.json()["invoice_processor"]
    assert processor["endpoint"] == "/api/v1/finops/billing/invoice-processor"
    assert processor["data"]["demonstrativo_contabil_legal"]["indexacao_ipca_anual"] is False
    assert replay.status_code == 200 and replay.json()["processed"] is False


def test_finops_invoice_processor_v3_canonical_payload():
    from app.invoice_processor_service import MotorFaturamentoEFiscalLETTERV3

    engine = MotorFaturamentoEFiscalLETTERV3()
    payload = engine.calcular_e_disparar_recibo_automatico(
        id_contrato="FLASH_CAPITAL_POOL_091",
        id_parceiro="PARTNER_LIVRE_0922",
        volume_total_pago=Decimal("21334.80"),
        mes_referencia=13,
        base_fruicao_juros=Decimal("10543.20"),
        base_amortizacao_recompra=Decimal("10791.60"),
    )
    demo = payload["demonstrativo_contabil_legal"]
    assert demo["valor_total_liquidado_baas"] == "21334.80"
    assert demo["fração_taxa_de_fruição_tributavel"] == "10543.20"
    assert demo["fração_amortização_da_recompra_isenta"] == "10791.60"
    assert demo["imposto_retido_spe_lucro_presumido"] == "1194.54"
    assert demo["indexacao_ipca_anual"] is True
    storage = payload["mapeamento_armazenamento_nuvem"]
    assert storage["rota_area_logada_cliente_db"] == (
        "/api/v1/customer/dashboard/contracts/FLASH_CAPITAL_POOL_091/receipts/recibo_fruicao_mes_13.pdf"
    )
    assert storage["rota_interna_bucket_s3_admin"] == (
        "s3://letter-vault-private/partners/PARTNER_LIVRE_0922/contracts/FLASH_CAPITAL_POOL_091/receipts/recibo_fruicao_mes_13.pdf"
    )
    assert payload["disparo_transacional_workflow"]["trigger_email_automatico"] == "SENT_D+0"


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
    calculation = next(c for c in client.get(f"/api/v1/proposals/{proposal['id']}/calculations", headers=auth_headers).json() if c["formula_version"].startswith("flash-"))
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


def test_nina_asset_timeline_dual_approval_documents_and_price_floor(client,auth_headers):
    delinquency=next(x for x in client.get("/api/v1/collections/cases",headers=auth_headers).json() if x["caducity_eligible"])
    created=client.post("/api/v1/nina-asset/cases",headers=auth_headers,json={
        "delinquency_case_id":delinquency["id"],"appraisal_value_avm":"500000.00",
        "photo_storage_reference":"s3://letter-sandbox/assets/property-001/",
        "daily_reduction_amount":"500.00"
    })
    assert created.status_code==201
    case=created.json();case_id=case["id"]
    assert case["stage"]=="EXECUTION_REVIEW" and case["days_overdue"]>=61
    assert case["legal_hold"] is True and case["auction_status"]=="BLOCKED"
    events=client.get(f"/api/v1/nina-asset/events?case_id={case_id}",headers=auth_headers).json()
    assert {x["event_key"] for x in events}>={"TIMELINE_D1","TIMELINE_D6","TIMELINE_D16","TIMELINE_D30","TIMELINE_D61"}
    blocked=client.post(f"/api/v1/nina-asset/cases/{case_id}/apply-gate",headers=auth_headers,json={"gate":"CADUCITY"})
    assert blocked.status_code==428
    assert client.post("/api/v1/auth/step-up",headers=auth_headers,json={"password":"Letter@123"}).status_code==200
    missing=client.post(f"/api/v1/nina-asset/cases/{case_id}/apply-gate",headers=auth_headers,json={"gate":"CADUCITY"})
    assert missing.status_code==409

    def stepped(email):
        token=client.post("/api/v1/auth/login",json={"email":email,"password":"Letter@123"}).json()["access_token"]
        headers={"Authorization":f"Bearer {token}"}
        assert client.post("/api/v1/auth/step-up",headers=headers,json={"password":"Letter@123"}).status_code==200
        return headers

    reviewer=stepped("revisor1@letter.com.br")
    for gate in ("CADUCITY","AUCTION_PUBLICATION"):
        first=client.post(f"/api/v1/nina-asset/cases/{case_id}/approvals",headers=auth_headers,json={"gate":gate,"decision":"APPROVED","notes":"Aprovado para simulação controlada e sem efeito jurídico"})
        second=client.post(f"/api/v1/nina-asset/cases/{case_id}/approvals",headers=reviewer,json={"gate":gate,"decision":"APPROVED","notes":"Documentos revisados exclusivamente para o ambiente sandbox"})
        assert first.status_code==201 and second.status_code==201
        applied=client.post(f"/api/v1/nina-asset/cases/{case_id}/apply-gate",headers=auth_headers,json={"gate":gate})
        assert applied.status_code==200
    ready=applied.json()
    assert ready["stage"]=="AUCTION_SANDBOX_READY"
    assert ready["current_auction_price"]=="400000.00"
    assert ready["legal_hold"] is True
    document=client.post(f"/api/v1/nina-asset/cases/{case_id}/documents",headers=auth_headers,json={"document_type":"AUCTION_EDICT","variables":{"registry":"Matrícula sandbox 123","occupancy":"OCCUPIED"}})
    assert document.status_code==201 and document.json()["status"]=="DRAFT_LEGAL_REVIEW"
    assert len(document.json()["content_hash"])==64 and "SEM EFEITO JURÍDICO" in document.json()["content"]["disclaimer"]
    pdf=client.get(f"/api/v1/nina-asset/documents/{document.json()['id']}/pdf",headers=auth_headers)
    assert pdf.status_code==200 and pdf.headers["content-type"]=="application/pdf" and pdf.content.startswith(b"%PDF")
    reduced=client.post("/api/v1/nina-asset/auction/reduce-prices",headers=auth_headers)
    assert reduced.status_code==200
    updated=next(x for x in reduced.json() if x["id"]==case_id)
    assert updated["current_auction_price"]=="399500.00"
    approvals=client.get("/api/v1/nina-asset/approvals",headers=auth_headers).json()
    assert len([x for x in approvals if x["case_id"]==case_id])==4


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


def test_dual_acceptance_quota_transfer_and_safe_release_gate(client,auth_headers):
    contract=client.get("/api/v1/contracts",headers=auth_headers).json()[0]
    templates=[]
    for kind,title in (("CHECKOUT_INITIAL","Aceite inicial do checkout"),("TRANSFER_RELEASE","Confirmação crítica de titularidade")):
        created=client.post("/api/v1/acceptance-templates",headers=auth_headers,json={"acceptance_type":kind,"version":1,"title":title,"body":f"Texto jurídico versionado para {title}, sujeito a revisão e registro de evidências."})
        assert created.status_code==201 and len(created.json()["body_hash"])==64
        templates.append(created.json())
    step=client.post("/api/v1/auth/step-up",headers=auth_headers,json={"password":"Letter@123"})
    assert step.status_code==200
    for template in templates:
        approved=client.post(f"/api/v1/acceptance-templates/{template['id']}/approve",headers=auth_headers)
        assert approved.status_code==200 and approved.json()["legal_review_status"]=="APPROVED"
    incomplete=client.post(f"/api/v1/contracts/{contract['id']}/checkout-acceptance",headers=auth_headers,json={"confirmation":True,"read_full_contract":False})
    assert incomplete.status_code==422
    initial=client.post(f"/api/v1/contracts/{contract['id']}/checkout-acceptance",headers=auth_headers,json={"confirmation":True,"read_full_contract":True,"ip_address":"127.0.0.1","user_agent":"pytest"})
    assert initial.status_code==201 and initial.json()["acceptance_type"]=="CHECKOUT_INITIAL" and len(initial.json()["evidence_hash"])==64
    replay=client.post(f"/api/v1/contracts/{contract['id']}/checkout-acceptance",headers=auth_headers,json={"confirmation":True,"read_full_contract":True})
    assert replay.status_code==201 and replay.json()["id"]==initial.json()["id"]
    evidence=[]
    for kind in ("STATEMENT","PROTOCOL","ASSIGNMENT"):
        uploaded=client.post("/api/v1/documents",headers=auth_headers,data={"entity_type":"contract","entity_id":contract["id"],"kind":kind},files={"file":(f"{kind.lower()}.pdf",b"%PDF-1.4\n% seller evidence\n", "application/pdf")})
        assert uploaded.status_code==201;evidence.append(uploaded.json()["id"])
    ocr=client.post(f"/api/v1/contracts/{contract['id']}/seller-evidence-audit",headers=auth_headers,json={
        "buyer_document":"12345678901","seller_document":"98765432100","statement_document_id":evidence[0],"protocol_document_id":evidence[1],"assignment_document_id":evidence[2],
        "statement_ocr_text":"Extrato oficial: cota CONTEMPLADA", "protocol_ocr_text":"PROTOCOLO: ADM-2026-9911",
        "assignment_ocr_text":"Termo 123.456.789-01 e 987.654.321-00 com FIRMA reconhecida por AUTENTICIDADE em CARTORIO"})
    assert ocr.status_code==201 and ocr.json()["status"]=="OCR_PASSED_PENDING_REVIEW"
    reviewed=client.post(f"/api/v1/seller-evidence-audits/{ocr.json()['id']}/review",headers=auth_headers,json={"decision":"APPROVE","notes":"Lastros conferidos por revisor humano"})
    assert reviewed.status_code==200 and reviewed.json()["status"]=="APPROVED"
    opened=client.post(f"/api/v1/contracts/{contract['id']}/transfer-verification",headers=auth_headers,json={"administrator_reference":"ADM-TRANSFER-2026-001"})
    assert opened.status_code==201 and opened.json()["status"]=="AUDIT_WINDOW_OPEN" and opened.json()["payout_unlocked"] is False
    jobs=client.get("/api/v1/system/jobs",headers=auth_headers).json()
    kinds={x["job_type"] for x in jobs if opened.json()["id"] in x["idempotency_key"]}
    assert kinds=={"QUOTA_AUDIT_WINDOW_STARTED","QUOTA_AUDIT_REMINDER_12H","QUOTA_AUDIT_REMINDER_2H"}
    missing=client.post(f"/api/v1/transfer-verifications/{opened.json()['id']}/confirm-release",headers=auth_headers,json={"logged_into_administrator":True,"quota_in_buyer_name":False,"authorize_release":True})
    assert missing.status_code==422
    confirmed=client.post(f"/api/v1/transfer-verifications/{opened.json()['id']}/confirm-release",headers=auth_headers,json={"logged_into_administrator":True,"quota_in_buyer_name":True,"authorize_release":True,"biometric_reference":"bio-provider-ref-001"})
    assert confirmed.status_code==201 and confirmed.json()["acceptance_type"]=="TRANSFER_RELEASE"
    readiness=client.get(f"/api/v1/transfer-verifications/{opened.json()['id']}/release-readiness",headers=auth_headers).json()
    assert readiness=={"verification_id":opened.json()["id"],"status":"BUYER_CONFIRMED","payout_unlocked":True,"automatic_release_on_silence":False,"requires_manual_review":False}


def test_structured_property_ltv_iq_two_phases_and_registry_gate(client,auth_headers):
    rejected=client.post("/api/v1/structured-properties",headers=auth_headers,json={"buyer_document":"12345678901","seller_document":"98765432100","has_lien_debt":True,"unregistered_construction":True,"land_appraisal_value":"300000","future_appraisal_value":"500000","estimated_debt":"200000"})
    assert rejected.status_code==422
    created=client.post("/api/v1/structured-properties",headers=auth_headers,json={"buyer_document":"12345678901","seller_document":"98765432100","has_lien_debt":True,"unregistered_construction":True,"land_appraisal_value":"300000","future_appraisal_value":"500000","estimated_debt":"80000"})
    assert created.status_code==201
    case=created.json();assert case["route"]=="UNREGISTERED_CONSTRUCTION" and case["gross_payout"]=="200000.00" and case["phase1_amount"]=="120000.00" and case["phase2_amount"]=="80000.00" and case["legal_hold"] is True
    doc=client.post("/api/v1/documents",headers=auth_headers,data={"entity_type":"structured_property","entity_id":case["id"],"kind":"IQ_PAYOFF"},files={"file":("iq.pdf",b"%PDF-1.4\n% payoff\n","application/pdf")}).json()
    attached=client.post(f"/api/v1/structured-properties/{case['id']}/iq-document",headers=auth_headers,json={"document_id":doc["id"]})
    assert attached.status_code==200 and attached.json()["iq_status"]=="DOCUMENT_PENDING_REVIEW"
    assert client.post("/api/v1/auth/step-up",headers=auth_headers,json={"password":"Letter@123"}).status_code==200
    assert client.post(f"/api/v1/structured-properties/{case['id']}/iq-approve",headers=auth_headers).json()["iq_status"]=="SANDBOX_SETTLEMENT_APPROVED"
    phase1=client.post(f"/api/v1/structured-properties/{case['id']}/phase-1-release",headers=auth_headers)
    assert phase1.status_code==200 and phase1.json()["phase_status"]=="PHASE1_SANDBOX_RELEASED" and phase1.json()["registration_deadline_at"]
    jobs=client.get("/api/v1/system/jobs",headers=auth_headers).json();kinds={x["job_type"] for x in jobs if f"property:{case['id']}:" in x["idempotency_key"]}
    assert kinds=={"PROPERTY_REGISTRATION_90D_STARTED","PROPERTY_REGISTRATION_REMINDER_30D","PROPERTY_REGISTRATION_REMINDER_7D","PROPERTY_REGISTRATION_REMINDER_1D"}
    registry=client.post("/api/v1/documents",headers=auth_headers,data={"entity_type":"structured_property","entity_id":case["id"],"kind":"REGISTERED_PROPERTY"},files={"file":("matricula.pdf",b"%PDF-1.4\n% registry\n","application/pdf")}).json()
    submitted=client.post(f"/api/v1/structured-properties/{case['id']}/registration",headers=auth_headers,json={"document_id":registry["id"]})
    assert submitted.json()["phase_status"]=="REGISTRATION_PENDING_REVIEW"
    approved=client.post(f"/api/v1/structured-properties/{case['id']}/registration-approve",headers=auth_headers)
    assert approved.json()["phase_status"]=="PHASE2_SANDBOX_READY" and approved.json()["legal_hold"] is True
    pdf=client.get(f"/api/v1/structured-properties/{case['id']}/registry-requirement.pdf",headers=auth_headers)
    assert pdf.status_code==200 and pdf.content.startswith(b"%PDF")


def test_flash_credit_pj_route_policy_and_valid_stamp(client,auth_headers):
    proposal=next(x for x in client.get("/api/v1/proposals",headers=auth_headers).json() if x["product"]=="FLASH_CREDIT")
    invalid=client.post(f"/api/v1/flash-credit/proposals/{proposal['id']}/parties",headers=auth_headers,json={"borrower_cnpj":"12345678901","property_owner_type":"PF","property_owner_document":"12345678901","liveness_reference":"bio-1","consent_confirmation":True})
    assert invalid.status_code==422
    mismatch=client.post(f"/api/v1/flash-credit/proposals/{proposal['id']}/parties",headers=auth_headers,json={"borrower_cnpj":"12345678000199","property_owner_type":"PJ_THIRD_PARTY","property_owner_document":"99887766000155","legal_representative_document":"12345678901","liveness_reference":"bio-2","qsa_representative_match":False,"consent_confirmation":True})
    assert mismatch.status_code==409
    route=client.post(f"/api/v1/flash-credit/proposals/{proposal['id']}/parties",headers=auth_headers,json={"borrower_cnpj":"12345678000199","property_owner_type":"PJ_THIRD_PARTY","property_owner_document":"99887766000155","legal_representative_document":"12345678901","liveness_reference":"bio-3","qsa_representative_match":True,"consent_confirmation":True})
    assert route.status_code==200 and route.json()["route"]=="THIRD_PARTY_PJ_QSA"
    policy=client.post("/api/v1/flash-credit/policies",headers=auth_headers,json={"version":2}).json()
    assert client.post("/api/v1/auth/step-up",headers=auth_headers,json={"password":"Letter@123"}).status_code==200
    assert client.post(f"/api/v1/flash-credit/policies/{policy['id']}/approve",headers=auth_headers).json()["status"]=="ACTIVE"
    calc=client.post(f"/api/v1/proposals/{proposal['id']}/calculate-flash-credit",headers=auth_headers,json={"asset_value":"600000","capital_source":"RETAIL","term_months":36,"ipca_annual_percent":"4.5"})
    assert calc.status_code==201 and calc.json()["formula_version"]=="flash-capital-v3" and calc.json()["output"]["borrower_eligibility"]=="PJ_ONLY"
    stamp_payload={**route.json(),"asset_type":"REAL_ESTATE","documents":{"MATRICULA_ENOTARIADO":"hash-matricula","LAUDO_AVALIACAO":"hash-laudo","SERASA":"hash-serasa","BACEN":"hash-bacen"}}
    stamp=client.post("/api/v1/valid-stamps",headers=auth_headers,json={"entity_type":"proposal","entity_id":proposal["id"],"purpose":"FLASH_CREDIT_PARTIES","payload":stamp_payload})
    assert stamp.status_code==201 and len(stamp.json()["chain_hash"])==64
    verified=client.get(f"/api/v1/valid-stamps/{stamp.json()['stamp_code']}/verify",headers=auth_headers).json()
    assert verified["integrity_valid"] is True and verified["legal_effect"]=="EVIDENCE_RECORD_NOT_DIGITAL_CERTIFICATE"


def test_lss_clickwrap_subscription_allocation_and_cancellation(client,auth_headers):
    terms=client.post("/api/v1/lss/terms",headers=auth_headers,json={"code":"LSS-B2B","version":51,"title":"Termos SaaS LSS","body":"Termos empresariais versionados do LSS, com recorrência, cancelamento e trilha de aceite sujeita à revisão jurídica."}).json()
    plan=client.post("/api/v1/lss/plans",headers=auth_headers,json={"code":"LSS-PRO","name":"LSS Profissional","monthly_price":"199.90","central_share_percent":"70","network_pool_percent":"30"}).json()
    payload={"plan_id":plan["id"],"terms_template_id":terms["id"],"company_name":"Empresa Teste Ltda","company_cnpj":"12345678000199","representative_name":"Representante Teste","representative_document":"12345678901","scroll_completed":True,"terms_accepted":True,"recurring_authorized":True,"verification_reference":"otp-sandbox-001"}
    assert client.post("/api/v1/lss/subscriptions",headers=auth_headers,json=payload).status_code==409
    assert client.post("/api/v1/auth/step-up",headers=auth_headers,json={"password":"Letter@123"}).status_code==200
    assert client.post(f"/api/v1/lss/terms/{terms['id']}/approve",headers=auth_headers).json()["legal_review_status"]=="APPROVED"
    missing=client.post("/api/v1/lss/subscriptions",headers=auth_headers,json={**payload,"scroll_completed":False})
    assert missing.status_code==422
    subscribed=client.post("/api/v1/lss/subscriptions",headers=auth_headers,json=payload)
    assert subscribed.status_code==201 and subscribed.json()["status"]=="ACTIVE_SANDBOX" and len(subscribed.json()["acceptance_hash"])==64
    allocation=client.get(f"/api/v1/lss/plans/{plan['id']}/allocation-preview",headers=auth_headers).json()
    assert allocation=={"monthly_price":"199.90","central_share":"139.93","network_pool":"59.97","execution":"PREVIEW_ONLY"}
    cancelled=client.post(f"/api/v1/lss/subscriptions/{subscribed.json()['id']}/cancel",headers=auth_headers)
    assert cancelled.status_code==200 and cancelled.json()["status"]=="CANCELLATION_SCHEDULED" and cancelled.json()["cancel_at_period_end"] is True


def test_flash_simulator_four_scenarios_and_settlement_quote(client,auth_headers):
    params = client.get("/api/v1/finops/flash-capital/simulation-params", headers=auth_headers)
    assert params.status_code == 200
    assert "2,5% a.m." in params.json()["labels"]["funds"]

    updated = client.put("/api/v1/finops/flash-capital/simulation-params", headers=auth_headers, json={
        "institutional_rate_annual": "15",
        "retail_rate_monthly": "2.8",
    })
    assert updated.status_code == 200
    assert updated.json()["institutional_rate_annual"] == "15.00"

    simulation=client.post("/api/v1/finops/flash-capital/simulate",headers=auth_headers,json={"asset_value":"1000000","ipca_projected_percent":"4.5"})
    assert simulation.status_code == 200
    assert simulation.json()["institutional_rate_annual"] == "15.00"
    simulation=client.post("/api/v1/public/flash-credit/simulate",json={"asset_value":"1000000","ipca_projected_percent":"4.5"})
    assert simulation.status_code==200
    body=simulation.json();assert body["principal"]=="400000.00" and body["ltv_percent"]=="40.00" and len(body["scenarios"])==4
    assert body["platform_fee"]=="40000.00" and body["itbi_provision"]=="12000.00" and body["net_payout"]=="348000.00"
    assert body["partner_commission_base"]=="348000.00" and body["interest_basis"]=="NOMINAL_PRINCIPAL"
    for rows in body["scenarios"].values():
        assert len(rows)==36 and rows[-1]["settlement_balance"]=="0.00"
    assert client.post("/api/v1/public/flash-credit/simulate",json={"asset_value":"1000000","requested_amount":"400000.01"}).status_code==422
    curve=client.post("/api/v1/public/flash-credit/settlement-curve",json={"principal":"400000","track":"POOL","balloon":True}).json()
    assert len(curve["curve"])==31 and curve["curve"][0]["installment"]==6 and curve["execution"]=="SIMULATION_ONLY"
    proposal=next(x for x in client.get("/api/v1/proposals",headers=auth_headers).json() if x["product"]=="FLASH_CREDIT")
    calculations=client.get(f"/api/v1/proposals/{proposal['id']}/calculations",headers=auth_headers).json();calculation=calculations[0]
    contracts=client.get("/api/v1/contracts",headers=auth_headers).json();contract=next((x for x in contracts if x["proposal_id"]==proposal["id"]),None)
    if contract is None:contract=client.post(f"/api/v1/proposals/{proposal['id']}/contracts",headers=auth_headers,json={"calculation_memory_id":calculation["id"]}).json()
    quote=client.post(f"/api/v1/contracts/{contract['id']}/early-settlement",headers=auth_headers,json={"current_installment":14,"track":"FUNDS","balloon":False,"ipca_projected_percent":"4.5"})
    assert quote.status_code==201 and quote.json()["status"]=="QUOTE_ONLY_SANDBOX" and len(quote.json()["calculation_hash"])==64
    client.put("/api/v1/finops/flash-capital/simulation-params", headers=auth_headers, json={
        "institutional_rate_annual": "14",
        "retail_rate_monthly": "2.5",
    })


def test_finops_signed_events_are_idempotent_and_never_move_funds(client,auth_headers):
    import time
    from app.core.config import settings
    from app.integration_service import sign_webhook,canonical_payload
    event={"event_id":"finops-event-0001","event_type":"asset.caducidade_executed","aggregate_id":"FC-0982","payload":{"days_overdue":61,"avm":"1000000.00"}}
    signature=sign_webhook(settings.secret_key,int(time.time()),canonical_payload(event))
    headers={**auth_headers,"X-Letter-Signature":signature}
    first=client.post("/api/v1/finops/events",headers=headers,json=event);second=client.post("/api/v1/finops/events",headers=headers,json=event)
    assert first.status_code==202 and second.status_code==202 and first.json()["id"]==second.json()["id"]
    assert first.json()["decision"]=="BLOCKED_REQUIRES_DUAL_LEGAL_APPROVAL" and first.json()["execution_mode"]=="SANDBOX_NO_FUNDS"
    tampered=client.post("/api/v1/finops/events",headers=headers,json={**event,"payload":{"days_overdue":62}})
    assert tampered.status_code==401
    provider={"event_id":"finops-event-0002","event_type":"sdc.provider.payout","aggregate_id":"SDC-9981","payload":{"liveness_reference":"sandbox","amount":"45000.00"}}
    provider_signature=sign_webhook(settings.secret_key,int(time.time()),canonical_payload(provider))
    payout=client.post("/api/v1/finops/events",headers={**auth_headers,"X-Letter-Signature":provider_signature},json=provider)
    assert payout.status_code==202 and payout.json()["decision"]=="BLOCKED_PENDING_BIOMETRY_AND_DUAL_APPROVAL"
    split=client.post("/api/v1/finops/sdc/bullet-split-preview",headers=auth_headers,json={"capital":"100000","turnover_days":45,"commission_pool":"4000","level3_available":False})
    assert split.status_code==200
    data=split.json();assert data["bullet_interest"]=="3750.00" and data["investor_total"]=="103750.00"
    assert data["split"]=={"master_franchisee":"2000.00","direct_seller":"1400.00","upline_level_1":"280.00","upline_level_2":"200.00","holding_residual":"120.00"}
    assert data["execution"]=="PREVIEW_ONLY_NO_FUNDS"


def test_nina_routing_real_estate_prenotations_demography_and_committee_stamp(client,auth_headers):
    policy=client.post("/api/v1/nina-routing/policies",headers=auth_headers,json={"version":1,"population_threshold":100000,"income_per_capita_threshold":"30000","tapaf_amount":"1500"})
    assert policy.status_code==201
    assert client.post("/api/v1/auth/step-up",headers=auth_headers,json={"password":"Letter@123"}).status_code==200
    approved=client.post(f"/api/v1/nina-routing/policies/{policy.json()['id']}/approve",headers=auth_headers)
    assert approved.status_code==200 and approved.json()["status"]=="ACTIVE"
    proposal=next(x for x in client.get("/api/v1/proposals",headers=auth_headers).json() if x["product"]=="FLASH_CREDIT")
    vehicle=client.post(f"/api/v1/nina-routing/proposals/{proposal['id']}/assess",headers=auth_headers,json={"asset_type":"VEHICLE","municipality_code":"3100000","population":500000,"income_per_capita":"50000","risk_flags":["PF_NEGATIVE"],"tapaf_evidence_reference":"tapaf-sandbox-1"})
    assert vehicle.status_code==201 and vehicle.json()["status"]=="BLOCKED" and "RISK_RESCUE_REQUIRES_REAL_ESTATE" in vehicle.json()["blockers"]
    judicial=client.post(f"/api/v1/nina-routing/proposals/{proposal['id']}/assess",headers=auth_headers,json={"asset_type":"REAL_ESTATE","municipality_code":"3100000","population":500000,"income_per_capita":"50000","encumbrances":["JUDICIAL_BLOCK"],"risk_flags":["PJ_NEGATIVE"],"tapaf_evidence_reference":"tapaf-sandbox-2"})
    assert judicial.json()["status"]=="BLOCKED" and "JUDICIAL_ENCUMBRANCE" in judicial.json()["blockers"]
    routed=client.post(f"/api/v1/nina-routing/proposals/{proposal['id']}/assess",headers=auth_headers,json={"asset_type":"REAL_ESTATE","municipality_code":"3100000","population":500000,"income_per_capita":"50000","encumbrances":["BANK_MORTGAGE"],"risk_flags":["PARTNER_NEGATIVE"],"tapaf_evidence_reference":"tapaf-sandbox-3"})
    assert routed.status_code==201 and routed.json()["product_route"]=="FLASH_CREDIT" and routed.json()["capital_route"]=="FUNDS" and routed.json()["status"]=="PENDING_COMMITTEE_REVIEW"
    final=client.post(f"/api/v1/nina-routing/assessments/{routed.json()['id']}/approve",headers=auth_headers)
    assert final.status_code==200 and final.json()["status"]=="COMMITTEE_APPROVED_EVIDENCE_STAMPED" and final.json()["physical_appraisal_required"] is True
    stamps=client.get("/api/v1/valid-stamps",headers=auth_headers).json()
    assert any(x["entity_id"]==routed.json()["id"] and x["purpose"]=="COMMITTEE_ROUTING_APPROVAL" for x in stamps)
    sources=client.get("/api/v1/nina-routing/source-policy",headers=auth_headers).json()
    assert "MASS_PJE_SCRAPING" in sources["blocked"] and sources["execution"]=="POLICY_ONLY_NO_SCRAPING"


def test_sdc_pool_investor_rate_campaign_override(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "SDC", "requested_amount": "800000", "terms": {}
    }).json()
    quotas = [q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["category"] == "REAL_ESTATE"][:2]
    calculated = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-sdc", headers=auth_headers, json={
        "quota_ids": [q["id"] for q in quotas], "duration_months": 12, "capital_source": "POOL",
        "pool_investor_rate_percent": "3.5",
    })
    assert calculated.status_code == 201
    output = calculated.json()["output"]
    assert output["investor_interest"] == "336000.00"
    assert output["platform_spread"] == "96000.00"
    assert output["total_interest"] == "432000.00"


def test_flash_pool_investor_rate_campaign_override(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "FLASH_CREDIT", "requested_amount": "200000", "terms": {}
    }).json()
    calculated = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-flash-credit", headers=auth_headers, json={
        "asset_value": "500000", "capital_source": "RETAIL", "term_months": 36,
        "ipca_annual_percent": "0", "pool_investor_rate_percent": "2.0",
    })
    assert calculated.status_code == 201
    output = calculated.json()["output"]
    assert output["investor_rate_percent"] == "2.00"
    assert output["platform_spread_rate_percent"] == "0.50"
    assert output["monthly_rate_percent"] == "2.50"
    assert output["pool_investor_rate_source"] == "MANUAL_CAMPAIGN_OVERRIDE"


def test_flash_pool_investor_tier_up_to_100k(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "FLASH_CREDIT", "requested_amount": "200000", "terms": {}
    }).json()
    calculated = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-flash-credit", headers=auth_headers, json={
        "asset_value": "500000", "capital_source": "RETAIL", "term_months": 36,
        "ipca_annual_percent": "0", "pool_investment_amount": "80000",
    })
    assert calculated.status_code == 201
    output = calculated.json()["output"]
    assert output["investor_rate_percent"] == "1.60"
    assert output["platform_spread_rate_percent"] == "0.90"
    assert output["pool_investor_tier"] == "FLAT"
    assert output["pool_investor_tax_status"] == "EXEMPT_NOT_WITHHELD"


def test_flash_pool_investor_tier_above_100k(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "FLASH_CREDIT", "requested_amount": "200000", "terms": {}
    }).json()
    calculated = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-flash-credit", headers=auth_headers, json={
        "asset_value": "500000", "capital_source": "RETAIL", "term_months": 36,
        "ipca_annual_percent": "0", "pool_investment_amount": "150000",
    })
    assert calculated.status_code == 201
    output = calculated.json()["output"]
    assert output["investor_rate_percent"] == "1.60"
    assert output["platform_spread_rate_percent"] == "0.90"
    assert output["pool_investor_tier"] == "FLAT"
    assert output["pool_investor_tax_status"] == "EXEMPT_NOT_WITHHELD"


def test_sdc_pool_investor_tier_auto(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "SDC", "requested_amount": "800000", "terms": {}
    }).json()
    quotas = [q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["category"] == "REAL_ESTATE"][:2]
    calculated = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-sdc", headers=auth_headers, json={
        "quota_ids": [q["id"] for q in quotas], "duration_months": 12, "capital_source": "POOL",
        "pool_investment_amount": "120000",
    })
    assert calculated.status_code == 201
    output = calculated.json()["output"]
    assert output["pool_investor_rate_percent"] == "1.6"
    assert output["pool_investor_tier"] == "FLAT"
    assert output["pool_investor_tax_status"] == "EXEMPT_NOT_WITHHELD"
    assert output["investor_interest"] == "153600.00"
    assert output["platform_spread"] == "278400.00"


def test_flash_capital_canonical_fee_and_commission_base(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "FLASH_CREDIT", "requested_amount": "400000", "terms": {}
    }).json()
    calculated = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-flash-credit", headers=auth_headers, json={
        "asset_value": "1000000", "capital_source": "RETAIL", "term_months": 36, "ipca_annual_percent": "0",
    })
    assert calculated.status_code == 201
    output = calculated.json()["output"]
    assert calculated.json()["formula_version"] == "flash-capital-v3"
    assert output["principal"] == "400000.00"
    assert output["platform_fee"] == "40000.00"
    assert output["itbi_provision"] == "12000.00"
    assert output["net_payout"] == "348000.00"
    assert output["partner_commission_base"] == "348000.00"
    assert output["interest_basis"] == "NOMINAL_PRINCIPAL"
    assert output["monthly_payment"] == price_payment_check("400000", "2.5", 36)


def price_payment_check(principal: str, rate_percent: str, months: int) -> str:
    from decimal import Decimal, ROUND_HALF_UP
    p = Decimal(principal)
    rate = Decimal(rate_percent) / Decimal("100")
    factor = (Decimal("1") + rate) ** months
    payment = (p * rate * factor / (factor - Decimal("1"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(payment)


def test_sdc_vehicle_registry_blocks_valid_stamp(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "SDC", "requested_amount": "200000", "terms": {}
    }).json()
    assert client.post("/api/v1/auth/step-up", headers=auth_headers, json={"password": "Letter@123"}).status_code == 200
    payload = {
        "asset_type": "VEHICLE",
        "tapaf_evidence_reference": "tapaf-pay-001",
        "vehicle": {"plate": "ABC1D2B", "uf": "MG", "vehicle_class": "LIGHT"},
        "documents": {
            "CRLV": "hash-crlv", "FIPE_MOLICAR": "hash-fipe", "LAUDO_AVALIACAO": "hash-laudo",
            "SERASA": "hash-serasa", "BACEN": "hash-bacen",
        },
    }
    blocked = client.post("/api/v1/valid-stamps", headers=auth_headers, json={
        "entity_type": "proposal", "entity_id": proposal["id"],
        "purpose": "SDC_VEHICLE_COLLATERAL", "payload": payload,
    })
    assert blocked.status_code == 409 and "restrição" in blocked.json()["detail"].lower()
    cleared = client.post("/api/v1/vehicles/registry-check", headers=auth_headers, json={
        "plate": "ABC1234", "uf": "MG", "vehicle_class": "LIGHT",
    })
    assert cleared.status_code == 200 and cleared.json()["cleared"] is True


def test_sdc_vehicle_routing_registry_at_tapaf(client, auth_headers):
    policy = client.post("/api/v1/nina-routing/policies", headers=auth_headers, json={
        "version": 2, "population_threshold": 100000, "income_per_capita_threshold": "30000", "tapaf_amount": "1500",
    })
    client.post("/api/v1/auth/step-up", headers=auth_headers, json={"password": "Letter@123"})
    client.post(f"/api/v1/nina-routing/policies/{policy.json()['id']}/approve", headers=auth_headers)
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "SDC", "requested_amount": "300000", "terms": {},
    }).json()
    blocked = client.post(f"/api/v1/nina-routing/proposals/{proposal['id']}/assess", headers=auth_headers, json={
        "asset_type": "VEHICLE", "municipality_code": "3100000", "population": 500000,
        "income_per_capita": "50000", "tapaf_evidence_reference": "tapaf-veh-1",
        "vehicle_plate": "XYZ1D2A", "vehicle_uf": "SP", "vehicle_class": "HEAVY",
    })
    assert blocked.status_code == 201
    assert blocked.json()["status"] == "BLOCKED"
    assert "VEHICLE_REGISTRY_RESTRICTION" in blocked.json()["blockers"]


def _valid_pre_analysis_documents(**overrides):
    base = [
        {"code": "EXTRATO_BANCARIO_6M", "filename": "extrato.pdf", "dpi": 300, "present": True},
        {"code": "PGDAS_DRE", "filename": "pgdas.pdf", "dpi": 300, "present": True},
        {"code": "DECORE_CRC", "filename": "decore.pdf", "dpi": 300, "present": True},
        {"code": "MATRICULA_OU_CRLV", "filename": "matricula.pdf", "dpi": 300, "present": True},
        {"code": "LAUDO_AVM", "filename": "avm.pdf", "dpi": 300, "present": True},
    ]
    if overrides:
        by_code = {d["code"]: d for d in base}
        for code, patch in overrides.items():
            by_code[code] = {**by_code[code], **patch}
        return list(by_code.values())
    return base


def _sample_extratos(monthly_credit=50000):
    return {f"2026-{m:02d}": [{"valor": monthly_credit, "tipo_credito": "PIX_RECEBIDO", "mesmo_titular_TED_bool": False}] for m in range(1, 7)}


def test_pre_analysis_v6_documents_tapaf_and_engine(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "SDC", "requested_amount": "150000", "terms": {},
    }).json()

    pending = client.post("/api/v1/finops/pre-analysis/validate-documents", headers=auth_headers, json={
        "proposal_id": proposal["id"],
        "documents": _valid_pre_analysis_documents(LAUDO_AVM={"present": False}),
    })
    assert pending.status_code == 200
    assert pending.json()["status"] == "PENDING_DOCUMENTS"
    assert any(e["code"] == "LAUDO_AVM" for e in pending.json()["documents"]["errors"])

    validated = client.post("/api/v1/finops/pre-analysis/validate-documents", headers=auth_headers, json={
        "proposal_id": proposal["id"], "documents": _valid_pre_analysis_documents(),
    })
    assert validated.status_code == 200 and validated.json()["status"] == "DOCUMENTS_OK"

    tapaf = client.post("/api/v1/finops/pre-analysis/generate-tapaf", headers=auth_headers, json={"proposal_id": proposal["id"]})
    assert tapaf.status_code == 200
    ui = tapaf.json()["interface_checkout_tapaf"]
    assert ui["valor_nominal_taxa"] == "1500.00"
    assert ui["botao_habilitado"] is False
    assert "TAPAF" in ui["texto_explicativo_tooltip_interrogacao"]
    assert "manifesto_html" in ui

    blocked = client.post("/api/v1/finops/pre-analysis/tapaf-checkout-accept", headers=auth_headers, json={
        "proposal_id": proposal["id"], "scroll_completed": False, "checkbox_1": True, "checkbox_2": True,
    })
    assert blocked.status_code == 422

    accepted = client.post("/api/v1/finops/pre-analysis/tapaf-checkout-accept", headers=auth_headers, json={
        "proposal_id": proposal["id"], "scroll_completed": True, "checkbox_1": True, "checkbox_2": True,
    })
    assert accepted.status_code == 200 and accepted.json()["status"] == "TAPAF_CHECKOUT_ACCEPTED"

    paid = client.post("/api/v1/finops/pre-analysis/tapaf-payment-webhook", headers=auth_headers, json={
        "proposal_id": proposal["id"], "event_id": "tapaf-webhook-001", "amount": "1500.00",
    })
    assert paid.status_code == 200 and paid.json()["status"] == "TAPAF_PAID"

    settlement = client.get(
        "/api/v1/finops/tapaf/settlements/lookup",
        headers=auth_headers,
        params={"entity_type": "pre_analysis_pauta", "entity_id": paid.json()["id"]},
    )
    assert settlement.status_code == 200
    body = settlement.json()
    assert body["total_brl"] == "1500.00"
    assert body["lote_a_api_reserve_brl"] == "300.00"
    assert body["lote_b_franchise_spread_brl"] == "1200.00"
    assert len(body["inventory"]["providers"]) >= 5

    policy = client.get("/api/v1/finops/tapaf/split-policy", headers=auth_headers)
    assert policy.status_code == 200
    assert policy.json()["lote_a_api_reserve_brl"] == "300.00"

    engine = client.post("/api/v1/finops/pre-analysis/run-engine", headers=auth_headers, json={
        "proposal_id": proposal["id"],
        "adm_nome": "ANCORA",
        "extratos_6_meses_data": _sample_extratos(50000),
        "parcela_simulada": "8000",
        "valor_avaliacao_bem": "200000",
        "saldo_devedor_cotas": "150000",
        "ano_fabricacao_bem": 2020,
    })
    assert engine.status_code == 200
    assert engine.json()["result"]["status_core"] == "APROVADO_COMPLIANCE_NINA"
    assert engine.json()["status"] == "APPROVED_VALID_STAMP"
    assert "resumo_fiduciario_interno_oculto_para_o_fundo" not in engine.json()["result"]

    pauta = client.get(f"/api/v1/finops/pre-analysis/{proposal['id']}", headers=auth_headers)
    assert pauta.status_code == 200
    assert pauta.json()["valid_stamp_hash"]
    assert "resumo_fiduciario_interno_oculto_para_o_fundo" not in (pauta.json()["client_result"] or {})

    help_flash = client.get("/api/v1/help/what-is-flash-capital")
    assert help_flash.status_code == 200 and "Flash Capital" in help_flash.json()["title"]


def test_flash_capital_tapaf_and_valid_stamp(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "FLASH_CREDIT", "requested_amount": "400000", "terms": {},
    }).json()

    validated = client.post("/api/v1/finops/pre-analysis/validate-documents", headers=auth_headers, json={
        "proposal_id": proposal["id"], "documents": _valid_pre_analysis_documents(),
    })
    assert validated.status_code == 200 and validated.json()["status"] == "DOCUMENTS_OK"

    client.post("/api/v1/finops/pre-analysis/tapaf-checkout-accept", headers=auth_headers, json={
        "proposal_id": proposal["id"], "scroll_completed": True, "checkbox_1": True, "checkbox_2": True,
    })
    paid = client.post("/api/v1/finops/pre-analysis/tapaf-payment-webhook", headers=auth_headers, json={
        "proposal_id": proposal["id"], "event_id": "tapaf-flash-001", "amount": "1500.00",
    })
    assert paid.status_code == 200 and paid.json()["status"] == "TAPAF_PAID"

    engine = client.post("/api/v1/finops/pre-analysis/run-engine", headers=auth_headers, json={
        "proposal_id": proposal["id"],
        "asset_type": "REAL_ESTATE",
        "extratos_6_meses_data": _sample_extratos(50000),
        "parcela_simulada": "10000",
        "valor_avaliacao_bem": "1000000",
    })
    assert engine.status_code == 200
    assert engine.json()["result"]["status_core"] == "APROVADO_COMPLIANCE_NINA"
    assert engine.json()["status"] == "APPROVED_VALID_STAMP"
    assert engine.json()["result"]["ltv_percent"] == "40.00"

    pauta = client.get(f"/api/v1/finops/pre-analysis/{proposal['id']}", headers=auth_headers)
    assert pauta.status_code == 200 and pauta.json()["valid_stamp_hash"]

    stamps = client.get("/api/v1/valid-stamps", headers=auth_headers).json()
    assert any(s["purpose"] == "FLASH_CAPITAL_PARTIES" for s in stamps)


def test_pre_analysis_v6_income_margin_bifurcation(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "SDC", "requested_amount": "300000", "terms": {},
    }).json()
    client.post("/api/v1/finops/pre-analysis/validate-documents", headers=auth_headers, json={
        "proposal_id": proposal["id"], "documents": _valid_pre_analysis_documents(),
    })
    client.post("/api/v1/finops/pre-analysis/tapaf-checkout-accept", headers=auth_headers, json={
        "proposal_id": proposal["id"], "scroll_completed": True, "checkbox_1": True, "checkbox_2": True,
    })
    client.post("/api/v1/finops/pre-analysis/tapaf-payment-webhook", headers=auth_headers, json={
        "proposal_id": proposal["id"], "event_id": "tapaf-webhook-002", "amount": "1500.00",
    })
    engine = client.post("/api/v1/finops/pre-analysis/run-engine", headers=auth_headers, json={
        "proposal_id": proposal["id"],
        "adm_nome": "ANCORA",
        "extratos_6_meses_data": _sample_extratos(10000),
        "parcela_simulada": "5000",
        "valor_avaliacao_bem": "400000",
        "saldo_devedor_cotas": "300000",
        "ano_fabricacao_bem": 2022,
    })
    assert engine.status_code == 200
    result = engine.json()["result"]
    assert result["status_core"] == "REPROVADO_POR_PARCELA_MAIOR_QUE_30_PERCENT_DA_RENDA"
    assert "bifurcacao_opcoes_interface_cliente" in result
    assert "resumo_fiduciario_interno_oculto_para_o_fundo" not in result
    assert engine.json()["status"] == "REPROVED"


def test_lease_equity_engine_canonical_doc251():
    from app.lease_equity_engine import EngineLeaseEquityLetter, money

    engine = EngineLeaseEquityLetter()
    credit = engine.processar_matriz_credito_ltv("URBANO_RESIDENCIAL", Decimal("1000000"))
    assert credit["ltv_percent"] == "40.00"
    assert credit["limite_teto_ltv_captacao"] == "400000.00"
    assert credit["base_calculo_recompensa_dono"] == "400000.00"
    assert credit["aluguel_mensal_recorrente_bruto_dono"] == "1600.00"
    assert credit["ganho_total_proprietario_prazo"] == "57600.00"
    assert credit["custo_mensal_remuneracao_pool_investidores"] == "6400.00"
    assert credit["comissao_parceiro_percent"] == "2"
    assert Decimal(credit["comissao_parceiro_pool"]) == money(
        Decimal(credit["saque_total_antecipado_vp"]) * Decimal("0.02")
    )

    sim_600k = engine.processar_matriz_credito_ltv("URBANO_RESIDENCIAL", Decimal("600000"))
    assert sim_600k["limite_teto_ltv_captacao"] == "240000.00"
    assert sim_600k["aluguel_mensal_recorrente_bruto_dono"] == "960.00"
    assert sim_600k["ganho_total_proprietario_prazo"] == "34560.00"

    lote = engine.processar_matriz_credito_ltv("LOTE_URBANO", Decimal("600000"))
    assert lote["limite_teto_ltv_captacao"] == "150000.00"
    assert lote["aluguel_mensal_recorrente_bruto_dono"] == "600.00"
    assert lote["ganho_total_proprietario_prazo"] == "21600.00"

    rural = engine.processar_matriz_credito_ltv("RURAL", Decimal("600000"))
    assert rural["limite_teto_ltv_captacao"] == "120000.00"
    assert rural["aluguel_mensal_recorrente_bruto_dono"] == "480.00"
    assert rural["ganho_total_proprietario_prazo"] == "17280.00"

    rwa = engine.gerar_fracionamento_securitizado_rwa(Decimal("400000"), "LETTER_LEASE_EQ_0044_2026")
    assert rwa["total_supply_tokens_mint"] == 4000
    assert rwa["rendimento_mensal_unitario_smart_contract"] == "1.60"
    blocked = engine.calcular_antecipacao_recebiveis_price(Decimal("1600"), 36, 5)
    assert blocked["status_antecipacao"] == "ANTECIPACAO_BLOQUEADA_CARENCIA_MINIMA"
    assert blocked["meses_faltantes_para_liberacao"] == 1
    released = engine.calcular_antecipacao_recebiveis_price(Decimal("1600"), 36, 6)
    assert released["status_antecipacao"] == "LIBERADO_PARA_SAQUE_VISTA"
    assert Decimal(released["valor_liquido_payout_vista"]) > Decimal("0")
    assert Decimal(released["comissao_parceiro_pool"]) == money(
        Decimal(released["valor_liquido_payout_vista"]) * Decimal("0.02")
    )


def test_lease_equity_full_pipeline_and_tokenization(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "SDC", "requested_amount": "600000", "terms": {},
    }).json()
    created = client.post("/api/v1/finops/lease-equity/pautas", headers=auth_headers, json={
        "proposal_id": proposal["id"],
        "property_type": "URBANO_RESIDENCIAL",
        "appraisal_value": "1000000",
        "registry_number": "44901",
        "registry_office": "Teixeira de Freitas - BA",
    })
    assert created.status_code == 201
    pauta = created.json()
    assert pauta["status"] == "AGUARDANDO_TAPAF"
    assert pauta["credit_matrix"]["aluguel_mensal_recorrente_bruto_dono"] == "1600.00"

    paid = client.post("/api/v1/finops/lease-equity/tapaf-payment-webhook", headers=auth_headers, json={
        "pauta_id": pauta["id"], "event_id": "tapaf-le-001", "amount": "750.00",
    })
    assert paid.status_code == 200 and paid.json()["status"] == "TAPAF_LIQUIDADA"
    assert paid.json()["compliance_dossier_uri"]

    gallery_blocked = client.post("/api/v1/finops/lease-equity/inspection-photos", headers=auth_headers, json={
        "pauta_id": pauta["id"],
        "photos": [{"filename": "x.jpg", "source": "GALLERY", "exif_timestamp_unix": 1, "gps_latitude": 0, "gps_longitude": 0}],
    })
    assert gallery_blocked.status_code == 422

    photos = [
        {"filename": f"foto{i}.jpg", "source": "CAMERA_NATIVE", "exif_timestamp_unix": 1700000000 + i,
         "gps_latitude": -17.5, "gps_longitude": -39.7}
        for i in range(3)
    ]
    inspection = client.post("/api/v1/finops/lease-equity/inspection-photos", headers=auth_headers, json={
        "pauta_id": pauta["id"], "photos": photos,
    })
    assert inspection.status_code == 200 and inspection.json()["status"] == "EM_AUDITORIA_RISCO"

    compliance = client.post("/api/v1/finops/lease-equity/compliance-review", headers=auth_headers, json={
        "pauta_id": pauta["id"], "approved": True,
    })
    assert compliance.json()["status"] == "AGUARDANDO_ASSINATURA"

    client.post(f"/api/v1/finops/lease-equity/sign-contract?pauta_id={pauta['id']}", headers=auth_headers)
    client.post(f"/api/v1/finops/lease-equity/submit-registry?pauta_id={pauta['id']}", headers=auth_headers)
    gravame = client.post(f"/api/v1/finops/lease-equity/complete-gravame?pauta_id={pauta['id']}", headers=auth_headers)
    assert gravame.json()["status"] == "GRAVAME_CONCLUIDO"

    funding = client.post("/api/v1/finops/lease-equity/funding-capture", headers=auth_headers, json={
        "pauta_id": pauta["id"], "amount": "120000.00",
    })
    assert funding.status_code == 200 and funding.json()["status"] == "ATIVO_OK_EM_PRODUCAO"

    token = client.post("/api/v1/finops/lease-equity/tokenization-processor", headers=auth_headers, json={
        "pauta_id": pauta["id"], "owner_uid": "USER_PF_88219_BA",
    })
    assert token.status_code == 200
    body = token.json()
    assert body["endpoint"] == "/api/v1/finops/lease-equity/tokenization-processor"
    assert body["status"] == "SUCCESS"
    data = body["data"]
    assert data["contrato_id"] == pauta["pauta_code"]
    assert data["colateral_imobiliario"]["matricula_numero"] == "44901"
    assert data["parametrizacao_finops_mesa"]["ltv_alavancagem_teto"] == 400000.0
    assert data["parametrizacao_finops_mesa"]["faturamento_mensal_bruto_recorrente_dono"] == 1600.0
    assert data["parametrizacao_finops_mesa"]["custo_mensal_pool_investment_1_6_porcento"] == 6400.0
    assert data["parametrizacao_finops_mesa"]["comissao_parceiro_pool_percent"] == 2.0
    meta = data["workflow_securitizacao_rwa"]["tokenizacao_blockchain_metadata"]
    assert meta["total_supply_tokens_emitidos"] == 4000
    assert meta["distribuicao_rendimento_token_mensal"] == 1.60
    assert data["trava_seguranca_antecipacao_futura"]["carecia_meses_minima"] == 6

    unlocked = client.post("/api/v1/finops/lease-equity/refresh-anticipation", headers=auth_headers, json={
        "pauta_id": pauta["id"], "months_in_force": 6,
    })
    assert unlocked.json()["status"] == "LIBERADO_PARA_ANTECIPACAO"


def _native_photos():
    return [
        {"filename": f"foto{i}.jpg", "source": "CAMERA_NATIVE", "exif_timestamp_unix": 1700000000 + i,
         "gps_latitude": -17.5, "gps_longitude": -39.7}
        for i in range(3)
    ]


def test_contract_native_inspection_sdc_and_flash_links_auction(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    quotas = [q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["category"] == "REAL_ESTATE"][:2]
    for product, amount, calc_fn in (
        ("SDC", "800000", lambda pid: client.post(f"/api/v1/proposals/{pid}/calculate-sdc", headers=auth_headers, json={
            "quota_ids": [q["id"] for q in quotas], "duration_months": 12,
        })),
        ("FLASH_CREDIT", "400000", lambda pid: client.post(f"/api/v1/proposals/{pid}/calculate-flash-credit", headers=auth_headers, json={
            "asset_value": "1000000", "capital_source": "RETAIL", "term_months": 36, "ipca_annual_percent": "0",
        })),
    ):
        proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
            "lead_id": lead["id"], "product": product, "requested_amount": amount, "terms": {},
        }).json()
        calc = calc_fn(proposal["id"])
        assert calc.status_code == 201, calc.text
        contract = client.post(f"/api/v1/proposals/{proposal['id']}/contracts", headers=auth_headers, json={
            "calculation_memory_id": calc.json()["id"],
        })
        assert contract.status_code == 201
        cid = contract.json()["id"]
        inspection = client.post(f"/api/v1/contracts/{cid}/native-inspection", headers=auth_headers, json={
            "photos": _native_photos(),
        })
        assert inspection.status_code == 201
        assert inspection.json()["product"] == product
        assert "collateral-inspections" in inspection.json()["vault_s3_uri"]
        assert inspection.json()["auction_evidence_ready"] is True

        gallery = client.post(f"/api/v1/contracts/{cid}/native-inspection", headers=auth_headers, json={
            "photos": [
                {"filename": f"g{i}.jpg", "source": "GALLERY", "exif_timestamp_unix": 1, "gps_latitude": 0, "gps_longitude": 0}
                for i in range(3)
            ],
        })
        assert gallery.status_code == 422
        assert "galeria" in gallery.json()["detail"].lower()


def test_nina_distress_auto_links_native_inspection_photos(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "FLASH_CREDIT", "requested_amount": "400000", "terms": {},
    }).json()
    calc = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-flash-credit", headers=auth_headers, json={
        "asset_value": "1000000", "capital_source": "RETAIL", "term_months": 36, "ipca_annual_percent": "0",
    })
    assert calc.status_code == 201
    contract = client.post(f"/api/v1/proposals/{proposal['id']}/contracts", headers=auth_headers, json={
        "calculation_memory_id": calc.json()["id"],
    }).json()
    client.post(f"/api/v1/contracts/{contract['id']}/native-inspection", headers=auth_headers, json={"photos": _native_photos()})
    client.post(f"/api/v1/contracts/{contract['id']}/billing", headers=auth_headers, json={"start_date": "2026-01-01"})
    contract_invoice_ids = {i["id"] for i in client.get("/api/v1/invoices", headers=auth_headers).json() if i["contract_id"] == contract["id"]}
    refreshed = client.post("/api/v1/collections/refresh?as_of=2026-05-05", headers=auth_headers)
    del_case = next(c for c in refreshed.json() if c["invoice_id"] in contract_invoice_ids and c.get("caducity_eligible"))
    nina = client.post("/api/v1/nina-asset/cases", headers=auth_headers, json={
        "delinquency_case_id": del_case["id"], "appraisal_value_avm": "800000", "daily_reduction_amount": "500",
    })
    assert nina.status_code == 201
    assert nina.json()["photo_storage_reference"]
    assert "collateral-inspections" in nina.json()["photo_storage_reference"]


def test_quitcon_engine_canonical_doc253():
    from app.quitcon_engine import EngineQuitConLetter

    engine = EngineQuitConLetter()
    sim = engine.simular_quitcon_doc253(Decimal("250000"), 12, administrator_name="Embracon")
    assert sim["saldo_devedor_bruto"] == "250000.00"
    assert sim["valor_presente_quitacao"] == "223214.29"
    assert sim["cedente"]["taxa_intermediacao_3_porcento_sobre_quitacao"] == "6696.43"
    assert sim["cedente"]["pagamento_total_quitacao_mais_intermediacao"] == "229910.72"
    assert sim["cessionario"]["capital_giro_liquido_na_liberacao"] == "212053.58"
    assert sim["custos_entrada"]["itens"][0]["codigo"] == "TAPAF"
    assert sim["custos_entrada"]["itens"][0]["valor"] == "1500.00"
    assert sim["custos_entrada"]["itens"][1]["codigo"] == "SERVICO_OPERACIONAL_2PCT"
    assert sim["custos_entrada"]["itens"][1]["aplicavel"] is False
    assert sim["custos_entrada"]["itens"][2]["valor"] == "22321.43"
    sim_svc = engine.simular_quitcon_doc253(Decimal("400000"), 0, operational_service=True, administrator_name="Embracon")
    assert sim_svc["custos_entrada"]["itens"][1]["valor"] == "8000.00"
    assert sim_svc["custos_entrada"]["total_com_servico_operacional"] == "49500.00"
    assert engine.calcular_pagamento_total_cedente(Decimal("400000")) == Decimal("412000.00")
    assert engine.calcular_liberacao_cessionario(Decimal("400000"))["capital_giro_liquido_na_liberacao"] == "380000.00"
    assert engine.calcular_taxa_servico_operacional_inicio(Decimal("400000")) == Decimal("8000.00")
    assert sim["elegibilidade"]["elegivel"] is True
    assert engine.administradora_permitida("Embracon") is True
    assert engine.administradora_permitida("Administradora Demo") is False

    finance = engine.processar_matriz_financeira(Decimal("250000"), meses_restantes=12)
    assert finance["meta_captacao_quitacao"] == "223214.29"
    assert finance["doc_version"] == "LETTER_QUITCON_PRODUTO_2026_DOC253"

    escrow = engine.calcular_taxa_sucesso_escrow(Decimal("223214.29"))
    assert escrow == Decimal("22321.43")


def test_quitcon_full_pipeline_penalties_and_tokenization(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "SDC", "requested_amount": "600000", "terms": {},
    }).json()
    created = client.post("/api/v1/finops/quitcon/operacoes", headers=auth_headers, json={
        "proposal_id": proposal["id"],
        "outstanding_balance": "250000",
        "registry_number": "44901",
        "registry_office": "Embracon",
        "meses_restantes": 12,
    })
    assert created.status_code == 201
    operacao = created.json()
    assert operacao["status"] == "AGUARDANDO_TAPAF"
    assert operacao["sla_dias_estimados"] == 45
    assert operacao["success_fee_escrow_amount"] == "22321.43"
    assert operacao["credit_matrix"]["ltv_assimetrico_aplicavel"] is False
    assert operacao["credit_matrix"]["meta_captacao_quitacao"] == "223214.29"

    paid = client.post("/api/v1/finops/quitcon/tapaf-payment-webhook", headers=auth_headers, json={
        "operacao_id": operacao["id"], "event_id": "tapaf-qc-001", "amount": "1500.00",
    })
    assert paid.status_code == 200 and paid.json()["status"] == "TAPAF_LIQUIDADA"

    fee = client.post("/api/v1/finops/quitcon/success-fee-payment-webhook", headers=auth_headers, json={
        "operacao_id": operacao["id"], "event_id": "fee-qc-001", "amount": "22321.43",
    })
    assert fee.status_code == 200 and fee.json()["success_fee_escrow_paid_at"]

    photos = _native_photos()
    inspection = client.post("/api/v1/finops/quitcon/inspection-photos", headers=auth_headers, json={
        "operacao_id": operacao["id"], "photos": photos,
    })
    assert inspection.status_code == 200 and inspection.json()["status"] == "EM_AUDITORIA_RISCO"

    compliance = client.post("/api/v1/finops/quitcon/compliance-review", headers=auth_headers, json={
        "operacao_id": operacao["id"], "approved": True,
    })
    assert compliance.json()["status"] == "AGUARDANDO_ASSINATURA"

    admin = client.post(f"/api/v1/finops/quitcon/administrator-approval?operacao_id={operacao['id']}", headers=auth_headers)
    assert admin.status_code == 200 and admin.json()["administrator_approved_at"]
    assert admin.json()["cedente_payment_amount"] == "229910.72"
    assert admin.json()["penalty_preview"]

    client.post(f"/api/v1/finops/quitcon/sign-contract?operacao_id={operacao['id']}", headers=auth_headers)
    client.post(f"/api/v1/finops/quitcon/submit-registry?operacao_id={operacao['id']}", headers=auth_headers)
    gravame = client.post(f"/api/v1/finops/quitcon/complete-gravame?operacao_id={operacao['id']}", headers=auth_headers)
    assert gravame.json()["status"] == "GRAVAME_CONCLUIDO"

    funding = client.post("/api/v1/finops/quitcon/funding-capture", headers=auth_headers, json={
        "operacao_id": operacao["id"], "amount": "75000.00",
    })
    assert funding.status_code == 200 and funding.json()["status"] == "ATIVO_OK_EM_PRODUCAO"

    token = client.post("/api/v1/finops/quitcon/tokenization-processor", headers=auth_headers, json={
        "operacao_id": operacao["id"], "owner_uid": "USER_PF_88219_BA",
    })
    assert token.status_code == 200
    data = token.json()["data"]
    assert data["parametrizacao_finops_mesa"]["meta_captacao_quitacao"] == 223214.29
    assert data["parametrizacao_finops_mesa"]["ltv_assimetrico_aplicavel"] is False
    assert data["parametrizacao_finops_mesa"]["remuneracao_proprietario_0_4_porcento"] is False
    assert data["governanca_risco_doc252"]["sla_dias_estimados"] == 45
    assert data["workflow_securitizacao_rwa"]["tokenizacao_blockchain_metadata"]["total_supply_tokens_emitidos"] == 2232

    cancel = client.post("/api/v1/finops/quitcon/cancel-inadimplencia", headers=auth_headers, json={
        "operacao_id": operacao["id"], "days_overdue": 16,
    })
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "CANCELADO_INADIMPLENCIA_CESSIONARIO"
    assert cancel.json()["penalty_amount"] == "22321.43"


def test_quitcon_public_simulator_doc253(client):
    res = client.post("/api/v1/public/quitcon/simulate", json={
        "outstanding_balance": "250000",
        "meses_restantes": 12,
        "administrator_name": "Embracon",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["doc_version"] == "LETTER_QUITCON_PRODUTO_2026_DOC253"
    assert body["valor_presente_quitacao"] == "223214.29"
    assert body["custos_entrada"]["titulo"] == "Custos pagos pelo cliente no início da operação"
    assert body["custos_entrada"]["itens"][0]["valor"] == "1500.00"
    assert body["elegibilidade"]["elegivel"] is True


def test_public_site_flash_pool_and_lead_capture(client):
    blocked = client.post("/api/v1/public/site/leads/capture", json={
        "razao_social": "Empresa Teste LTDA",
        "whatsapp": "32988887777",
        "produto": "flash",
        "valor_base": "1000000",
        "autorizacao_scr_bacen": False,
    })
    assert blocked.status_code == 422
    lead = client.post("/api/v1/public/site/leads/capture", json={
        "razao_social": "Empresa Teste LTDA",
        "whatsapp": "32988887777",
        "produto": "flash",
        "valor_base": "1000000",
        "autorizacao_scr_bacen": True,
    })
    assert lead.status_code == 201
    assert lead.json()["status"] == "LEAD_LOGGED_AND_BACEN_AUTHORIZED"
    sim = client.post("/api/v1/public/site/flash/simulate", json={"asset_value": "1000000"})
    assert sim.status_code == 200
    body = sim.json()
    assert body["track"] == "POOL"
    assert body["principal"] == "400000.00"
    assert body["net_payout"] == "348000.00"
    assert body["mmn"]["configured"] is True
    assert body["mmn"]["commission_pool"] == "10440.00"
    assert body["mmn"]["holding_retained_from_fee"] == "29560.00"


def test_public_site_sdc_simulate_with_quotas(client):
    quotas = client.get("/api/v1/public/site/quotas").json()
    assert len(quotas) >= 2
    sim = client.post("/api/v1/public/site/sdc/simulate", json={
        "quota_ids": [quotas[0]["id"], quotas[1]["id"]],
        "requested_amount": "800000",
        "duration_months": 12,
        "capital_source": "POOL",
    })
    assert sim.status_code == 200
    output = sim.json()["output"]
    assert output["principal"] == "800000.00"
    assert output["total_interest"] == "432000.00"
    assert sim.json()["mmn"]["configured"] is True
    assert sim.json()["mmn"]["commission_pool"] == "2400.00"


def test_public_site_chat_home_proxy(client, monkeypatch):
    import httpx

    payload = {
        "OBJ": {
            "chat_next": [{"text": "O que você deseja:", "mascote": 1}],
            "info": {"whatsapp": "(11) 92175-5065"},
        }
    }

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None):
            assert url.endswith("/api/home")
            return FakeResponse()

    monkeypatch.setattr("app.public_chat_proxy.httpx.Client", FakeClient)
    response = client.post("/api/v1/public/site/chat/home", json={})
    assert response.status_code == 200
    assert response.json()["OBJ"]["chat_next"][0]["text"] == "O que você deseja:"


def test_escrow_asaas_status_not_configured(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.asaas_common.settings.asaas_api_key", None)
    monkeypatch.setattr("app.asaas_common.settings.asaas_wallet_id", None)
    response = client.get("/api/v1/escrow/asaas/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["connected"] is False


def test_escrow_create_uses_asaas_subaccount_when_configured(client, auth_headers, monkeypatch):
    escrow_calls: list[dict] = []

    class FakeAsaasClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get_balance(self):
            return {"balance": 1000.0}

        def list_wallets(self):
            return {"data": [{"id": "wallet-test-001"}]}

        def create_subaccount(self, payload):
            assert payload["name"]
            assert payload["cpfCnpj"]
            return {"id": "acct-sub-001", "walletId": "wallet-sub-001", "apiKey": "secret-once"}

        def configure_subaccount_escrow(self, account_id, **kwargs):
            escrow_calls.append({"account_id": account_id, **kwargs})
            return {"enabled": True}

        def configure_default_escrow(self, **kwargs):
            return {"enabled": True}

    monkeypatch.setattr("app.asaas_common.settings.asaas_api_key", "test-key")
    monkeypatch.setattr("app.asaas_common.settings.asaas_wallet_id", "wallet-test-001")
    monkeypatch.setattr("app.asaas_escrow_service.AsaasClient", FakeAsaasClient)
    monkeypatch.setattr("app.asaas_subaccount_service.AsaasClient", FakeAsaasClient)

    created = client.post("/api/v1/escrow/accounts", headers=auth_headers, json={"create_subaccount": True, "enable_escrow": True})
    assert created.status_code == 201
    body = created.json()
    assert body["provider"] == "ASAAS_SUBACCOUNT"
    assert body["external_account_id"] == "wallet-sub-001"
    assert body["asaas_account_id"] == "acct-sub-001"
    assert body["subaccount_name"]
    assert body["escrow_enabled"] is True
    assert len(escrow_calls) == 1


def test_escrow_create_plain_subaccount_without_escrow(client, auth_headers, monkeypatch):
    escrow_calls: list[dict] = []

    class FakeAsaasClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get_balance(self):
            return {"balance": 1000.0}

        def list_wallets(self):
            return {"data": [{"id": "wallet-test-001"}]}

        def create_subaccount(self, payload):
            return {"id": "acct-plain-001", "walletId": "wallet-plain-001", "apiKey": "secret-once"}

        def configure_subaccount_escrow(self, account_id, **kwargs):
            escrow_calls.append({"account_id": account_id, **kwargs})
            return {"enabled": True}

        def configure_default_escrow(self, **kwargs):
            return {"enabled": True}

    monkeypatch.setattr("app.asaas_common.settings.asaas_api_key", "test-key")
    monkeypatch.setattr("app.asaas_common.settings.asaas_wallet_id", "wallet-test-001")
    monkeypatch.setattr("app.asaas_escrow_service.AsaasClient", FakeAsaasClient)
    monkeypatch.setattr("app.asaas_subaccount_service.AsaasClient", FakeAsaasClient)

    created = client.post(
        "/api/v1/escrow/accounts",
        headers=auth_headers,
        json={"create_subaccount": True, "enable_escrow": False},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["provider"] == "ASAAS_SUBACCOUNT"
    assert body["external_account_id"] == "wallet-plain-001"
    assert body["escrow_enabled"] is False
    assert escrow_calls == []


def test_escrow_create_main_wallet_legacy(client, auth_headers, monkeypatch):
    class FakeAsaasClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get_balance(self):
            return {"balance": 1000.0}

        def list_wallets(self):
            return {"data": [{"id": "wallet-test-001"}]}

        def configure_default_escrow(self, **kwargs):
            return {"enabled": True}

    monkeypatch.setattr("app.asaas_common.settings.asaas_api_key", "test-key")
    monkeypatch.setattr("app.asaas_common.settings.asaas_wallet_id", "wallet-test-001")
    monkeypatch.setattr("app.asaas_escrow_service.AsaasClient", FakeAsaasClient)

    created = client.post("/api/v1/escrow/accounts", headers=auth_headers, json={"create_subaccount": False})
    assert created.status_code == 201
    body = created.json()
    assert body["provider"] == "ASAAS"
    assert body["external_account_id"] == "wallet-test-001"


def test_escrow_subaccount_preview(client, auth_headers):
    response = client.post("/api/v1/escrow/subaccount/preview", headers=auth_headers, json={"create_subaccount": True})
    assert response.status_code == 200
    body = response.json()
    assert body["name"]
    assert body["cpf_cnpj"]
    assert body["person_type"] in {"PF", "PJ"}


def test_escrow_create_mock_subaccount_without_asaas(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.asaas_common.settings.asaas_api_key", None)
    monkeypatch.setattr("app.asaas_common.settings.asaas_wallet_id", None)
    created = client.post("/api/v1/escrow/accounts", headers=auth_headers, json={"create_subaccount": True})
    assert created.status_code == 201
    body = created.json()
    assert body["provider"] == "MOCK_SUBACCOUNT"
    assert body["subaccount_name"]
    assert body["escrow_enabled"] is True


def test_escrow_create_mock_plain_subaccount_without_asaas(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.asaas_common.settings.asaas_api_key", None)
    monkeypatch.setattr("app.asaas_common.settings.asaas_wallet_id", None)
    created = client.post(
        "/api/v1/escrow/accounts",
        headers=auth_headers,
        json={"create_subaccount": True, "enable_escrow": False},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["provider"] == "MOCK_SUBACCOUNT"
    assert body["escrow_enabled"] is False
    monkeypatch.setattr("app.zapsign_signature_service.settings.zapsign_api_token", None)
    response = client.get("/api/v1/signatures/zapsign/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["connected"] is False


def test_signature_create_uses_zapsign_when_configured(client, auth_headers, monkeypatch):
    class FakeZapSignClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def create_doc_from_pdf(self, **kwargs):
            return {
                "token": "doc-token-001",
                "status": "pending",
                "signers": [{"email": "cliente@exemplo.com.br", "sign_url": "https://app.zapsign.com.br/verificar/signer-001"}],
            }

        def get_doc(self, token):
            return {"token": token, "status": "pending", "signers": [{"email": "cliente@exemplo.com.br", "sign_url": "https://app.zapsign.com.br/verificar/signer-001"}]}

    monkeypatch.setattr("app.zapsign_signature_service.settings.zapsign_api_token", "zapsign-test-token")
    monkeypatch.setattr("app.zapsign_signature_service.ZapSignClient", FakeZapSignClient)

    proposal = client.get("/api/v1/proposals", headers=auth_headers).json()[0]
    quotas = [q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["category"] == "REAL_ESTATE"][:2]
    calculation = client.post(
        f"/api/v1/proposals/{proposal['id']}/calculate",
        headers=auth_headers,
        json={"quota_ids": [q["id"] for q in quotas], "fee_percent": "10", "start_fee": "1500"},
    )
    assert calculation.status_code == 201
    contract = client.post(
        f"/api/v1/proposals/{proposal['id']}/contracts",
        headers=auth_headers,
        json={"calculation_memory_id": calculation.json()["id"]},
    ).json()
    created = client.post(
        f"/api/v1/contracts/{contract['id']}/signature",
        headers=auth_headers,
        json={"signer_email": "cliente@exemplo.com.br", "signer_name": "Cliente Teste"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["provider"] == "ZAPSIGN"
    assert body["external_id"] == "doc-token-001"
    assert body["sign_url"].startswith("https://")

    refresh = client.post(f"/api/v1/signatures/{body['id']}/refresh", headers=auth_headers)
    assert refresh.status_code == 200

    mock_complete = client.post(
        f"/api/v1/signatures/{body['id']}/mock-complete",
        headers=auth_headers,
        json={"confirmation": True, "ip_address": "127.0.0.1"},
    )
    assert mock_complete.status_code == 409


def test_quitcon_sdc_projection_doc256(client, auth_headers):
    from app.quitcon_engine import EngineQuitConLetter

    engine = EngineQuitConLetter()
    vp6 = engine.calcular_valor_quitcon_vp(Decimal("250000"), 6)
    assert vp6 == Decimal("235849.06")
    table = engine.gerar_tabela_projecao_quitcon(Decimal("250000"))
    assert table["tabela"]["quitacao_48_meses"]["status_operacao"] == "Estimativa com desconto de 48%"
    assert table["tabela"]["quitacao_48_meses"]["valor_quitcon_estimado_vp"] == "168918.92"

    projection = client.post("/api/v1/finops/sdc/quitcon-projection", headers=auth_headers, json={
        "saldo_devedor_simulado": "250000",
        "meses_restantes": 12,
    })
    assert projection.status_code == 200
    body = projection.json()
    assert body["card"]["quitacao_vista_quitcon_vp"] == "223214.29"
    assert body["card"]["pagamento_total_cedente_vp_mais_3_porcento"] == "229910.72"
    assert body["card"]["modal"]["titulo"] == "Como funciona a Quitação Inteligente QuitCon?"
    assert "INCC ou IPCA" in body["projecao_temporal"]["nota_compliance_rodape"]

    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "SDC", "requested_amount": "800000", "terms": {},
    }).json()
    quotas = [q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["category"] == "REAL_ESTATE"][:2]
    calculated = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-sdc", headers=auth_headers, json={
        "quota_ids": [q["id"] for q in quotas], "duration_months": 12,
    }).json()
    contract = client.post(f"/api/v1/proposals/{proposal['id']}/contracts", headers=auth_headers, json={
        "calculation_memory_id": calculated["id"],
    }).json()
    client.post(f"/api/v1/contracts/{contract['id']}/accept", headers=auth_headers, json={
        "confirmation": True, "ip_address": "127.0.0.1", "user_agent": "pytest",
    })
    card = client.get(f"/api/v1/contracts/{contract['id']}/sdc-quitcon-card", headers=auth_headers)
    assert card.status_code == 200
    assert card.json()["card"]["saldo_devedor_atual"] == calculated["output"]["maturity_total"]


def test_sdc_start_quitcon_from_simulation_and_contract(client, auth_headers):
    lead = client.get("/api/v1/leads", headers=auth_headers).json()[0]
    proposal = client.post("/api/v1/proposals", headers=auth_headers, json={
        "lead_id": lead["id"], "product": "SDC", "requested_amount": "800000", "terms": {},
    }).json()
    quotas = [q for q in client.get("/api/v1/quotas", headers=auth_headers).json() if q["category"] == "REAL_ESTATE"][:2]
    calculated = client.post(f"/api/v1/proposals/{proposal['id']}/calculate-sdc", headers=auth_headers, json={
        "quota_ids": [q["id"] for q in quotas], "duration_months": 12,
    })
    assert calculated.status_code == 201
    calc = calculated.json()

    started = client.post("/api/v1/finops/sdc/start-quitcon", headers=auth_headers, json={
        "proposal_id": proposal["id"],
        "calculation_memory_id": calc["id"],
        "confirmation": True,
    })
    assert started.status_code == 201
    body = started.json()
    assert body["created"] is True
    assert body["status"] == "AGUARDANDO_TAPAF"
    assert body["tapaf_checkout"]["valor_tapaf_brl"] == "1500.00"
    assert body["quitcon_sdc"]["card"]["saldo_devedor_atual"] == calc["output"]["maturity_total"]

    again = client.post("/api/v1/finops/sdc/start-quitcon", headers=auth_headers, json={
        "proposal_id": proposal["id"],
        "calculation_memory_id": calc["id"],
        "confirmation": True,
    })
    assert again.status_code == 200
    assert again.json()["created"] is False
    assert again.json()["operacao_id"] == body["operacao_id"]

    contract = client.post(f"/api/v1/proposals/{proposal['id']}/contracts", headers=auth_headers, json={
        "calculation_memory_id": calc["id"],
    }).json()
    client.post(f"/api/v1/contracts/{contract['id']}/accept", headers=auth_headers, json={
        "confirmation": True, "ip_address": "127.0.0.1", "user_agent": "pytest",
    })
    from_contract = client.post("/api/v1/finops/sdc/start-quitcon", headers=auth_headers, json={
        "contract_id": contract["id"],
        "confirmation": True,
    })
    assert from_contract.status_code == 200
    assert from_contract.json()["operacao_id"] == body["operacao_id"]


def test_public_site_lead_flash_pool_and_sdc(client, auth_headers):
    blocked = client.post("/api/v1/public/site/leads/capture", json={
        "razao_social": "Empresa Teste LTDA",
        "whatsapp": "11988887777",
        "produto": "flash",
        "valor_base": "1000000",
        "autorizacao_scr_bacen": False,
    })
    assert blocked.status_code == 422

    lead = client.post("/api/v1/public/site/leads/capture", json={
        "razao_social": "Empresa Site LTDA",
        "whatsapp": "11988887777",
        "produto": "flash",
        "valor_base": "1000000",
        "autorizacao_scr_bacen": True,
    })
    assert lead.status_code == 201
    assert lead.json()["status"] == "LEAD_LOGGED_AND_BACEN_AUTHORIZED"

    flash = client.post("/api/v1/public/site/flash/simulate", json={
        "asset_value": "1000000",
        "requested_amount": "400000",
    })
    assert flash.status_code == 200
    body = flash.json()
    assert body["track"] == "POOL"
    assert body["principal"] == "400000.00"
    assert body["net_payout"] == "348000.00"
    assert body["mmn"]["configured"] is True
    assert body["mmn"]["commission_pool"] == "10440.00"

    quotas = client.get("/api/v1/public/site/quotas")
    assert quotas.status_code == 200
    catalog = quotas.json()
    assert len(catalog) >= 2

    sdc = client.post("/api/v1/public/site/sdc/simulate", json={
        "quota_ids": [catalog[0]["id"], catalog[1]["id"]],
        "requested_amount": "800000",
        "duration_months": 12,
        "capital_source": "POOL",
    })
    assert sdc.status_code == 200
    out = sdc.json()["output"]
    assert out["principal"] == "800000.00"
    assert out["total_interest"] == "432000.00"
    assert sdc.json()["mmn"]["configured"] is True
    assert sdc.json()["mmn"]["commission_pool"] == "2400.00"

def test_public_client_self_registration(client, auth_headers):
    users = client.get("/api/v1/admin/users", headers=auth_headers).json()
    partner = next(u for u in users if u["email"] == "parceiro@letter.com.br")
    node = client.post(
        "/api/v1/network/nodes",
        headers=auth_headers,
        json={"user_id": partner["id"], "tree_type": "SALES"},
    )
    assert node.status_code == 201
    referral_code = node.json()["referral_code"]

    preview = client.get(f"/api/v1/public/site/referral/{referral_code}")
    assert preview.status_code == 200
    assert preview.json()["valid"] is True
    assert preview.json()["referrer_name"]

    registered = client.post("/api/v1/public/site/auth/register", json={
        "name": "Cliente Site Demo",
        "email": "cliente.site@letter.com.br",
        "phone": "11977776666",
        "password": "ClienteSite1!",
        "referral_code": referral_code,
        "terms_accepted": True,
    })
    assert registered.status_code == 201
    body = registered.json()
    assert body["user"]["role"] == "CLIENT"
    assert body["user"]["email"] == "cliente.site@letter.com.br"
    assert body["referrer"]["valid"] is True
    assert body["referrer"]["referral_code"] == referral_code

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "CLIENT"

    duplicate = client.post("/api/v1/public/site/auth/register", json={
        "name": "Outro Cliente",
        "email": "cliente.site@letter.com.br",
        "phone": "11966665555",
        "password": "ClienteSite1!",
        "terms_accepted": True,
    })
    assert duplicate.status_code == 409

    invalid_ref = client.post("/api/v1/public/site/auth/register", json={
        "name": "Cliente Sem Ref",
        "email": "cliente2.site@letter.com.br",
        "phone": "11955554444",
        "password": "ClienteSite1!",
        "referral_code": "LTR-SAL-INVALIDO",
        "terms_accepted": True,
    })
    assert invalid_ref.status_code == 422

    direct = client.post("/api/v1/public/site/auth/register", json={
        "name": "Cliente Direto",
        "email": "cliente3.site@letter.com.br",
        "phone": "11944443333",
        "password": "ClienteSite1!",
        "terms_accepted": True,
    })
    assert direct.status_code == 201
    assert direct.json()["referrer"] is None

