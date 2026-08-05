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


class InviteAccept(BaseModel):
    token: str
    name: str = Field(min_length=2, max_length=180)
    document: str | None = None
    password: str = Field(min_length=10)


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
    created_at: datetime


class QuotaCreate(BaseModel):
    administrator_id: str
    group_code: str
    quota_code: str
    category: str
    credit_value: Decimal = Field(gt=0)
    outstanding_balance: Decimal = Field(ge=0, default=0)
    premium_value: Decimal = Field(ge=0, default=0)


class QuotaUpdate(BaseModel):
    credit_value: Decimal | None = Field(default=None, gt=0)
    outstanding_balance: Decimal | None = Field(default=None, ge=0)
    premium_value: Decimal | None = Field(default=None, ge=0)
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
    status: str
    created_at: datetime


class ReservationCreate(BaseModel):
    quota_id: str
    proposal_id: str | None = None
    ttl_minutes: int = Field(default=30, ge=5, le=2880)


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


class FlashCreditCalculationRequest(BaseModel):
    asset_value: Decimal = Field(gt=0)
    capital_source: str
    term_months: int = Field(default=36)
    ipca_annual_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class CalculationView(BaseModel):
    id: str
    proposal_id: str
    version: int
    formula_version: str
    input: dict
    output: dict
    approved_at: datetime | None = None


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


class SignatureComplete(BaseModel):
    confirmation: bool
    ip_address: str | None = None


class SignatureView(ORMModel):
    id: str
    contract_id: str
    provider: str
    external_id: str
    signer_email: EmailStr
    status: str
    sent_at: datetime | None
    signed_at: datetime | None


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


class EscrowCreate(BaseModel):
    operation_id: str | None = None


class EscrowView(ORMModel):
    id: str
    operation_id: str | None
    provider: str
    external_account_id: str
    status: str
    available_balance: Decimal
    locked_balance: Decimal


class EscrowWebhook(BaseModel):
    event_id: str = Field(min_length=4, max_length=120)
    event_type: str
    amount: Decimal = Field(gt=0)
    metadata: dict = Field(default_factory=dict)


class PayoutCreate(BaseModel):
    escrow_account_id: str
    beneficiary_name: str
    beneficiary_document: str
    pix_key: str
    amount: Decimal = Field(gt=0)
    condition_evidence: dict = Field(default_factory=dict)


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
    quota_ids: list[str]; total_credit: Decimal; deviation_percent: Decimal; score: int
    administrator_id: str; explanation: str

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
