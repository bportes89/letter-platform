from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Role


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProviderIntegrationCreate(BaseModel):
    provider: str = Field(min_length=2, max_length=60)
    category: str
    environment: str = "SANDBOX"
    base_url: str | None = Field(default=None, max_length=500)
    credential: str | None = Field(default=None, min_length=8, max_length=500)
    allowed_hosts: list[str] = Field(default_factory=list)
    sla_latency_ms: int = Field(default=2000,ge=100,le=60000)


class ProviderIntegrationView(ORMModel):
    id: str; provider: str; category: str; environment: str; base_url: str | None; active: bool
    health_status: str; latency_ms: int | None; last_health_at: datetime | None
    consecutive_failures: int; circuit_status: str; created_at: datetime
    allowed_hosts: list[str] = Field(default_factory=list)
    credential_version: int; credential_rotated_at: datetime | None; sla_latency_ms: int
    total_checks: int; successful_checks: int; uptime_percent: float = 0


class IntegrationProbeRequest(BaseModel):
    simulate_status: str = "UP"
    latency_ms: int = Field(default=40, ge=0, le=60000)


class CredentialRotateRequest(BaseModel):
    credential: str = Field(min_length=8,max_length=500)


class ProviderRequest(BaseModel):
    method: str = "GET"
    path: str = Field(min_length=1,max_length=500)
    payload: dict | None = None


class ProviderRequestLogView(ORMModel):
    id: str; integration_id: str; method: str; path: str; response_code: int | None
    latency_ms: int; success: bool; error: str | None; created_at: datetime


class ProviderIncidentView(ORMModel):
    id: str; integration_id: str; incident_type: str; severity: str; status: str
    title: str; details: str; acknowledged_at: datetime | None; resolved_at: datetime | None; created_at: datetime


class IncidentActionRequest(BaseModel):
    action: str


class DeadLetterBulkRequest(BaseModel):
    delivery_ids: list[str] = Field(min_length=1,max_length=100)


class SecretCreate(BaseModel):
    name: str = Field(min_length=3,max_length=120)
    backend: str = "LOCAL_ENCRYPTED"
    value: str | None = Field(default=None,min_length=8,max_length=20000)
    external_reference: str | None = Field(default=None,max_length=500)


class SecretReferenceView(ORMModel):
    id: str; name: str; backend: str; external_reference: str | None; version: int; active: bool; last_rotated_at: datetime


class MTLSConfigCreate(BaseModel):
    certificate_secret_id: str; private_key_secret_id: str; ca_secret_id: str | None = None
    verify_peer: bool = True; enabled: bool = True


class MTLSConfigView(ORMModel):
    id: str; integration_id: str; certificate_secret_id: str; private_key_secret_id: str
    ca_secret_id: str | None; verify_peer: bool; enabled: bool; updated_at: datetime


class OnboardingProfileCreate(BaseModel):
    api_version: str = "v1"; authentication_type: str = "BEARER"; health_path: str = "/health"
    reconciliation_mode: str = "CSV_AND_WEBHOOK"; checklist: dict = Field(default_factory=dict)


class OnboardingProfileView(ORMModel):
    id: str; integration_id: str; api_version: str; authentication_type: str; health_path: str
    reconciliation_mode: str; status: str; homologated_at: datetime | None; created_at: datetime
    checklist: dict = Field(default_factory=dict)


class ReconciliationRunView(ORMModel):
    id: str; integration_id: str; source_type: str; source_reference: str; content_hash: str
    total_items: int; matched_items: int; divergent_items: int; status: str; processed_at: datetime | None; created_at: datetime


class ProviderReconciliationItemView(ORMModel):
    id: str; run_id: str; external_id: str; event_type: str; amount: Decimal
    provider_status: str; match_status: str; reason: str | None


class HomologationEvidenceView(ORMModel):
    id: str; integration_id: str; control_key: str; result: str; evidence_hash: str; executed_at: datetime


class AdapterExecuteRequest(BaseModel):
    operation: str = Field(min_length=3,max_length=80)
    idempotency_key: str = Field(min_length=8,max_length=120)
    payload: dict = Field(default_factory=dict)


class AdapterExecutionView(ORMModel):
    id: str; integration_id: str; category: str; operation: str; idempotency_key: str
    input_hash: str; external_id: str; status: str; adapter_name: str; adapter_version: str; created_at: datetime
    output: dict = Field(default_factory=dict)


class AdapterCatalogItem(BaseModel):
    category: str; adapter: str; version: str; capabilities: list[str]; mode: str


class AdapterCertificationView(ORMModel):
    id: str; integration_id: str; status: str; passed_checks: int; total_checks: int
    report_hash: str; executed_at: datetime; report: dict = Field(default_factory=dict)


class GoLiveApprovalRequest(BaseModel):
    area: str; decision: str; notes: str = Field(min_length=5,max_length=1000)


class GoLiveApprovalView(ORMModel):
    id: str; integration_id: str; area: str; decision: str; notes: str
    decided_by_id: str; decided_at: datetime


class GoLiveDecisionView(ORMModel):
    id: str; integration_id: str; status: str; snapshot_hash: str; decided_at: datetime
    blockers: list[str] = Field(default_factory=list)


class WebhookEndpointCreate(BaseModel):
    integration_id: str
    name: str = Field(min_length=3, max_length=100)
    target_url: str = Field(min_length=8, max_length=500)
    secret: str = Field(min_length=16, max_length=500)
    subscribed_events: list[str] = Field(default_factory=lambda: ["*"])
    max_attempts: int = Field(default=5, ge=1, le=10)


class WebhookEndpointView(ORMModel):
    id: str; integration_id: str; name: str; target_url: str; max_attempts: int; active: bool; created_at: datetime
    subscribed_events: list[str] = Field(default_factory=list)


class WebhookDispatchRequest(BaseModel):
    event_id: str = Field(min_length=8, max_length=120)
    event_type: str = Field(min_length=3, max_length=100)
    payload: dict = Field(default_factory=dict)
    simulate_failure: bool = False


class WebhookRetryRequest(BaseModel):
    simulate_failure: bool = False


class WebhookDeliveryView(ORMModel):
    id: str; endpoint_id: str; event_id: str; event_type: str; signature: str; status: str
    attempts: int; max_attempts: int; response_code: int | None; response_body: str | None
    last_error: str | None; next_attempt_at: datetime | None; delivered_at: datetime | None; created_at: datetime


class WebhookVerifyRequest(BaseModel):
    secret: str = Field(min_length=16, max_length=500)
    signature: str
    payload: dict


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    otp: str | None = Field(default=None, min_length=6, max_length=6)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserView(ORMModel):
    id: str
    organization_id: str
    branch_id: str | None
    name: str
    email: EmailStr
    role: Role
    active: bool
    mfa_enabled: bool
    last_login_at: datetime | None


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    role: Role | None = None
    branch_id: str | None = None
    active: bool | None = None


class BranchCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    code: str = Field(min_length=2, max_length=40)
    region: str | None = None


class BranchView(ORMModel):
    id: str
    organization_id: str
    name: str
    code: str
    region: str | None
    active: bool


class InviteCreate(BaseModel):
    email: EmailStr
    role: Role
    branch_id: str | None = None


class PartnerInviteCreate(BaseModel):
    email: EmailStr
    role: Role = Field(description="MASTER_FRANCHISEE, MANAGER, PARTNER ou QUOTA_SELLER")


class InviteAccept(BaseModel):
    token: str
    name: str = Field(min_length=2, max_length=180)
    document: str | None = None
    password: str = Field(min_length=10)
    company_name: str | None = Field(default=None, max_length=180)
    company_cnpj: str | None = Field(default=None, max_length=20)
    company_address: str | None = Field(default=None, max_length=240)
    company_city: str | None = Field(default=None, max_length=120)
    company_state: str | None = Field(default=None, max_length=2)
    phone: str | None = Field(default=None, max_length=20)
    terms_accepted: bool = False
    scroll_completed: bool = False
    verification_reference: str | None = Field(default=None, max_length=120)


class InvitationPreviewView(BaseModel):
    email: EmailStr
    role: Role
    expires_at: datetime
    contract_required: bool
    contract_title: str
    contract_version: str
    contract_excerpt: str
    inviter_name: str | None = None
    company_legal_name: str
    company_cnpj: str


class PartnerContractAcceptanceView(ORMModel):
    id: str
    template_slug: str
    template_version: str
    document_sha256: str
    evidence_hash: str
    accepted_at: datetime


class InvitationView(ORMModel):
    id: str
    email: EmailStr
    role: Role
    branch_id: str | None
    status: str
    expires_at: datetime
    token: str | None = None


class MfaSetupView(BaseModel):
    secret: str
    provisioning_uri: str


class MfaVerify(BaseModel):
    otp: str = Field(min_length=6, max_length=6)


class StepUpRequest(BaseModel):
    password: str
    otp: str | None = None


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=10)


class SessionView(ORMModel):
    id: str
    user_agent: str | None
    ip_address: str | None
    active: bool
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    step_up_until: datetime | None


class KycCreate(BaseModel):
    subject_type: str
    subject_id: str


class KycDecision(BaseModel):
    status: str
    risk_level: str
    notes: str | None = None


class KycView(ORMModel):
    id: str
    subject_type: str
    subject_id: str
    provider: str
    external_id: str
    status: str
    risk_level: str | None
    created_at: datetime


class KycSelfCompleteResponse(BaseModel):
    kyc_status: str
    kyc_case_id: str
    subaccount: dict | None = None
    message: str


class NetworkNodeCreate(BaseModel):
    user_id: str
    sponsor_user_id: str | None = None
    tree_type: str = "SALES"


class NetworkNodeView(ORMModel):
    id: str
    user_id: str
    sponsor_user_id: str | None
    tree_type: str
    referral_code: str
    status: str


class CommissionRuleCreate(BaseModel):
    product: str
    commission_type: str
    pool_rate_percent: Decimal = Field(gt=0, le=100)
    base_type: str = "NET_PAYOUT"


class CommissionRuleView(ORMModel):
    id: str
    product: str
    commission_type: str
    version: int
    base_type: str
    pool_rate_percent: Decimal
    levels_json: str
    active: bool


class CommissionAllocate(BaseModel):
    originator_id: str
    proposal_id: str | None = None
    reference: str
    product: str
    commission_type: str = "SALES"
    calculation_base: Decimal = Field(gt=0)


class CommissionEntryView(ORMModel):
    id: str
    beneficiary_id: str
    originator_id: str
    proposal_id: str | None
    reference: str
    product: str
    commission_type: str
    level: int
    calculation_base: Decimal
    pool_rate_percent: Decimal
    level_share_percent: Decimal
    amount: Decimal
    status: str
    released_at: datetime | None


class FiscalReleaseRequest(BaseModel):
    reference_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    document_content: str = Field(min_length=10)
    access_key: str | None = Field(default=None, min_length=44, max_length=44)
    gross_amount: Decimal | None = Field(default=None, gt=0)


class SefazRobotStatusView(BaseModel):
    enabled: bool
    provider: str
    mode: str
    message: str


class FiscalEvidenceView(ORMModel):
    id: str
    reference_month: str
    provider: str
    status: str
    access_key: str | None
    sefaz_status: str | None
    gross_amount: Decimal | None
    validated_at: datetime


class FundingOpportunityCreate(BaseModel):
    proposal_id: str | None = None
    title: str = Field(min_length=3, max_length=180)
    product: str
    capital_source: str = "RETAIL"
    target_amount: Decimal = Field(gt=0)
    min_investment: Decimal = Field(default=Decimal("1000"), gt=0)
    annual_return_reference: Decimal | None = Field(default=None, ge=0)


class FundingOpportunityView(ORMModel):
    id: str
    proposal_id: str | None
    title: str
    product: str
    capital_source: str
    target_amount: Decimal
    funded_amount: Decimal
    min_investment: Decimal
    annual_return_reference: Decimal | None
    status: str
    created_at: datetime


class InvestmentReserveRequest(BaseModel):
    amount: Decimal = Field(gt=0)


class InvestmentReservationView(ORMModel):
    id: str
    opportunity_id: str
    investor_id: str
    amount: Decimal
    status: str
    confirmed_at: datetime | None


class InvestmentPositionView(ORMModel):
    id: str
    opportunity_id: str
    investor_id: str
    principal: Decimal
    accrued_return: Decimal
    status: str


class BillingGenerateRequest(BaseModel):
    start_date: date


class InvoiceView(ORMModel):
    id: str
    contract_id: str
    proposal_id: str
    invoice_number: str
    installment_number: int
    kind: str
    due_date: date
    principal_amount: Decimal
    interest_amount: Decimal
    fee_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    status: str
    paid_at: datetime | None


class InvoicePaymentWebhook(BaseModel):
    event_id: str
    amount: Decimal = Field(gt=0)
    metadata: dict = Field(default_factory=dict)


class InvoiceProcessorRequest(BaseModel):
    invoice_id: str


class PaymentReceiptView(BaseModel):
    id: str
    contract_id: str
    invoice_id: str
    partner_id: str
    reference_month: int
    filename: str
    total_paid: Decimal
    fruicao_amount: Decimal
    amortizacao_amount: Decimal
    tax_withheld: Decimal
    authenticity_hash: str
    customer_route: str
    vault_s3_uri: str
    email_status: str
    push_status: str
    issued_at: datetime


class ReconciliationBatchView(ORMModel):
    id: str
    source: str
    status: str
    total_records: int
    matched_records: int
    divergent_records: int
    created_at: datetime


class ReconciliationItemView(ORMModel):
    id: str
    batch_id: str
    invoice_id: str | None
    external_reference: str
    external_event_id: str
    expected_amount: Decimal
    received_amount: Decimal
    payment_date: date | None
    status: str
    reason: str | None
    resolved_at: datetime | None
    resolution_note: str | None


class ReconciliationResolveRequest(BaseModel):
    decision: str
    note: str = Field(min_length=3, max_length=500)


class DelinquencyView(ORMModel):
    id: str
    invoice_id: str
    days_overdue: int
    penalty_amount: Decimal
    late_interest_amount: Decimal
    status: str
    caducity_eligible: bool


class NinaDistressCaseCreate(BaseModel):
    delinquency_case_id: str
    appraisal_value_avm: Decimal | None = Field(default=None,gt=0)
    photo_storage_reference: str | None = Field(default=None,max_length=500)
    matched_quota_id: str | None = None
    daily_reduction_amount: Decimal = Field(default=500,gt=0)


class NinaDistressCaseView(ORMModel):
    id: str; delinquency_case_id: str; operation_id: str | None; stage: str; days_overdue: int
    fiscal_check_status: str; cash_hold_status: str; legal_notice_status: str
    caducity_status: str; auction_status: str; appraisal_value_avm: Decimal | None
    opening_price_percent: Decimal; floor_price_percent: Decimal; daily_reduction_amount: Decimal
    current_auction_price: Decimal | None; voluntary_vacate_deadline: datetime | None
    photo_storage_reference: str | None; matched_quota_id: str | None; legal_hold: bool
    next_action_at: datetime | None; created_at: datetime


class NinaTimelineEvaluateRequest(BaseModel):
    as_of: date | None = None


class NinaApprovalRequest(BaseModel):
    gate: str; decision: str; notes: str = Field(min_length=5,max_length=1000)


class NinaCriticalApprovalView(ORMModel):
    id: str; case_id: str; gate: str; decision: str; notes: str; approver_id: str; decided_at: datetime


class NinaGateApplyRequest(BaseModel):
    gate: str


class NinaDocumentCreate(BaseModel):
    document_type: str; variables: dict = Field(default_factory=dict)


class NinaLegalDocumentView(ORMModel):
    id: str; case_id: str; document_type: str; version: int; status: str
    content_hash: str; created_at: datetime; content: dict = Field(default_factory=dict)


class NinaDistressEventView(ORMModel):
    id: str; case_id: str; event_key: str; event_type: str; status: str
    evidence_hash: str; actor_id: str | None; occurred_at: datetime; payload: dict = Field(default_factory=dict)


class CollectionActionView(ORMModel):
    id: str
    invoice_id: str
    action_type: str
    channel: str
    status: str
    scheduled_at: datetime
    executed_at: datetime | None


class LeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    document: str | None = None
    phone: str = Field(min_length=8, max_length=30)
    product_interest: str
    source: str = "DIRECT"


class LeadUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    phone: str | None = Field(default=None, min_length=8, max_length=30)
    product_interest: str | None = None
    status: str | None = None
    source: str | None = None


class LeadView(ORMModel):
    id: str
    name: str
    phone: str
    product_interest: str
    status: str
    source: str
    scr_status: str | None = None
    scr_reference: str | None = None
    scr_consulted_at: datetime | None = None
    created_at: datetime


class AdministratorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    document: str = Field(min_length=14, max_length=20)
    code: str | None = Field(default=None, min_length=2, max_length=40)


class AdministratorRulesUpdate(BaseModel):
    rules: dict
    bump_version: bool = True


class AdministratorHomologate(BaseModel):
    approved: bool
    notes: str | None = Field(default=None, max_length=2000)


class AdministratorView(BaseModel):
    id: str
    code: str | None
    name: str
    document: str
    authorization_status: str
    rules: dict
    rules_version: int
    bacen_rules_synced_at: datetime | None = None
    homologated_at: datetime | None
    homologated_by_id: str | None
    homologation_notes: str | None
    created_at: datetime
    updated_at: datetime


class BacenAdministratorRulesSyncView(BaseModel):
    total: int
    changed: int
    mode: str
    synced_at: str
    administrators: list[dict]


class BacenScrStatusView(BaseModel):
    provider: str
    configured: bool
    mode: str
    institution_code: str | None
    message: str


class QuotaCreate(BaseModel):
    administrator_id: str
    group_code: str
    quota_code: str
    category: str
    credit_value: Decimal = Field(gt=0)
    outstanding_balance: Decimal = Field(ge=0, default=0)
    premium_value: Decimal = Field(ge=0, default=0)
    installment_due_date: date | None = None


class QuotaUpdate(BaseModel):
    credit_value: Decimal | None = Field(default=None, gt=0)
    outstanding_balance: Decimal | None = Field(default=None, ge=0)
    premium_value: Decimal | None = Field(default=None, ge=0)
    installment_due_date: date | None = None
    status: str | None = None


class QuotaView(ORMModel):
    id: str
    administrator_id: str
    group_code: str
    quota_code: str
    category: str
    credit_value: Decimal
    outstanding_balance: Decimal
    premium_value: Decimal
    installment_due_date: date | None
    nina_scan_status: str | None
    nina_scanned_at: datetime | None
    status: str
    created_at: datetime


class NinaQuotaScanView(BaseModel):
    quota_id: str
    status: str
    scanned_at: datetime
    message: str


class ReservationCreate(BaseModel):
    quota_id: str
    proposal_id: str | None = None
    ttl_minutes: int = Field(default=60, ge=5, le=2880)


class ReservationView(ORMModel):
    id: str
    quota_id: str
    proposal_id: str | None
    status: str
    expires_at: datetime
    created_at: datetime


class ProposalCreate(BaseModel):
    lead_id: str
    product: str
    requested_amount: Decimal = Field(gt=0)
    terms: dict = Field(default_factory=dict)


class ProposalUpdate(BaseModel):
    status: str | None = None
    requested_amount: Decimal | None = Field(default=None, gt=0)
    terms: dict | None = None


class ProposalView(ORMModel):
    id: str
    lead_id: str
    product: str
    requested_amount: Decimal
    status: str
    calculation_version: str
    created_at: datetime


class CalculationRequest(BaseModel):
    quota_ids: list[str] = Field(min_length=1)
    fee_percent: Decimal = Field(default=Decimal("10"), ge=0, le=100)
    start_fee: Decimal = Field(default=Decimal("0"), ge=0)


class SdcCalculationRequest(BaseModel):
    quota_ids: list[str] = Field(min_length=1)
    duration_months: int = Field(default=12, ge=1, le=60)
    capital_source: str = Field(default="POOL")
    pool_investment_amount: Decimal | None = Field(
        default=None, gt=0,
        description="Valor aplicado pelo investidor no pool (rentabilidade fixa 1,6% a.m.).",
    )
    pool_investor_rate_percent: Decimal | None = Field(
        default=None, ge=0, le=4.5,
        description="Repasse manual aos investidores do pool (campanha). Sobrescreve faixa automática.",
    )


class FlashCreditCalculationRequest(BaseModel):
    asset_value: Decimal = Field(gt=0)
    capital_source: str
    term_months: int = Field(default=36)
    ipca_annual_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    pool_investment_amount: Decimal | None = Field(
        default=None, gt=0,
        description="Valor aplicado pelo investidor no pool (rentabilidade fixa 1,6% a.m.).",
    )
    pool_investor_rate_percent: Decimal | None = Field(
        default=None, ge=0, le=2.5,
        description="Repasse manual aos investidores do pool (campanha). Sobrescreve faixa automática.",
    )


class FlashSimulatorRequest(BaseModel):
    asset_value: Decimal = Field(gt=0)
    requested_amount: Decimal | None = Field(default=None,gt=0)
    ipca_projected_percent: Decimal = Field(default=Decimal("4.5"),ge=0,le=100)


class SettlementCurveRequest(BaseModel):
    principal: Decimal = Field(gt=0)
    track: str
    ipca_projected_percent: Decimal = Field(default=Decimal("4.5"),ge=0,le=100)
    balloon: bool = False


class ContractSettlementRequest(BaseModel):
    current_installment: int = Field(ge=1,le=36)
    track: str
    balloon: bool = False
    ipca_projected_percent: Decimal = Field(default=Decimal("4.5"),ge=0,le=100)


class FlashCapitalSimulationParamsView(BaseModel):
    institutional_rate_annual: str
    retail_rate_monthly: str
    default_ipca_projected_percent: str
    labels: dict[str, str]
    source: str
    policy_id: str | None = None
    policy_version: int | None = None
    nota: str


class FlashCapitalSimulationParamsUpdate(BaseModel):
    institutional_rate_annual: Decimal = Field(default=Decimal("14"), ge=0, le=100)
    retail_rate_monthly: Decimal = Field(default=Decimal("2.5"), ge=0, le=100)


class EarlySettlementQuoteView(ORMModel):
    id: str
    contract_id: str
    installment_number: int
    track: str
    balloon: bool
    principal: Decimal
    settlement_amount: Decimal
    future_interest_discount: Decimal
    calculation_hash: str
    status: str
    expires_at: datetime
    created_at: datetime


class FinOpsEventCreate(BaseModel):
    event_id: str = Field(min_length=8,max_length=120)
    event_type: str = Field(min_length=3,max_length=80)
    aggregate_id: str = Field(min_length=3,max_length=120)
    payload: dict


class FinOpsEventView(ORMModel):
    id: str
    event_id: str
    event_type: str
    aggregate_id: str
    payload_hash: str
    signature_valid: bool
    decision: str
    execution_mode: str
    received_at: datetime


class TapafSplitPolicyView(BaseModel):
    nominal_brl: str
    lote_a_api_reserve_brl: str
    lote_b_franchise_spread_brl: str
    estimated_api_cost_brl: str
    estimated_infra_margin_brl: str


class TapafSettlementView(BaseModel):
    id: str
    track: str
    entity_type: str
    entity_id: str
    payment_event_id: str
    total_brl: str
    lote_a_api_reserve_brl: str
    lote_b_franchise_spread_brl: str
    ledger_reference: str
    inventory: dict
    created_at: str | None = None


class InfraProviderCatalogItem(BaseModel):
    code: str
    name: str
    category: str
    estimated_cost_brl: str
    configured: bool
    production_ready: bool = False


class SdcBulletPreviewRequest(BaseModel):
    capital: Decimal = Field(gt=0)
    turnover_days: int
    commission_pool: Decimal = Field(ge=0)
    level3_available: bool = True


class FlashCreditPolicyCreate(BaseModel):
    version: int = Field(ge=1)
    max_ltv_percent: Decimal = Field(default=Decimal("40"),gt=0,le=100)
    institutional_rate_annual: Decimal = Field(default=Decimal("14"),ge=0)
    retail_rate_monthly: Decimal = Field(default=Decimal("2.5"),ge=0)
    investor_rate_monthly: Decimal = Field(default=Decimal("1.6"),ge=0)
    treasury_spread_monthly: Decimal = Field(default=Decimal("0.9"),ge=0)
    auction_steps_json: str = "[100,80,70,60]"
    auction_floor_percent: Decimal = Field(default=Decimal("60"),gt=0,le=100)
    intermediation_fee_percent: Decimal = Field(default=Decimal("10"),ge=0,le=100)


class FlashCreditPolicyView(ORMModel):
    id: str
    version: int
    status: str
    max_ltv_percent: Decimal
    institutional_rate_annual: Decimal
    retail_rate_monthly: Decimal
    investor_rate_monthly: Decimal
    treasury_spread_monthly: Decimal
    auction_steps_json: str
    auction_floor_percent: Decimal
    intermediation_fee_percent: Decimal
    approved_at: datetime | None


class NinaRoutingPolicyCreate(BaseModel):
    version: int = Field(ge=1)
    population_threshold: int = Field(ge=0,default=100000)
    income_per_capita_threshold: Decimal = Field(ge=0,default=Decimal("30000"))
    tapaf_amount: Decimal = Field(gt=0,default=Decimal("1500"))
    accepted_encumbrances_json: str = '["BANK_MORTGAGE","HOME_EQUITY","ACTIVE_MORTGAGE_FINANCING"]'
    rejected_encumbrances_json: str = '["JUDICIAL_BLOCK","JUDICIAL_LIEN","ATTACHMENT","SEIZURE","TAX_EMBARGO"]'


class NinaRoutingPolicyView(ORMModel):
    id: str
    version: int
    population_threshold: int
    income_per_capita_threshold: Decimal
    tapaf_amount: Decimal
    accepted_encumbrances_json: str
    rejected_encumbrances_json: str
    status: str
    approved_at: datetime | None


class NinaRoutingAssessmentCreate(BaseModel):
    asset_type: str
    municipality_code: str = Field(min_length=2,max_length=20)
    population: int = Field(ge=0)
    income_per_capita: Decimal = Field(ge=0)
    encumbrances: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    tapaf_evidence_reference: str | None = Field(default=None,max_length=200)
    vehicle_plate: str | None = Field(default=None, max_length=10)
    vehicle_renavam: str | None = Field(default=None, max_length=20)
    vehicle_uf: str | None = Field(default=None, min_length=2, max_length=2)
    vehicle_class: str | None = Field(default=None, description="LIGHT, HEAVY ou MACHINE")


class NinaRoutingAssessmentView(BaseModel):
    id: str
    proposal_id: str
    policy_id: str
    version: int
    asset_type: str
    municipality_code: str
    population: int
    income_per_capita: Decimal
    encumbrances: list[str]
    risk_flags: list[str]
    tapaf_evidence_reference: str | None
    physical_appraisal_required: bool
    product_route: str
    capital_route: str | None
    status: str
    blockers: list[str]
    evidence_hash: str
    approved_at: datetime | None
    created_at: datetime


class FlashCreditPartiesCreate(BaseModel):
    borrower_cnpj: str = Field(min_length=14,max_length=18)
    property_owner_type: str
    property_owner_document: str = Field(min_length=11,max_length=20)
    legal_representative_document: str | None = Field(default=None,max_length=20)
    liveness_reference: str | None = Field(default=None,max_length=200)
    qsa_representative_match: bool | None = None
    consent_confirmation: bool = False


class FlashCreditRouteView(BaseModel):
    borrower_pj: bool
    property_owner_type: str
    route: str
    dynamic_clause_blocks: list[str]


class ValidStampCreate(BaseModel):
    entity_type: str = Field(min_length=2,max_length=60)
    entity_id: str
    purpose: str = Field(min_length=3,max_length=80)
    payload: dict


class ValidStampView(ORMModel):
    id: str
    stamp_code: str
    entity_type: str
    entity_id: str
    purpose: str
    algorithm: str
    payload_hash: str
    previous_hash: str | None
    chain_hash: str
    status: str
    issued_at: datetime


class SaaSTermsCreate(BaseModel):
    code: str = Field(min_length=3,max_length=80)
    version: int = Field(ge=1)
    title: str = Field(min_length=3,max_length=200)
    body: str = Field(min_length=50)


class SaaSTermsView(ORMModel):
    id: str
    code: str
    version: int
    title: str
    body: str
    body_hash: str
    legal_review_status: str
    active: bool
    approved_at: datetime | None


class SaaSPlanCreate(BaseModel):
    code: str = Field(min_length=2,max_length=60)
    name: str = Field(min_length=3,max_length=160)
    monthly_price: Decimal = Field(default=Decimal("199.90"),gt=0)
    central_share_percent: Decimal = Field(default=Decimal("70"),ge=0,le=100)
    network_pool_percent: Decimal = Field(default=Decimal("30"),ge=0,le=100)


class SaaSPlanView(ORMModel):
    id: str
    code: str
    name: str
    monthly_price: Decimal
    central_share_percent: Decimal
    network_pool_percent: Decimal
    active: bool


class SaaSSubscribeCreate(BaseModel):
    plan_id: str
    terms_template_id: str
    company_name: str = Field(min_length=3,max_length=180)
    company_cnpj: str = Field(min_length=14,max_length=18)
    representative_name: str = Field(min_length=3,max_length=180)
    representative_document: str = Field(min_length=11,max_length=20)
    scroll_completed: bool
    terms_accepted: bool
    recurring_authorized: bool
    verification_reference: str = Field(min_length=3,max_length=200)
    payment_method_reference: str | None = Field(default=None,max_length=200)
    billing_type: str | None = Field(default=None, max_length=30)
    subscriber_email: str | None = Field(default=None, max_length=255)
    subscriber_phone: str | None = Field(default=None, max_length=30)
    ip_address: str | None = None
    user_agent: str | None = None


class SaaSSubscriptionView(ORMModel):
    id: str
    plan_id: str
    terms_template_id: str
    subscriber_company_name: str
    subscriber_document_masked: str
    legal_representative_name: str
    legal_representative_document_masked: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    cancelled_at: datetime | None
    recurring_authorized: bool
    acceptance_hash: str
    billing_type: str | None = None
    subscriber_email: str | None = None
    asaas_subscription_id: str | None = None
    last_payment_id: str | None = None
    last_payment_status: str | None = None
    payment_checkout_url: str | None = None
    created_at: datetime


class CalculationView(BaseModel):
    id: str
    proposal_id: str
    version: int
    formula_version: str
    input: dict
    output: dict
    approved_at: datetime | None = None
    quitcon_sdc: dict | None = None


class SdcQuitConProjectionRequest(BaseModel):
    saldo_devedor_simulado: Decimal = Field(gt=0)
    meses_restantes: int | None = Field(default=None, ge=0, le=600)


class SdcQuitConIntegrationView(BaseModel):
    card: dict
    projecao_temporal: dict


class SdcStartQuitConRequest(BaseModel):
    proposal_id: str | None = None
    contract_id: str | None = None
    calculation_memory_id: str | None = None
    meses_restantes: int | None = Field(default=None, ge=0, le=600)
    confirmation: bool = True


class SdcStartQuitConResponse(BaseModel):
    created: bool
    operacao_id: str
    operacao_code: str
    status: str
    quitcon_sdc: dict
    tapaf_checkout: dict
    next_step: str
    finops_route: str
    message: str


class ContractCreate(BaseModel):
    calculation_memory_id: str


class ContractAccept(BaseModel):
    confirmation: bool
    ip_address: str | None = None
    user_agent: str | None = None


class ContractView(ORMModel):
    id: str
    proposal_id: str
    calculation_memory_id: str
    contract_number: str
    status: str
    template_version: str
    content_hash: str
    accepted_at: datetime | None


class AcceptanceTemplateCreate(BaseModel):
    acceptance_type: str
    version: int = Field(ge=1)
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=20)


class AcceptanceTemplateView(ORMModel):
    id: str
    acceptance_type: str
    version: int
    title: str
    body: str
    body_hash: str
    legal_review_status: str
    active: bool
    approved_at: datetime | None


class CheckoutAcceptanceCreate(BaseModel):
    confirmation: bool
    read_full_contract: bool
    ip_address: str | None = None
    user_agent: str | None = None


class TransactionAcceptanceView(ORMModel):
    id: str
    contract_id: str
    template_id: str
    acceptance_type: str
    accepted_by_id: str
    accepted_at: datetime
    evidence_hash: str
    ip_address: str | None
    user_agent: str | None


class TransferWindowCreate(BaseModel):
    administrator_reference: str = Field(min_length=3, max_length=200)
    quota_id: str | None = None


class TransferReleaseCreate(BaseModel):
    logged_into_administrator: bool
    quota_in_buyer_name: bool
    authorize_release: bool
    biometric_reference: str | None = Field(default=None, max_length=200)
    ip_address: str | None = None
    user_agent: str | None = None


class TransferDisputeCreate(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


class QuotaTransferVerificationView(ORMModel):
    id: str
    contract_id: str
    quota_id: str | None
    status: str
    administrator_reference: str
    transfer_reported_at: datetime | None
    audit_deadline_at: datetime | None
    confirmed_at: datetime | None
    disputed_at: datetime | None
    payout_unlocked: bool
    created_at: datetime


class SellerEvidenceAuditCreate(BaseModel):
    buyer_document: str = Field(min_length=11,max_length=20)
    seller_document: str = Field(min_length=11,max_length=20)
    statement_document_id: str
    protocol_document_id: str
    assignment_document_id: str
    statement_ocr_text: str = Field(min_length=10,max_length=20000)
    protocol_ocr_text: str = Field(min_length=10,max_length=20000)
    assignment_ocr_text: str = Field(min_length=10,max_length=20000)


class SellerEvidenceReview(BaseModel):
    decision: str
    notes: str = Field(min_length=5,max_length=1000)


class SellerEvidenceAuditView(ORMModel):
    id: str
    contract_id: str
    status: str
    buyer_document_masked: str
    seller_document_masked: str
    statement_contemplated: bool
    administrator_protocol: str | None
    parties_matched: bool
    signature_evidence_detected: bool
    manual_review_status: str
    rejection_reason: str | None
    evidence_hash: str
    reviewed_at: datetime | None
    created_at: datetime


class StructuredPropertyCreate(BaseModel):
    operation_id: str | None = None
    buyer_document: str = Field(min_length=11,max_length=20)
    seller_document: str = Field(min_length=11,max_length=20)
    has_lien_debt: bool = False
    unregistered_construction: bool = False
    land_appraisal_value: Decimal = Field(gt=0)
    future_appraisal_value: Decimal = Field(gt=0)
    estimated_debt: Decimal = Field(default=Decimal("0"),ge=0)


class PropertyDocumentAttach(BaseModel):
    document_id: str


class StructuredPropertyView(ORMModel):
    id: str
    operation_id: str | None
    case_reference: str
    buyer_document_masked: str
    seller_document_masked: str
    has_lien_debt: bool
    unregistered_construction: bool
    route: str
    land_appraisal_value: Decimal
    future_appraisal_value: Decimal
    gross_payout: Decimal
    estimated_debt: Decimal
    phase1_amount: Decimal
    phase2_amount: Decimal
    iq_status: str
    phase_status: str
    registration_deadline_at: datetime | None
    legal_hold: bool
    evidence_hash: str
    created_at: datetime


class StructuredPropertyEventView(ORMModel):
    id: str
    case_id: str
    event_key: str
    event_type: str
    status: str
    evidence_hash: str
    occurred_at: datetime


class DocumentView(ORMModel):
    id: str
    entity_type: str
    entity_id: str
    kind: str
    filename: str
    sha256: str
    status: str
    created_at: datetime


class SignatureCreate(BaseModel):
    signer_email: EmailStr
    signer_name: str | None = None


class SignatureComplete(BaseModel):
    confirmation: bool
    ip_address: str | None = None


class SignatureZapSignStatusView(BaseModel):
    configured: bool
    connected: bool
    provider: str = "ZAPSIGN"
    environment: str
    documents_total: int | None = None
    message: str


class SignatureView(ORMModel):
    id: str
    contract_id: str
    provider: str
    external_id: str
    signer_email: EmailStr
    status: str
    sent_at: datetime | None
    signed_at: datetime | None
    sign_url: str | None = None


class LedgerPostRequest(BaseModel):
    reference: str = Field(min_length=4, max_length=120)
    event_type: str
    description: str
    debit_account: str
    credit_account: str
    amount: Decimal = Field(gt=0)
    operation_id: str | None = None


class LedgerTransactionView(BaseModel):
    id: str
    reference: str
    event_type: str
    description: str
    amount: Decimal
    debit_account: str
    credit_account: str
    created_at: datetime


class AccountBalanceView(BaseModel):
    code: str
    name: str
    account_type: str
    balance: Decimal


class EscrowSubaccountProfile(BaseModel):
    name: str | None = Field(default=None, max_length=180)
    email: str | None = Field(default=None, max_length=255)
    cpf_cnpj: str | None = Field(default=None, max_length=20)
    mobile_phone: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=20)
    income_value: Decimal | None = Field(default=None, gt=0)
    address: str | None = Field(default=None, max_length=180)
    address_number: str | None = Field(default=None, max_length=20)
    complement: str | None = Field(default=None, max_length=80)
    province: str | None = Field(default=None, max_length=80)
    postal_code: str | None = Field(default=None, max_length=12)
    company_type: str | None = Field(default=None, max_length=30)
    birth_date: str | None = Field(default=None, max_length=10)


class EscrowCreate(BaseModel):
    operation_id: str | None = None
    create_subaccount: bool = True
    enable_escrow: bool = True
    profile: EscrowSubaccountProfile | None = None


class EscrowSubaccountPreviewView(BaseModel):
    name: str
    email: str
    cpf_cnpj: str
    mobile_phone: str
    income_value: str
    address: str
    address_number: str
    province: str
    postal_code: str
    person_type: str
    operation_id: str | None = None


class EscrowAsaasStatusView(BaseModel):
    configured: bool
    connected: bool
    provider: str = "ASAAS"
    wallet_id: str | None = None
    wallet_id_masked: str | None = None
    environment: str
    balance: str | None = None
    subaccounts_enabled: bool = False
    message: str


class EscrowView(ORMModel):
    id: str
    user_id: str | None = None
    operation_id: str | None
    provider: str
    external_account_id: str
    asaas_account_id: str | None = None
    subaccount_name: str | None = None
    bank_code: str | None = None
    bank_agency: str | None = None
    bank_account_number: str | None = None
    pix_key: str | None = None
    asaas_kyc_status: str | None = None
    asaas_commercial_status: str | None = None
    asaas_onboarding_url: str | None = None
    escrow_enabled: bool = True
    status: str
    available_balance: Decimal
    locked_balance: Decimal


class WalletTransferRequest(BaseModel):
    pix_key: str = Field(min_length=3, max_length=180)
    amount: Decimal = Field(gt=0)
    description: str | None = Field(default=None, max_length=200)


class WalletBillPaymentRequest(BaseModel):
    barcode: str = Field(min_length=10, max_length=120)
    amount: Decimal = Field(gt=0)
    description: str | None = Field(default=None, max_length=200)


class WalletPricingRowView(BaseModel):
    code: str
    label: str
    customer_amount: str
    applies_to: str
    billing_cycle_days: int | None = None


class EscrowBillingCycleView(BaseModel):
    status: str
    monthly_amount: str
    next_billing_at: str | None = None
    last_billed_at: str | None = None
    outstanding_amount: str
    billing_blocked: bool
    delinquent_since: str | None = None


class WalletEscrowBillingSyncView(BaseModel):
    processed: int
    items: list[dict]
    enabled: bool = True
    synced_at: str | None = None


class LssBillingSyncView(BaseModel):
    processed: int
    items: list[dict]
    enabled: bool = True
    synced_at: str | None = None


class LegalManualPublicView(BaseModel):
    slug: str
    title: str
    category: str
    product: str
    audience: str
    description: str
    requires_login: bool = True


class LegalManualView(LegalManualPublicView):
    filename: str
    available: bool
    size_bytes: int = 0


class EscrowWebhook(BaseModel):
    event_id: str = Field(min_length=4, max_length=120)
    event_type: str
    amount: Decimal = Field(gt=0)
    billing_type: str | None = Field(default=None, max_length=30)
    metadata: dict = Field(default_factory=dict)


class PayoutCreate(BaseModel):
    escrow_account_id: str
    beneficiary_name: str
    beneficiary_document: str
    pix_key: str
    amount: Decimal = Field(gt=0)
    condition_evidence: dict = Field(default_factory=dict)
    transfer_verification_id: str | None = None


class PayoutApprove(BaseModel):
    decision: str = "APPROVE"
    comment: str | None = Field(default=None, max_length=500)


class PayoutView(ORMModel):
    id: str
    escrow_account_id: str
    beneficiary_name: str
    beneficiary_document: str
    pix_key_masked: str
    amount: Decimal
    status: str
    provider_transaction_id: str | None
    transfer_verification_id: str | None
    created_at: datetime
    approval_count: int = 0


class ModuleView(BaseModel):
    key: str
    name: str
    description: str
    status: str
    route: str
    critical: bool = False


class DashboardSummary(BaseModel):
    leads: int
    available_quotas: int
    active_proposals: int
    active_operations: int
    modules: int
    financial_transactions_enabled: bool


class RecoveredAssetCreate(BaseModel):
    delinquency_case_id: str | None = None
    title: str = Field(min_length=3, max_length=180)
    asset_type: str = Field(min_length=3, max_length=40)
    public_description: str = Field(min_length=10)
    gated_details: dict = Field(default_factory=dict)
    appraisal_value: Decimal = Field(gt=0)
    debt_balance: Decimal = Field(ge=0)
    recovery_costs: Decimal = Field(ge=0, default=0)
    custody_reference: str = Field(min_length=4, max_length=120)


class RecoveredAssetView(ORMModel):
    id: str
    delinquency_case_id: str | None
    title: str
    asset_type: str
    public_description: str
    appraisal_value: Decimal
    debt_balance: Decimal
    recovery_costs: Decimal
    custody_reference: str
    status: str
    created_at: datetime


class AuctionLotCreate(BaseModel):
    asset_id: str
    opening_price: Decimal = Field(gt=0)
    reserve_price: Decimal = Field(gt=0)
    min_increment: Decimal = Field(gt=0)
    platform_fee_percent: Decimal = Field(ge=0, le=100, default=5)
    starts_at: datetime
    ends_at: datetime
    extension_minutes: int = Field(ge=1, le=60, default=5)


class AuctionLotView(ORMModel):
    id: str
    asset_id: str
    lot_number: str
    opening_price: Decimal
    reserve_price: Decimal
    min_increment: Decimal
    platform_fee_percent: Decimal
    starts_at: datetime
    ends_at: datetime
    extension_minutes: int
    status: str
    winning_bid_id: str | None
    created_at: datetime


class AuctionQualificationRequest(BaseModel):
    confirmation: bool


class AuctionQualificationView(ORMModel):
    id: str
    lot_id: str
    user_id: str
    status: str
    terms_version: str
    accepted_at: datetime


class AuctionBidCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=120)


class AuctionBidView(ORMModel):
    id: str
    lot_id: str
    bidder_id: str
    idempotency_key: str
    amount: Decimal
    status: str
    placed_at: datetime


class AuctionSettlementView(ORMModel):
    id: str
    lot_id: str
    winning_bid_id: str
    gross_amount: Decimal
    recovery_costs: Decimal
    debt_paid: Decimal
    platform_fee: Decimal
    owner_surplus: Decimal
    status: str
    settled_at: datetime


class TaxDocumentCreate(BaseModel):
    user_id: str
    reference_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    gross_amount: Decimal = Field(gt=0)
    tax_amount: Decimal = Field(ge=0, default=0)
    content: str = Field(min_length=10)

class TaxDocumentView(ORMModel):
    id: str; user_id: str; reference_month: str; document_number: str; provider: str
    gross_amount: Decimal; tax_amount: Decimal; status: str; issued_at: datetime

class TaxClosingRequest(BaseModel):
    reference_month: str = Field(pattern=r"^\d{4}-\d{2}$")

class TaxClosingView(ORMModel):
    id: str; reference_month: str; gross_commissions: Decimal; documented_amount: Decimal
    eligible_payout: Decimal; exception_count: int; status: str; closed_at: datetime | None

class TaxExceptionView(ORMModel):
    id: str; closing_id: str; user_id: str; reason: str; amount: Decimal; status: str
    resolved_at: datetime | None; resolution_note: str | None

class TaxExceptionResolve(BaseModel):
    note: str = Field(min_length=5,max_length=500)

class CommunicationTemplateCreate(BaseModel):
    key: str = Field(min_length=3,max_length=80); channel: str; subject: str | None = None
    body: str = Field(min_length=3); purpose: str = "TRANSACTIONAL"

class CommunicationTemplateView(ORMModel):
    id: str; key: str; channel: str; version: int; subject: str | None; body: str; purpose: str; active: bool

class CommunicationConsentRequest(BaseModel):
    subject_type: str; subject_id: str; channel: str; status: str; source: str = "PLATFORM"; evidence: dict = Field(default_factory=dict)

class CommunicationConsentView(ORMModel):
    id: str; subject_type: str; subject_id: str; channel: str; status: str; source: str; changed_at: datetime

class CommunicationSendRequest(BaseModel):
    template_id: str; subject_type: str; subject_id: str; destination: str
    idempotency_key: str = Field(min_length=8,max_length=120); variables: dict = Field(default_factory=dict)

class CommunicationDeliveryView(ORMModel):
    id: str; template_id: str; subject_type: str; subject_id: str; destination_masked: str
    status: str; rendered_body: str; provider_message_id: str | None; delivered_at: datetime | None; created_at: datetime


class UnderwritingPolicyCreate(BaseModel):
    product: str; minimum_score: int = Field(ge=0,le=1000,default=650)
    maximum_ltv_percent: Decimal = Field(gt=0,le=100,default=40)
    maximum_commitment_percent: Decimal = Field(gt=0,le=100,default=35)
    manual_review_score: int = Field(ge=0,le=1000,default=720); rules: dict = Field(default_factory=dict)

class UnderwritingPolicyView(ORMModel):
    id: str; product: str; version: int; minimum_score: int; maximum_ltv_percent: Decimal
    maximum_commitment_percent: Decimal; manual_review_score: int; active: bool; created_at: datetime

class UnderwritingAssessmentCreate(BaseModel):
    policy_id: str; monthly_income: Decimal = Field(gt=0); monthly_commitment: Decimal = Field(ge=0)
    asset_value: Decimal = Field(gt=0); external_score: int = Field(ge=0,le=1000)
    document_completeness_percent: Decimal = Field(ge=0,le=100); kyc_status: str

class UnderwritingAssessmentView(ORMModel):
    id: str; proposal_id: str; policy_id: str; version: int; score: int; risk_band: str
    recommendation: str; status: str; created_at: datetime
    explanation: dict = Field(default_factory=dict)

class UnderwritingDecisionCreate(BaseModel):
    decision: str; reason: str = Field(min_length=5,max_length=500)

class UnderwritingDecisionView(ORMModel):
    id: str; assessment_id: str; decision: str; reason: str; decided_by_id: str; decided_at: datetime

class QuotaRankingView(BaseModel):
    quota_ids: list[str]
    total_credit: Decimal
    deviation_percent: Decimal
    score: int
    administrator_id: str
    explanation: str


class MarketplaceClientProfile(BaseModel):
    monthly_income: Decimal = Field(gt=0)
    monthly_commitment: Decimal = Field(ge=0, default=0)
    asset_value: Decimal = Field(gt=0)
    asset_year: int = Field(ge=1980, le=2100)


class MarketplaceEsteira1Request(MarketplaceClientProfile):
    quota_id: str


class MarketplaceQuotaBrief(BaseModel):
    quota_id: str
    group_code: str
    quota_code: str
    category: str
    credit_value: str
    premium_value: str
    installment_due_date: str | None
    administrator_name: str | None
    status: str
    nina_scan_status: str | None


class MarketplaceMatchView(BaseModel):
    quota_ids: list[str]
    total_credit: str
    deviation_percent: str
    score: int
    administrator_id: str
    administrator_name: str | None = None
    explanation: str
    message: str | None = None
    quotas: list[MarketplaceQuotaBrief] = Field(default_factory=list)


class MarketplaceEsteira1Response(BaseModel):
    esteira: str
    eligible: bool
    quota: MarketplaceQuotaBrief
    blockers: list[str] = Field(default_factory=list)
    alternatives: list[MarketplaceMatchView] = Field(default_factory=list)
    message: str


class MarketplaceEsteira2Request(MarketplaceClientProfile):
    target_amount: Decimal = Field(gt=0)
    category: str


class MarketplaceEsteira2Response(BaseModel):
    esteira: str
    eligible: bool
    blockers: list[str] = Field(default_factory=list)
    matches: list[MarketplaceMatchView] = Field(default_factory=list)
    message: str

class BISummaryView(BaseModel):
    funnel: dict; portfolio: dict; risk: dict; funding: dict; recovery: dict

class OperationalJobCreate(BaseModel):
    job_type: str; idempotency_key: str = Field(min_length=8,max_length=120)
    payload: dict = Field(default_factory=dict); max_attempts: int = Field(ge=1,le=10,default=3)

class OperationalJobView(ORMModel):
    id: str; job_type: str; idempotency_key: str; status: str; attempts: int; max_attempts: int
    scheduled_at: datetime; completed_at: datetime | None; last_error: str | None; created_at: datetime

class JobProcessRequest(BaseModel):
    simulate_failure: bool = False

class TenantQuotaUpdate(BaseModel):
    api_requests_per_minute: int | None = Field(default=None,ge=10,le=10000)
    jobs_per_day: int | None = Field(default=None,ge=1,le=1000000)
    communications_per_day: int | None = Field(default=None,ge=1,le=10000000)
    storage_mb: int | None = Field(default=None,ge=10,le=10000000)

class TenantQuotaView(ORMModel):
    id: str; organization_id: str; api_requests_per_minute: int; jobs_per_day: int
    communications_per_day: int; storage_mb: int; active: bool

class SecurityEventView(ORMModel):
    id: str; organization_id: str | None; event_type: str; severity: str
    ip_address: str | None; subject: str | None; created_at: datetime


class PreAnalysisDocumentItem(BaseModel):
    code: str
    filename: str | None = None
    dpi: int | None = None
    present: bool = True
    illegible: bool = False
    rasurado: bool = False


class PreAnalysisValidateDocumentsRequest(BaseModel):
    proposal_id: str
    documents: list[PreAnalysisDocumentItem]


class PreAnalysisProposalRequest(BaseModel):
    proposal_id: str


class PreAnalysisTapafCheckoutAcceptRequest(BaseModel):
    proposal_id: str
    scroll_completed: bool
    checkbox_1: bool
    checkbox_2: bool


class PreAnalysisTapafPaymentWebhook(BaseModel):
    proposal_id: str
    event_id: str
    amount: Decimal = Field(gt=0)


class PreAnalysisEngineRequest(BaseModel):
    proposal_id: str
    adm_nome: str = "ANCORA"
    extratos_6_meses_data: dict = Field(default_factory=dict)
    parcela_simulada: Decimal | None = None
    valor_avaliacao_bem: Decimal = Field(default=Decimal("0"))
    saldo_devedor_cotas: Decimal | None = None
    ano_fabricacao_bem: int | None = None
    restricoes_cadastrais_bool: bool = False
    possui_gravame_bool: bool = False
    valor_gravame_anterior: Decimal = Field(default=Decimal("0"))


class PreAnalysisPautaView(BaseModel):
    id: str
    proposal_id: str
    pauta_code: str
    status: str
    documents: dict | list
    tapaf_scroll_completed: bool
    tapaf_checkbox_1: bool
    tapaf_checkbox_2: bool
    tapaf_payment_reference: str | None
    tapaf_paid_at: datetime | None
    client_result: dict | None
    valid_stamp_hash: str | None
    created_at: datetime


class LeaseEquityPautaCreate(BaseModel):
    proposal_id: str
    property_type: str = Field(description="URBANO_RESIDENCIAL | URBANO_COMERCIAL | LOTE_URBANO | GALPAO | RURAL")
    appraisal_value: Decimal = Field(gt=0)
    registry_number: str = Field(min_length=1, max_length=80)
    registry_office: str = Field(min_length=1, max_length=180)
    owner_user_id: str | None = None


class LeaseEquityTapafWebhook(BaseModel):
    pauta_id: str
    event_id: str = Field(min_length=4, max_length=120)
    amount: Decimal = Field(gt=0)


class LeaseEquityInspectionPhoto(BaseModel):
    filename: str
    source: str = Field(default="CAMERA_NATIVE")
    exif_timestamp_unix: int
    gps_latitude: float
    gps_longitude: float


class LeaseEquityInspectionRequest(BaseModel):
    pauta_id: str
    photos: list[LeaseEquityInspectionPhoto] = Field(min_length=3)


class LeaseEquityComplianceReview(BaseModel):
    pauta_id: str
    approved: bool
    blockers: list[str] | None = None


class LeaseEquityFundingCapture(BaseModel):
    pauta_id: str
    amount: Decimal = Field(gt=0)


class LeaseEquityActivateRequest(BaseModel):
    pauta_id: str
    manual: bool = False


class LeaseEquityAnticipationRequest(BaseModel):
    pauta_id: str
    parcelas_restantes: int = Field(default=36, ge=1, le=36)


class LeaseEquityMonthsRequest(BaseModel):
    pauta_id: str
    months_in_force: int = Field(ge=0, le=36)


class LeaseEquityLtvSimulateRequest(BaseModel):
    property_type: str
    appraisal_value: Decimal = Field(gt=0)


class LeaseEquityTokenizationRequest(BaseModel):
    pauta_id: str
    owner_uid: str | None = None


class NativeInspectionPhoto(BaseModel):
    filename: str
    source: str = Field(default="CAMERA_NATIVE")
    exif_timestamp_unix: int
    gps_latitude: float
    gps_longitude: float


class ContractNativeInspectionRequest(BaseModel):
    photos: list[NativeInspectionPhoto] = Field(min_length=3)


class CollateralNativeInspectionView(BaseModel):
    id: str
    product: str
    proposal_id: str
    contract_id: str | None
    lease_equity_pauta_id: str | None
    quitcon_operacao_id: str | None
    photos_count: int
    vault_s3_uri: str
    auction_evidence_ready: bool
    created_at: datetime
    updated_at: datetime


class LeaseEquityPautaView(BaseModel):
    id: str
    proposal_id: str
    pauta_code: str
    status: str
    property_type: str
    appraisal_value: str
    registry_number: str
    registry_office: str
    tapaf_payment_reference: str | None
    tapaf_paid_at: datetime | None
    compliance_dossier_uri: str | None
    inspection_photos_count: int
    funding_captured_amount: str
    funding_target_amount: str
    funding_capture_percent: str
    activation_at: datetime | None
    activated_manually: bool
    months_in_force: int
    anticipation_unlock_at: datetime | None
    credit_matrix: dict
    anticipation_preview: dict
    tokenization_json: dict | None
    created_at: datetime
    updated_at: datetime


class QuitConOperacaoCreate(BaseModel):
    proposal_id: str
    outstanding_balance: Decimal = Field(gt=0)
    registry_number: str = Field(min_length=1, max_length=80)
    registry_office: str = Field(min_length=1, max_length=180)
    property_type: str = Field(default="CONSORCIO", description="Metadado da operação — não define LTV")
    appraisal_value: Decimal | None = Field(default=None, gt=0, description="Referência opcional de avaliação")
    quota_id: str | None = None
    owner_user_id: str | None = None
    meses_restantes: int = Field(default=48, ge=1, le=600)
    operational_service: bool = False
    contemplada: bool = True
    bem_faturado: bool = True
    parcelas_em_dia: bool = True


class QuitConPublicSimulateRequest(BaseModel):
    outstanding_balance: Decimal = Field(gt=0)
    meses_restantes: int = Field(ge=1, le=600)
    operational_service: bool = False
    administrator_name: str | None = None
    contemplada: bool = True
    bem_faturado: bool = True
    parcelas_em_dia: bool = True


class PublicLeadCaptureRequest(BaseModel):
    razao_social: str = Field(min_length=2, max_length=180)
    whatsapp: str = Field(min_length=8, max_length=30)
    produto: str = Field(description="flash ou sdc")
    valor_base: Decimal | None = Field(default=None, gt=0)
    autorizacao_scr_bacen: bool = False
    document: str | None = Field(default=None, min_length=11, max_length=20)
    referral_code: str | None = Field(default=None, min_length=6, max_length=40)


class PublicClientRegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    email: EmailStr
    phone: str = Field(min_length=8, max_length=30)
    password: str = Field(min_length=10, max_length=128)
    document: str | None = Field(default=None, min_length=11, max_length=20)
    referral_code: str | None = Field(default=None, min_length=6, max_length=40)
    terms_accepted: bool = False


class PublicReferralPreview(BaseModel):
    valid: bool
    referral_code: str | None = None
    referrer_name: str | None = None
    message: str | None = None


class PublicClientRegisterResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserView
    referrer: PublicReferralPreview | None = None
    lead_id: str


class PublicFlashPoolRequest(BaseModel):
    asset_value: Decimal = Field(gt=0)
    requested_amount: Decimal | None = Field(default=None, gt=0)


class PublicSdcSimulateRequest(BaseModel):
    quota_ids: list[str] = Field(min_length=1)
    requested_amount: Decimal = Field(gt=0)
    duration_months: int = Field(ge=1, le=120)
    capital_source: str = "POOL"


class PublicQuotaCatalogItem(BaseModel):
    id: str
    group_code: str
    quota_code: str
    category: str
    credit_value: str
    status: str


class QuitConSuccessFeeWebhook(BaseModel):
    operacao_id: str
    event_id: str = Field(min_length=4, max_length=120)
    amount: Decimal = Field(gt=0)


class QuitConOperationalServiceWebhook(BaseModel):
    operacao_id: str
    event_id: str = Field(min_length=4, max_length=120)
    amount: Decimal = Field(gt=0)


class QuitConCedentePaymentWebhook(BaseModel):
    operacao_id: str
    event_id: str = Field(min_length=4, max_length=120)
    amount: Decimal = Field(gt=0)


class QuitConAdminRejectionRequest(BaseModel):
    operacao_id: str
    reason: str | None = None


class QuitConTapafWebhook(BaseModel):
    operacao_id: str
    event_id: str = Field(min_length=4, max_length=120)
    amount: Decimal = Field(gt=0)


class QuitConInspectionRequest(BaseModel):
    operacao_id: str
    photos: list[LeaseEquityInspectionPhoto] = Field(min_length=3)


class QuitConComplianceReview(BaseModel):
    operacao_id: str
    approved: bool
    blockers: list[str] | None = None


class QuitConFundingCapture(BaseModel):
    operacao_id: str
    amount: Decimal = Field(gt=0)


class QuitConActivateRequest(BaseModel):
    operacao_id: str
    manual: bool = False


class QuitConSimulateRequest(BaseModel):
    outstanding_balance: Decimal = Field(gt=0)
    meses_restantes: int = Field(default=48, ge=1, le=600)
    operational_service: bool = False
    administrator_name: str | None = None
    contemplada: bool = True
    bem_faturado: bool = True
    parcelas_em_dia: bool = True
    appraisal_value: Decimal | None = Field(default=None, gt=0)


class QuitConTokenizationRequest(BaseModel):
    operacao_id: str
    owner_uid: str | None = None


class QuitConCancelInadimplenciaRequest(BaseModel):
    operacao_id: str
    days_overdue: int = Field(ge=1)


class QuitConOperacaoView(BaseModel):
    id: str
    proposal_id: str
    quota_id: str | None
    operacao_code: str
    status: str
    property_type: str
    appraisal_value: str
    outstanding_balance: str
    registry_number: str
    registry_office: str
    tapaf_payment_reference: str | None
    tapaf_paid_at: datetime | None
    compliance_dossier_uri: str | None
    inspection_photos_count: int
    administrator_approved_at: datetime | None
    sla_estimated_completion_at: datetime | None
    sla_dias_estimados: int
    success_fee_escrow_amount: str
    funding_captured_amount: str
    funding_target_amount: str
    funding_capture_percent: str
    activation_at: datetime | None
    activated_manually: bool
    cancellation_reason: str | None
    penalty_amount: str | None
    penalty_detail_json: dict | None
    credit_matrix: dict
    penalty_preview: dict | None
    tokenization_json: dict | None
    meses_restantes: int | None = None
    quitacao_vp_amount: str | None = None
    operational_service_enabled: bool = False
    operational_service_fee_amount: str | None = None
    operational_service_paid_at: datetime | None = None
    success_fee_escrow_paid_at: datetime | None = None
    success_fee_refunded: bool = False
    cedente_payment_amount: str | None = None
    cedente_payment_due_at: datetime | None = None
    cedente_payment_escrow_reference: str | None = None
    product_snapshot: dict | None = None
    custos_entrada: dict | None = None
    created_at: datetime
    updated_at: datetime


class LegacyMigrationBundle(BaseModel):
    legacy_source: str | None = None
    source_label: str | None = None
    entities: dict[str, list[dict[str, object]]] = Field(default_factory=dict)


class LegacyMigrationRunView(BaseModel):
    id: str
    legacy_source: str
    mode: str
    status: str
    error_message: str | None = None
    summary: dict[str, object] = Field(default_factory=dict)
    started_by_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class LegacyIdMapView(BaseModel):
    id: str
    legacy_source: str
    entity_type: str
    legacy_id: str
    new_id: str
    migration_run_id: str | None = None
    created_at: str | None = None

