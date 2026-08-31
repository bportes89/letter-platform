from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def uid() -> str:
    return str(uuid4())


class Role(StrEnum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    INTERNAL_STAFF = "INTERNAL_STAFF"
    MASTER_FRANCHISEE = "MASTER_FRANCHISEE"
    MANAGER = "MANAGER"
    PARTNER = "PARTNER"
    CLIENT = "CLIENT"
    QUOTA_SELLER = "QUOTA_SELLER"
    RETAIL_INVESTOR = "RETAIL_INVESTOR"
    INSTITUTIONAL_FUND = "INSTITUTIONAL_FUND"
    AUDITOR = "AUDITOR"


ROLE_SCOPES = {
    Role.PLATFORM_ADMIN: ["*"],
    Role.INTERNAL_STAFF: ["dashboard:read", "operations:write", "documents:write", "payments:review"],
    Role.MASTER_FRANCHISEE: ["dashboard:read", "network:read", "proposals:read"],
    Role.MANAGER: ["dashboard:read", "leads:read", "proposals:read"],
    Role.PARTNER: ["dashboard:read", "leads:write", "proposals:write", "wallet:read"],
    Role.CLIENT: ["dashboard:read", "proposals:read", "contracts:read", "payments:read"],
    Role.QUOTA_SELLER: ["dashboard:read", "inventory:write", "payments:read"],
    Role.RETAIL_INVESTOR: ["dashboard:read", "investments:read", "investments:reserve"],
    Role.INSTITUTIONAL_FUND: ["dashboard:read", "institutional:read", "investments:write"],
    Role.AUDITOR: ["dashboard:read", "audit:read"],
}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(180))
    document: Mapped[str | None] = mapped_column(String(20), unique=True)
    kind: Mapped[str] = mapped_column(String(40), default="HEADQUARTERS")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Branch(TimestampMixin, Base):
    __tablename__ = "branches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    code: Mapped[str] = mapped_column(String(40))
    region: Mapped[str | None] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    document: Mapped[str | None] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    mfa_secret: Mapped[str | None] = mapped_column(String(64))
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    organization: Mapped[Organization] = relationship()


class UserInvitation(TimestampMixin, Base):
    __tablename__ = "user_invitations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"))
    invited_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[Role] = mapped_column(Enum(Role))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    step_up_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasswordReset(Base):
    __tablename__ = "password_resets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class KycCase(TimestampMixin, Base):
    __tablename__ = "kyc_cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    subject_type: Mapped[str] = mapped_column(String(20))
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    provider: Mapped[str] = mapped_column(String(40), default="MOCK")
    external_id: Mapped[str] = mapped_column(String(120), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    risk_level: Mapped[str | None] = mapped_column(String(20))
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(180))
    document: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str] = mapped_column(String(30))
    product_interest: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(40), default="NEW")
    source: Mapped[str] = mapped_column(String(80), default="DIRECT")


class Administrator(TimestampMixin, Base):
    __tablename__ = "administrators"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(180), unique=True)
    document: Mapped[str] = mapped_column(String(20), unique=True)
    authorization_status: Mapped[str] = mapped_column(String(40), default="PENDING_REVIEW")
    rules_json: Mapped[str] = mapped_column(Text, default="{}")


class Quota(TimestampMixin, Base):
    __tablename__ = "quotas"
    __table_args__ = (UniqueConstraint("administrator_id", "group_code", "quota_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    administrator_id: Mapped[str] = mapped_column(ForeignKey("administrators.id"))
    seller_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    group_code: Mapped[str] = mapped_column(String(60))
    quota_code: Mapped[str] = mapped_column(String(60))
    category: Mapped[str] = mapped_column(String(30))
    credit_value: Mapped[float] = mapped_column(Numeric(15, 2))
    outstanding_balance: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    premium_value: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    status: Mapped[str] = mapped_column(String(40), default="AVAILABLE")
    administrator: Mapped[Administrator] = relationship()


class QuotaReservation(TimestampMixin, Base):
    __tablename__ = "quota_reservations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    quota_id: Mapped[str] = mapped_column(ForeignKey("quotas.id"), index=True)
    reserved_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("proposals.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(String(120))


class Proposal(TimestampMixin, Base):
    __tablename__ = "proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"))
    product: Mapped[str] = mapped_column(String(50))
    requested_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    status: Mapped[str] = mapped_column(String(50), default="DRAFT")
    calculation_version: Mapped[str] = mapped_column(String(30), default="v1")
    terms_json: Mapped[str] = mapped_column(Text, default="{}")


class CalculationMemory(TimestampMixin, Base):
    __tablename__ = "calculation_memories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    version: Mapped[int] = mapped_column(default=1)
    product: Mapped[str] = mapped_column(String(50))
    input_json: Mapped[str] = mapped_column(Text)
    output_json: Mapped[str] = mapped_column(Text)
    formula_version: Mapped[str] = mapped_column(String(30), default="marketplace-v1")
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Contract(TimestampMixin, Base):
    __tablename__ = "contracts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), unique=True)
    calculation_memory_id: Mapped[str] = mapped_column(ForeignKey("calculation_memories.id"))
    contract_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="DRAFT")
    template_version: Mapped[str] = mapped_column(String(30), default="marketplace-v1")
    content_hash: Mapped[str] = mapped_column(String(64))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")


class AcceptanceTemplate(TimestampMixin, Base):
    __tablename__ = "acceptance_templates"
    __table_args__ = (UniqueConstraint("organization_id", "acceptance_type", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    acceptance_type: Mapped[str] = mapped_column(String(40), index=True)
    version: Mapped[int] = mapped_column(default=1)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    body_hash: Mapped[str] = mapped_column(String(64))
    legal_review_status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TransactionAcceptance(TimestampMixin, Base):
    __tablename__ = "transaction_acceptances"
    __table_args__ = (UniqueConstraint("contract_id", "acceptance_type"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("acceptance_templates.id"))
    acceptance_type: Mapped[str] = mapped_column(String(40), index=True)
    accepted_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    evidence_json: Mapped[str] = mapped_column(Text)
    evidence_hash: Mapped[str] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))


class QuotaTransferVerification(TimestampMixin, Base):
    __tablename__ = "quota_transfer_verifications"
    __table_args__ = (UniqueConstraint("contract_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    quota_id: Mapped[str | None] = mapped_column(ForeignKey("quotas.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="PENDING_TRANSFER", index=True)
    administrator_reference: Mapped[str] = mapped_column(String(200))
    transfer_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    audit_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disputed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payout_unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")


class SellerEvidenceAudit(TimestampMixin, Base):
    __tablename__ = "seller_evidence_audits"
    __table_args__ = (UniqueConstraint("contract_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="PENDING_OCR", index=True)
    buyer_document_masked: Mapped[str] = mapped_column(String(30))
    seller_document_masked: Mapped[str] = mapped_column(String(30))
    statement_document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    protocol_document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    assignment_document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    statement_contemplated: Mapped[bool] = mapped_column(Boolean, default=False)
    administrator_protocol: Mapped[str | None] = mapped_column(String(100))
    parties_matched: Mapped[bool] = mapped_column(Boolean, default=False)
    signature_evidence_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_review_status: Mapped[str] = mapped_column(String(30), default="PENDING")
    rejection_reason: Mapped[str | None] = mapped_column(String(1000))
    evidence_hash: Mapped[str] = mapped_column(String(64))
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StructuredPropertyCase(TimestampMixin, Base):
    __tablename__ = "structured_property_cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    operation_id: Mapped[str | None] = mapped_column(ForeignKey("operations.id"), unique=True, index=True)
    case_reference: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    buyer_document_masked: Mapped[str] = mapped_column(String(30))
    seller_document_masked: Mapped[str] = mapped_column(String(30))
    has_lien_debt: Mapped[bool] = mapped_column(Boolean, default=False)
    unregistered_construction: Mapped[bool] = mapped_column(Boolean, default=False)
    route: Mapped[str] = mapped_column(String(40), index=True)
    land_appraisal_value: Mapped[float] = mapped_column(Numeric(15, 2))
    future_appraisal_value: Mapped[float] = mapped_column(Numeric(15, 2))
    gross_payout: Mapped[float] = mapped_column(Numeric(15, 2))
    estimated_debt: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    phase1_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    phase2_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    iq_status: Mapped[str] = mapped_column(String(40), default="NOT_APPLICABLE", index=True)
    phase_status: Mapped[str] = mapped_column(String(40), default="AWAITING_REGISTRY", index=True)
    iq_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    registered_property_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    registration_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence_hash: Mapped[str] = mapped_column(String(64))


class StructuredPropertyEvent(Base):
    __tablename__ = "structured_property_events"
    __table_args__ = (UniqueConstraint("case_id", "event_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("structured_property_cases.id"), index=True)
    event_key: Mapped[str] = mapped_column(String(120), index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    evidence_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class FlashCreditPolicy(TimestampMixin, Base):
    __tablename__ = "flash_credit_policies"
    __table_args__ = (UniqueConstraint("organization_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    max_ltv_percent: Mapped[float] = mapped_column(Numeric(8, 4), default=40)
    institutional_rate_annual: Mapped[float] = mapped_column(Numeric(8, 4), default=14)
    retail_rate_monthly: Mapped[float] = mapped_column(Numeric(8, 4), default=2.5)
    investor_rate_monthly: Mapped[float] = mapped_column(Numeric(8, 4), default=1.6)
    treasury_spread_monthly: Mapped[float] = mapped_column(Numeric(8, 4), default=.9)
    auction_steps_json: Mapped[str] = mapped_column(Text, default="[100,80,70,60]")
    auction_floor_percent: Mapped[float] = mapped_column(Numeric(8, 4), default=60)
    intermediation_fee_percent: Mapped[float] = mapped_column(Numeric(8, 4), default=10)
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NinaRoutingPolicy(TimestampMixin, Base):
    __tablename__ = "nina_routing_policies"
    __table_args__ = (UniqueConstraint("organization_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    version: Mapped[int] = mapped_column(default=1)
    population_threshold: Mapped[int] = mapped_column(default=100000)
    income_per_capita_threshold: Mapped[float] = mapped_column(Numeric(15,2),default=30000)
    tapaf_amount: Mapped[float] = mapped_column(Numeric(15,2),default=1500)
    accepted_encumbrances_json: Mapped[str] = mapped_column(Text,default='["BANK_MORTGAGE","HOME_EQUITY","ACTIVE_MORTGAGE_FINANCING"]')
    rejected_encumbrances_json: Mapped[str] = mapped_column(Text,default='["JUDICIAL_BLOCK","JUDICIAL_LIEN","ATTACHMENT","SEIZURE","TAX_EMBARGO"]')
    status: Mapped[str] = mapped_column(String(30),default="DRAFT",index=True)
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NinaRoutingAssessment(TimestampMixin, Base):
    __tablename__ = "nina_routing_assessments"
    __table_args__ = (UniqueConstraint("proposal_id", "version"),)
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"),index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"),index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("nina_routing_policies.id"))
    version: Mapped[int] = mapped_column(default=1)
    asset_type: Mapped[str] = mapped_column(String(30))
    municipality_code: Mapped[str] = mapped_column(String(20))
    population: Mapped[int]
    income_per_capita: Mapped[float] = mapped_column(Numeric(15,2))
    encumbrances_json: Mapped[str] = mapped_column(Text,default="[]")
    risk_flags_json: Mapped[str] = mapped_column(Text,default="[]")
    tapaf_evidence_reference: Mapped[str | None] = mapped_column(String(200))
    physical_appraisal_required: Mapped[bool] = mapped_column(Boolean,default=True)
    product_route: Mapped[str] = mapped_column(String(50),index=True)
    capital_route: Mapped[str | None] = mapped_column(String(30),index=True)
    status: Mapped[str] = mapped_column(String(50),index=True)
    blockers_json: Mapped[str] = mapped_column(Text,default="[]")
    evidence_hash: Mapped[str] = mapped_column(String(64),unique=True)
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FlashCreditParty(TimestampMixin, Base):
    __tablename__ = "flash_credit_parties"
    __table_args__ = (UniqueConstraint("proposal_id", "party_role"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    party_role: Mapped[str] = mapped_column(String(40), index=True)
    person_type: Mapped[str] = mapped_column(String(10))
    document_masked: Mapped[str] = mapped_column(String(30))
    legal_representative_document_masked: Mapped[str | None] = mapped_column(String(30))
    qsa_match_status: Mapped[str] = mapped_column(String(30), default="NOT_APPLICABLE")
    liveness_reference: Mapped[str | None] = mapped_column(String(200))
    consent_status: Mapped[str] = mapped_column(String(30), default="PENDING")
    consent_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="PENDING_VALIDATION", index=True)


class ValidStamp(TimestampMixin, Base):
    __tablename__ = "valid_stamps"
    __table_args__ = (UniqueConstraint("organization_id", "stamp_code"), UniqueConstraint("organization_id", "entity_type", "entity_id", "purpose"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    stamp_code: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    purpose: Mapped[str] = mapped_column(String(80))
    algorithm: Mapped[str] = mapped_column(String(30), default="HMAC-SHA256")
    payload_hash: Mapped[str] = mapped_column(String(64))
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    chain_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    signature: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="VALID", index=True)
    issued_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EarlySettlementQuote(TimestampMixin, Base):
    __tablename__ = "early_settlement_quotes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    requested_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    installment_number: Mapped[int]
    track: Mapped[str] = mapped_column(String(30))
    balloon: Mapped[bool] = mapped_column(Boolean, default=False)
    principal: Mapped[float] = mapped_column(Numeric(15, 2))
    settlement_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    future_interest_discount: Mapped[float] = mapped_column(Numeric(15, 2))
    calculation_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(50), default="QUOTE_ONLY_SANDBOX", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class FinOpsDomainEvent(TimestampMixin, Base):
    __tablename__ = "finops_domain_events"
    __table_args__ = (UniqueConstraint("organization_id", "event_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    event_id: Mapped[str] = mapped_column(String(120), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(120), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    payload_hash: Mapped[str] = mapped_column(String(64))
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    decision: Mapped[str] = mapped_column(String(80), index=True)
    execution_mode: Mapped[str] = mapped_column(String(30), default="SANDBOX_NO_FUNDS")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class TapafSettlement(TimestampMixin, Base):
    __tablename__ = "tapaf_settlements"
    __table_args__ = (UniqueConstraint("organization_id", "payment_event_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    track: Mapped[str] = mapped_column(String(30), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    payment_event_id: Mapped[str] = mapped_column(String(120), index=True)
    total_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    lote_a_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    lote_b_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    ledger_reference: Mapped[str] = mapped_column(String(120), index=True)
    inventory_json: Mapped[str] = mapped_column(Text, default="{}")


class SaaSTermsTemplate(TimestampMixin, Base):
    __tablename__ = "saas_terms_templates"
    __table_args__ = (UniqueConstraint("organization_id", "code", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int] = mapped_column(default=1)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    body_hash: Mapped[str] = mapped_column(String(64))
    legal_review_status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SaaSPlan(TimestampMixin, Base):
    __tablename__ = "saas_plans"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(160))
    monthly_price: Mapped[float] = mapped_column(Numeric(15, 2), default=199.90)
    central_share_percent: Mapped[float] = mapped_column(Numeric(8, 4), default=70)
    network_pool_percent: Mapped[float] = mapped_column(Numeric(8, 4), default=30)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SaaSSubscription(TimestampMixin, Base):
    __tablename__ = "saas_subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("saas_plans.id"), index=True)
    terms_template_id: Mapped[str] = mapped_column(ForeignKey("saas_terms_templates.id"))
    subscriber_company_name: Mapped[str] = mapped_column(String(180))
    subscriber_document_masked: Mapped[str] = mapped_column(String(30))
    legal_representative_name: Mapped[str] = mapped_column(String(180))
    legal_representative_document_masked: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", index=True)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_method_reference: Mapped[str | None] = mapped_column(String(200))
    recurring_authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    acceptance_hash: Mapped[str] = mapped_column(String(64))


class SaaSAcceptance(Base):
    __tablename__ = "saas_acceptances"
    __table_args__ = (UniqueConstraint("subscription_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("saas_subscriptions.id"), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    terms_template_id: Mapped[str] = mapped_column(ForeignKey("saas_terms_templates.id"))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    verification_reference: Mapped[str] = mapped_column(String(200))
    evidence_json: Mapped[str] = mapped_column(Text)
    evidence_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="PENDING_REVIEW")
    uploaded_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class SignatureEnvelope(TimestampMixin, Base):
    __tablename__ = "signature_envelopes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), unique=True)
    provider: Mapped[str] = mapped_column(String(40), default="MOCK")
    external_id: Mapped[str] = mapped_column(String(120), unique=True)
    signer_email: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")


class Operation(TimestampMixin, Base):
    __tablename__ = "operations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), unique=True)
    product: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="PENDING_DOCUMENTS")
    capital_source: Mapped[str | None] = mapped_column(String(40))
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    valid_stamp_hash: Mapped[str | None] = mapped_column(String(64))


class LedgerTransaction(TimestampMixin, Base):
    __tablename__ = "ledger_transactions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    operation_id: Mapped[str | None] = mapped_column(ForeignKey("operations.id"))
    event_type: Mapped[str] = mapped_column(String(80))
    reference: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="POSTED")


class LedgerEntry(TimestampMixin, Base):
    __tablename__ = "ledger_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("ledger_transactions.id"), index=True)
    operation_id: Mapped[str | None] = mapped_column(ForeignKey("operations.id"))
    account: Mapped[str] = mapped_column(String(100))
    direction: Mapped[str] = mapped_column(String(10))
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    reference: Mapped[str] = mapped_column(String(120), index=True)


class ChartAccount(TimestampMixin, Base):
    __tablename__ = "chart_accounts"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    account_type: Mapped[str] = mapped_column(String(30))
    normal_balance: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class EscrowAccount(TimestampMixin, Base):
    __tablename__ = "escrow_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    operation_id: Mapped[str | None] = mapped_column(ForeignKey("operations.id"), unique=True)
    provider: Mapped[str] = mapped_column(String(40), default="MOCK")
    external_account_id: Mapped[str] = mapped_column(String(120), unique=True)
    asaas_account_id: Mapped[str | None] = mapped_column(String(120), index=True)
    subaccount_name: Mapped[str | None] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    available_balance: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    locked_balance: Mapped[float] = mapped_column(Numeric(15, 2), default=0)


class EscrowEvent(Base):
    __tablename__ = "escrow_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    escrow_account_id: Mapped[str] = mapped_column(ForeignKey("escrow_accounts.id"), index=True)
    provider_event_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60))
    amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    payload_json: Mapped[str] = mapped_column(Text)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class PayoutRequest(TimestampMixin, Base):
    __tablename__ = "payout_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    escrow_account_id: Mapped[str] = mapped_column(ForeignKey("escrow_accounts.id"), index=True)
    requested_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    beneficiary_name: Mapped[str] = mapped_column(String(180))
    beneficiary_document: Mapped[str] = mapped_column(String(20))
    pix_key_masked: Mapped[str] = mapped_column(String(180))
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    status: Mapped[str] = mapped_column(String(40), default="PENDING_APPROVAL", index=True)
    condition_evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    provider_transaction_id: Mapped[str | None] = mapped_column(String(120))
    transfer_verification_id: Mapped[str | None] = mapped_column(String(36), index=True)


class PayoutApproval(Base):
    __tablename__ = "payout_approvals"
    __table_args__ = (UniqueConstraint("payout_request_id", "approver_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    payout_request_id: Mapped[str] = mapped_column(ForeignKey("payout_requests.id"), index=True)
    approver_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(120))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class NetworkNode(TimestampMixin, Base):
    __tablename__ = "network_nodes"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", "tree_type"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    sponsor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    tree_type: Mapped[str] = mapped_column(String(20), default="SALES")
    referral_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")


class CommissionRule(TimestampMixin, Base):
    __tablename__ = "commission_rules"
    __table_args__ = (UniqueConstraint("organization_id", "product", "commission_type", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    product: Mapped[str] = mapped_column(String(50), index=True)
    commission_type: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(default=1)
    base_type: Mapped[str] = mapped_column(String(40), default="NET_PAYOUT")
    pool_rate_percent: Mapped[float] = mapped_column(Numeric(8, 4))
    levels_json: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CommissionEntry(TimestampMixin, Base):
    __tablename__ = "commission_entries"
    __table_args__ = (UniqueConstraint("reference", "beneficiary_id", "commission_type", "level"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    beneficiary_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    originator_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("proposals.id"), index=True)
    reference: Mapped[str] = mapped_column(String(120), index=True)
    product: Mapped[str] = mapped_column(String(50))
    commission_type: Mapped[str] = mapped_column(String(20))
    level: Mapped[int]
    calculation_base: Mapped[float] = mapped_column(Numeric(15, 2))
    pool_rate_percent: Mapped[float] = mapped_column(Numeric(8, 4))
    level_share_percent: Mapped[float] = mapped_column(Numeric(8, 4))
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    status: Mapped[str] = mapped_column(String(30), default="PENDING_FISCAL", index=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FiscalEvidence(TimestampMixin, Base):
    __tablename__ = "fiscal_evidences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    reference_month: Mapped[str] = mapped_column(String(7))
    provider: Mapped[str] = mapped_column(String(40), default="MOCK_PARSER")
    status: Mapped[str] = mapped_column(String(30), default="VALID")
    document_hash: Mapped[str] = mapped_column(String(64), unique=True)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class FundingOpportunity(TimestampMixin, Base):
    __tablename__ = "funding_opportunities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("proposals.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    product: Mapped[str] = mapped_column(String(50))
    capital_source: Mapped[str] = mapped_column(String(30), default="RETAIL")
    target_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    funded_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    min_investment: Mapped[float] = mapped_column(Numeric(15, 2), default=1000)
    annual_return_reference: Mapped[float | None] = mapped_column(Numeric(8, 4))
    status: Mapped[str] = mapped_column(String(30), default="OPEN", index=True)


class InvestmentReservation(TimestampMixin, Base):
    __tablename__ = "investment_reservations"
    __table_args__ = (UniqueConstraint("opportunity_id", "investor_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("funding_opportunities.id"), index=True)
    investor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    status: Mapped[str] = mapped_column(String(30), default="RESERVED", index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InvestmentPosition(TimestampMixin, Base):
    __tablename__ = "investment_positions"
    __table_args__ = (UniqueConstraint("opportunity_id", "investor_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("funding_opportunities.id"), index=True)
    investor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    principal: Mapped[float] = mapped_column(Numeric(15, 2))
    accrued_return: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("contract_id", "installment_number", "kind"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    invoice_number: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    installment_number: Mapped[int]
    kind: Mapped[str] = mapped_column(String(30), default="INSTALLMENT")
    due_date: Mapped[date] = mapped_column(Date, index=True)
    principal_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    interest_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    fee_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    paid_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    provider_event_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    status: Mapped[str] = mapped_column(String(30))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class PreAnalysisPauta(TimestampMixin, Base):
    __tablename__ = "pre_analysis_pautas"
    __table_args__ = (UniqueConstraint("organization_id", "proposal_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    pauta_code: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING_DOCUMENTS", index=True)
    documents_json: Mapped[str] = mapped_column(Text, default="[]")
    tapaf_scroll_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    tapaf_checkbox_1: Mapped[bool] = mapped_column(Boolean, default=False)
    tapaf_checkbox_2: Mapped[bool] = mapped_column(Boolean, default=False)
    tapaf_payment_reference: Mapped[str | None] = mapped_column(String(120))
    tapaf_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    engine_result_json: Mapped[str | None] = mapped_column(Text)
    client_result_json: Mapped[str | None] = mapped_column(Text)
    valid_stamp_hash: Mapped[str | None] = mapped_column(String(128))
    vault_s3_uri: Mapped[str | None] = mapped_column(String(500))


class LeaseEquityPauta(TimestampMixin, Base):
    __tablename__ = "lease_equity_pautas"
    __table_args__ = (UniqueConstraint("organization_id", "proposal_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    pauta_code: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(50), default="AGUARDANDO_TAPAF", index=True)
    property_type: Mapped[str] = mapped_column(String(40))
    appraisal_value: Mapped[float] = mapped_column(Numeric(15, 2))
    registry_number: Mapped[str] = mapped_column(String(80))
    registry_office: Mapped[str] = mapped_column(String(180))
    tapaf_payment_reference: Mapped[str | None] = mapped_column(String(120))
    tapaf_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    compliance_dossier_uri: Mapped[str | None] = mapped_column(String(500))
    compliance_blockers_json: Mapped[str | None] = mapped_column(Text)
    inspection_photos_count: Mapped[int] = mapped_column(default=0)
    inspection_metadata_json: Mapped[str | None] = mapped_column(Text)
    gravame_certificate_uri: Mapped[str | None] = mapped_column(String(500))
    funding_target_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    funding_captured_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    activation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_manually: Mapped[bool] = mapped_column(Boolean, default=False)
    months_in_force: Mapped[int] = mapped_column(default=0)
    anticipation_unlock_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tokenization_json: Mapped[str | None] = mapped_column(Text)


class LeaseEquityStatusLog(Base):
    __tablename__ = "lease_equity_status_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    pauta_id: Mapped[str] = mapped_column(ForeignKey("lease_equity_pautas.id"), index=True)
    from_status: Mapped[str] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class QuitConOperacao(TimestampMixin, Base):
    __tablename__ = "operacoes_quitcon"
    __table_args__ = (UniqueConstraint("organization_id", "proposal_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    quota_id: Mapped[str | None] = mapped_column(ForeignKey("quotas.id"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    operacao_code: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(50), default="AGUARDANDO_TAPAF", index=True)
    property_type: Mapped[str] = mapped_column(String(40))
    appraisal_value: Mapped[float] = mapped_column(Numeric(15, 2))
    outstanding_balance: Mapped[float] = mapped_column(Numeric(15, 2))
    registry_number: Mapped[str] = mapped_column(String(80))
    registry_office: Mapped[str] = mapped_column(String(180))
    tapaf_payment_reference: Mapped[str | None] = mapped_column(String(120))
    tapaf_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    compliance_dossier_uri: Mapped[str | None] = mapped_column(String(500))
    compliance_blockers_json: Mapped[str | None] = mapped_column(Text)
    inspection_photos_count: Mapped[int] = mapped_column(default=0)
    inspection_metadata_json: Mapped[str | None] = mapped_column(Text)
    inspection_cost_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    gravame_certificate_uri: Mapped[str | None] = mapped_column(String(500))
    administrator_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_estimated_completion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    success_fee_escrow_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    funding_target_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    funding_captured_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    activation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_manually: Mapped[bool] = mapped_column(Boolean, default=False)
    months_in_force: Mapped[int] = mapped_column(default=0)
    anticipation_unlock_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(String(80))
    penalty_amount: Mapped[float | None] = mapped_column(Numeric(15, 2))
    penalty_detail_json: Mapped[str | None] = mapped_column(Text)
    tokenization_json: Mapped[str | None] = mapped_column(Text)
    meses_restantes: Mapped[int] = mapped_column(default=48)
    quitacao_vp_amount: Mapped[float | None] = mapped_column(Numeric(15, 2))
    operational_service_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    operational_service_fee_amount: Mapped[float | None] = mapped_column(Numeric(15, 2))
    operational_service_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    success_fee_escrow_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    success_fee_escrow_reference: Mapped[str | None] = mapped_column(String(120))
    success_fee_refunded: Mapped[bool] = mapped_column(Boolean, default=False)
    cedente_payment_amount: Mapped[float | None] = mapped_column(Numeric(15, 2))
    cedente_payment_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cedente_payment_escrow_reference: Mapped[str | None] = mapped_column(String(120))
    product_snapshot_json: Mapped[str | None] = mapped_column(Text)


class QuitConStatusLog(Base):
    __tablename__ = "quitcon_status_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    operacao_id: Mapped[str] = mapped_column(ForeignKey("operacoes_quitcon.id"), index=True)
    from_status: Mapped[str] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class CollateralNativeInspection(TimestampMixin, Base):
    __tablename__ = "collateral_native_inspections"
    __table_args__ = (UniqueConstraint("organization_id", "proposal_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    product: Mapped[str] = mapped_column(String(40), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    contract_id: Mapped[str | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    lease_equity_pauta_id: Mapped[str | None] = mapped_column(ForeignKey("lease_equity_pautas.id"), index=True)
    quitcon_operacao_id: Mapped[str | None] = mapped_column(ForeignKey("operacoes_quitcon.id"), index=True)
    photos_count: Mapped[int] = mapped_column(default=0)
    metadata_json: Mapped[str] = mapped_column(Text, default="[]")
    vault_s3_uri: Mapped[str] = mapped_column(String(500))
    auction_evidence_ready: Mapped[bool] = mapped_column(Boolean, default=True)


class PaymentReceipt(TimestampMixin, Base):
    __tablename__ = "payment_receipts"
    __table_args__ = (UniqueConstraint("invoice_id", "payment_event_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), index=True)
    payment_event_id: Mapped[str | None] = mapped_column(ForeignKey("payment_events.id"))
    partner_id: Mapped[str] = mapped_column(String(80))
    reference_month: Mapped[int] = mapped_column()
    filename: Mapped[str] = mapped_column(String(120))
    total_paid: Mapped[float] = mapped_column(Numeric(15, 2))
    fruicao_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    amortizacao_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    tax_withheld: Mapped[float] = mapped_column(Numeric(15, 2))
    authenticity_hash: Mapped[str] = mapped_column(String(64), index=True)
    customer_route: Mapped[str] = mapped_column(String(500))
    vault_s3_uri: Mapped[str] = mapped_column(String(500))
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    payload_json: Mapped[str] = mapped_column(Text)
    email_status: Mapped[str] = mapped_column(String(30), default="SENT_D+0")
    push_status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReconciliationBatch(TimestampMixin, Base):
    __tablename__ = "reconciliation_batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    source: Mapped[str] = mapped_column(String(40), default="CSV")
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="PROCESSING", index=True)
    total_records: Mapped[int] = mapped_column(default=0)
    matched_records: Mapped[int] = mapped_column(default=0)
    divergent_records: Mapped[int] = mapped_column(default=0)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class ReconciliationItem(TimestampMixin, Base):
    __tablename__ = "reconciliation_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_batches.id"), index=True)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id"), index=True)
    external_reference: Mapped[str] = mapped_column(String(120), index=True)
    external_event_id: Mapped[str] = mapped_column(String(120))
    expected_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    received_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    payment_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    reason: Mapped[str | None] = mapped_column(String(255))
    resolved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(String(500))


class DelinquencyCase(TimestampMixin, Base):
    __tablename__ = "delinquency_cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), unique=True, index=True)
    days_overdue: Mapped[int]
    penalty_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    late_interest_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", index=True)
    caducity_eligible: Mapped[bool] = mapped_column(Boolean, default=False)


class NinaDistressCase(TimestampMixin, Base):
    __tablename__ = "nina_distress_cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    delinquency_case_id: Mapped[str] = mapped_column(ForeignKey("delinquency_cases.id"), unique=True, index=True)
    operation_id: Mapped[str | None] = mapped_column(ForeignKey("operations.id"), index=True)
    stage: Mapped[str] = mapped_column(String(40), default="MONITORING", index=True)
    days_overdue: Mapped[int] = mapped_column(default=0, index=True)
    fiscal_check_status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    cash_hold_status: Mapped[str] = mapped_column(String(30), default="NOT_REQUESTED", index=True)
    legal_notice_status: Mapped[str] = mapped_column(String(30), default="NOT_REQUESTED", index=True)
    caducity_status: Mapped[str] = mapped_column(String(30), default="NOT_ELIGIBLE", index=True)
    auction_status: Mapped[str] = mapped_column(String(30), default="NOT_ELIGIBLE", index=True)
    appraisal_value_avm: Mapped[float | None] = mapped_column(Numeric(15, 2))
    opening_price_percent: Mapped[float] = mapped_column(Numeric(8, 4), default=80)
    floor_price_percent: Mapped[float] = mapped_column(Numeric(8, 4), default=50)
    daily_reduction_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=500)
    current_auction_price: Mapped[float | None] = mapped_column(Numeric(15, 2))
    voluntary_vacate_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    photo_storage_reference: Mapped[str | None] = mapped_column(String(500))
    matched_quota_id: Mapped[str | None] = mapped_column(ForeignKey("quotas.id"), index=True)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class NinaDistressEvent(Base):
    __tablename__ = "nina_distress_events"
    __table_args__ = (UniqueConstraint("case_id", "event_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("nina_distress_cases.id"), index=True)
    event_key: Mapped[str] = mapped_column(String(120), index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    evidence_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class NinaCriticalApproval(Base):
    __tablename__ = "nina_critical_approvals"
    __table_args__ = (UniqueConstraint("case_id", "gate", "approver_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("nina_distress_cases.id"), index=True)
    gate: Mapped[str] = mapped_column(String(40), index=True)
    decision: Mapped[str] = mapped_column(String(20), index=True)
    notes: Mapped[str] = mapped_column(String(1000))
    approver_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class NinaLegalDocument(TimestampMixin, Base):
    __tablename__ = "nina_legal_documents"
    __table_args__ = (UniqueConstraint("case_id", "document_type", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("nina_distress_cases.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(50), index=True)
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT_LEGAL_REVIEW", index=True)
    content_json: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class CollectionAction(TimestampMixin, Base):
    __tablename__ = "collection_actions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(40))
    channel: Mapped[str] = mapped_column(String(30), default="IN_APP")
    status: Mapped[str] = mapped_column(String(30), default="SCHEDULED", index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")


class RecoveredAsset(TimestampMixin, Base):
    __tablename__ = "recovered_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    delinquency_case_id: Mapped[str | None] = mapped_column(ForeignKey("delinquency_cases.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    asset_type: Mapped[str] = mapped_column(String(40))
    public_description: Mapped[str] = mapped_column(Text)
    gated_details_json: Mapped[str] = mapped_column(Text, default="{}")
    appraisal_value: Mapped[float] = mapped_column(Numeric(15, 2))
    debt_balance: Mapped[float] = mapped_column(Numeric(15, 2))
    recovery_costs: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    custody_reference: Mapped[str] = mapped_column(String(120), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)


class AuctionLot(TimestampMixin, Base):
    __tablename__ = "auction_lots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("recovered_assets.id"), unique=True, index=True)
    lot_number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    opening_price: Mapped[float] = mapped_column(Numeric(15, 2))
    reserve_price: Mapped[float] = mapped_column(Numeric(15, 2))
    min_increment: Mapped[float] = mapped_column(Numeric(15, 2))
    platform_fee_percent: Mapped[float] = mapped_column(Numeric(8, 4), default=5)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    extension_minutes: Mapped[int] = mapped_column(default=5)
    status: Mapped[str] = mapped_column(String(30), default="SCHEDULED", index=True)
    winning_bid_id: Mapped[str | None] = mapped_column(String(36))


class AuctionQualification(TimestampMixin, Base):
    __tablename__ = "auction_qualifications"
    __table_args__ = (UniqueConstraint("lot_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    lot_id: Mapped[str] = mapped_column(ForeignKey("auction_lots.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="APPROVED", index=True)
    terms_version: Mapped[str] = mapped_column(String(30), default="auction-terms-v1")
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class AuctionBid(Base):
    __tablename__ = "auction_bids"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    lot_id: Mapped[str] = mapped_column(ForeignKey("auction_lots.id"), index=True)
    bidder_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    status: Mapped[str] = mapped_column(String(30), default="VALID", index=True)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class AuctionSettlement(TimestampMixin, Base):
    __tablename__ = "auction_settlements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    lot_id: Mapped[str] = mapped_column(ForeignKey("auction_lots.id"), unique=True, index=True)
    winning_bid_id: Mapped[str] = mapped_column(ForeignKey("auction_bids.id"), unique=True)
    gross_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    recovery_costs: Mapped[float] = mapped_column(Numeric(15, 2))
    debt_paid: Mapped[float] = mapped_column(Numeric(15, 2))
    platform_fee: Mapped[float] = mapped_column(Numeric(15, 2))
    owner_surplus: Mapped[float] = mapped_column(Numeric(15, 2))
    status: Mapped[str] = mapped_column(String(30), default="SIMULATED", index=True)
    settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class TaxDocument(TimestampMixin, Base):
    __tablename__ = "tax_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    reference_month: Mapped[str] = mapped_column(String(7), index=True)
    document_number: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), default="MOCK_NFSE")
    gross_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    tax_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="VALIDATED", index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class TaxClosing(TimestampMixin, Base):
    __tablename__ = "tax_closings"
    __table_args__ = (UniqueConstraint("organization_id", "reference_month"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    reference_month: Mapped[str] = mapped_column(String(7), index=True)
    gross_commissions: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    documented_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    eligible_payout: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    exception_count: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(30), default="PROCESSING", index=True)
    closed_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaxException(TimestampMixin, Base):
    __tablename__ = "tax_exceptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    closing_id: Mapped[str] = mapped_column(ForeignKey("tax_closings.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    reason: Mapped[str] = mapped_column(String(120))
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    status: Mapped[str] = mapped_column(String(30), default="OPEN", index=True)
    resolved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(String(500))


class CommunicationTemplate(TimestampMixin, Base):
    __tablename__ = "communication_templates"
    __table_args__ = (UniqueConstraint("organization_id", "key", "channel", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    key: Mapped[str] = mapped_column(String(80), index=True)
    channel: Mapped[str] = mapped_column(String(30), index=True)
    version: Mapped[int]
    subject: Mapped[str | None] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(String(40), default="TRANSACTIONAL")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CommunicationConsent(TimestampMixin, Base):
    __tablename__ = "communication_consents"
    __table_args__ = (UniqueConstraint("organization_id", "subject_type", "subject_id", "channel"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    subject_type: Mapped[str] = mapped_column(String(30))
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    channel: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20), default="OPT_IN", index=True)
    source: Mapped[str] = mapped_column(String(60), default="PLATFORM")
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class CommunicationDelivery(TimestampMixin, Base):
    __tablename__ = "communication_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("communication_templates.id"), index=True)
    subject_type: Mapped[str] = mapped_column(String(30))
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    destination_masked: Mapped[str] = mapped_column(String(180))
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), default="MOCK")
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    rendered_body: Mapped[str] = mapped_column(Text)
    provider_message_id: Mapped[str | None] = mapped_column(String(120))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UnderwritingPolicy(TimestampMixin, Base):
    __tablename__ = "underwriting_policies"
    __table_args__ = (UniqueConstraint("organization_id", "product", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    product: Mapped[str] = mapped_column(String(50), index=True)
    version: Mapped[int]
    minimum_score: Mapped[int] = mapped_column(default=650)
    maximum_ltv_percent: Mapped[float] = mapped_column(Numeric(8, 4), default=40)
    maximum_commitment_percent: Mapped[float] = mapped_column(Numeric(8, 4), default=35)
    manual_review_score: Mapped[int] = mapped_column(default=720)
    rules_json: Mapped[str] = mapped_column(Text, default="{}")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class UnderwritingAssessment(TimestampMixin, Base):
    __tablename__ = "underwriting_assessments"
    __table_args__ = (UniqueConstraint("proposal_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("underwriting_policies.id"), index=True)
    version: Mapped[int]
    score: Mapped[int] = mapped_column(index=True)
    risk_band: Mapped[str] = mapped_column(String(20), index=True)
    recommendation: Mapped[str] = mapped_column(String(30), index=True)
    inputs_json: Mapped[str] = mapped_column(Text)
    explanation_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="PENDING_DECISION", index=True)
    assessed_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class UnderwritingDecision(TimestampMixin, Base):
    __tablename__ = "underwriting_decisions"
    __table_args__ = (UniqueConstraint("assessment_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("underwriting_assessments.id"), unique=True, index=True)
    decision: Mapped[str] = mapped_column(String(30), index=True)
    reason: Mapped[str] = mapped_column(String(500))
    decided_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class OperationalJob(TimestampMixin, Base):
    __tablename__ = "operational_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    job_type: Mapped[str] = mapped_column(String(80), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    result_json: Mapped[str | None] = mapped_column(Text)


class TenantQuota(TimestampMixin, Base):
    __tablename__ = "tenant_quotas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), unique=True, index=True)
    api_requests_per_minute: Mapped[int] = mapped_column(default=120)
    jobs_per_day: Mapped[int] = mapped_column(default=1000)
    communications_per_day: Mapped[int] = mapped_column(default=10000)
    storage_mb: Mapped[int] = mapped_column(default=1024)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str | None] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    subject: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class ProviderIntegration(TimestampMixin, Base):
    __tablename__ = "provider_integrations"
    __table_args__ = (UniqueConstraint("organization_id", "provider", "environment"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    provider: Mapped[str] = mapped_column(String(60), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    environment: Mapped[str] = mapped_column(String(20), default="SANDBOX", index=True)
    base_url: Mapped[str | None] = mapped_column(String(500))
    credential_ciphertext: Mapped[str | None] = mapped_column(Text)
    allowed_hosts_json: Mapped[str] = mapped_column(Text, default="[]")
    credential_version: Mapped[int] = mapped_column(default=1)
    credential_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_latency_ms: Mapped[int] = mapped_column(default=2000)
    total_checks: Mapped[int] = mapped_column(default=0)
    successful_checks: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    health_status: Mapped[str] = mapped_column(String(30), default="UNKNOWN", index=True)
    latency_ms: Mapped[int | None]
    last_health_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(default=0)
    circuit_status: Mapped[str] = mapped_column(String(20), default="CLOSED", index=True)
    circuit_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderIncident(TimestampMixin, Base):
    __tablename__ = "provider_incidents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("provider_integrations.id"), index=True)
    incident_type: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    title: Mapped[str] = mapped_column(String(180))
    details: Mapped[str] = mapped_column(String(1000))
    acknowledged_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderRequestLog(Base):
    __tablename__ = "provider_request_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("provider_integrations.id"), index=True)
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(500))
    response_code: Mapped[int | None]
    latency_ms: Mapped[int]
    success: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class SecretReference(TimestampMixin, Base):
    __tablename__ = "secret_references"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    backend: Mapped[str] = mapped_column(String(30), default="LOCAL_ENCRYPTED")
    encrypted_value: Mapped[str | None] = mapped_column(Text)
    external_reference: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_rotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class IntegrationMTLSConfig(TimestampMixin, Base):
    __tablename__ = "integration_mtls_configs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("provider_integrations.id"), unique=True, index=True)
    certificate_secret_id: Mapped[str] = mapped_column(ForeignKey("secret_references.id"))
    private_key_secret_id: Mapped[str] = mapped_column(ForeignKey("secret_references.id"))
    ca_secret_id: Mapped[str | None] = mapped_column(ForeignKey("secret_references.id"))
    verify_peer: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class ProviderOnboardingProfile(TimestampMixin, Base):
    __tablename__ = "provider_onboarding_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("provider_integrations.id"), unique=True, index=True)
    api_version: Mapped[str] = mapped_column(String(40), default="v1")
    authentication_type: Mapped[str] = mapped_column(String(40), default="BEARER")
    health_path: Mapped[str] = mapped_column(String(200), default="/health")
    reconciliation_mode: Mapped[str] = mapped_column(String(30), default="CSV_AND_WEBHOOK")
    checklist_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    homologated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderReconciliationRun(TimestampMixin, Base):
    __tablename__ = "provider_reconciliation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("provider_integrations.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(30), index=True)
    source_reference: Mapped[str] = mapped_column(String(180))
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    total_items: Mapped[int] = mapped_column(default=0)
    matched_items: Mapped[int] = mapped_column(default=0)
    divergent_items: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(30), default="PROCESSING", index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderReconciliationItem(Base):
    __tablename__ = "provider_reconciliation_items"
    __table_args__ = (UniqueConstraint("run_id", "external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("provider_reconciliation_runs.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(120), index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    amount: Mapped[float] = mapped_column(Numeric(15,2), default=0)
    provider_status: Mapped[str] = mapped_column(String(50))
    match_status: Mapped[str] = mapped_column(String(30), index=True)
    reason: Mapped[str | None] = mapped_column(String(500))


class HomologationEvidence(Base):
    __tablename__ = "homologation_evidences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("provider_integrations.id"), index=True)
    control_key: Mapped[str] = mapped_column(String(100), index=True)
    result: Mapped[str] = mapped_column(String(20), index=True)
    evidence_json: Mapped[str] = mapped_column(Text)
    evidence_hash: Mapped[str] = mapped_column(String(64), unique=True)
    executed_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class AdapterExecution(Base):
    __tablename__ = "adapter_executions"
    __table_args__ = (UniqueConstraint("integration_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("provider_integrations.id"), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    operation: Mapped[str] = mapped_column(String(80), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    input_hash: Mapped[str] = mapped_column(String(64))
    output_json: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    adapter_name: Mapped[str] = mapped_column(String(100))
    adapter_version: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class AdapterCertificationRun(Base):
    __tablename__ = "adapter_certification_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("provider_integrations.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    passed_checks: Mapped[int] = mapped_column(default=0)
    total_checks: Mapped[int] = mapped_column(default=0)
    report_json: Mapped[str] = mapped_column(Text)
    report_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    executed_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class ProviderGoLiveApproval(Base):
    __tablename__ = "provider_go_live_approvals"
    __table_args__ = (UniqueConstraint("integration_id", "area"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("provider_integrations.id"), index=True)
    area: Mapped[str] = mapped_column(String(30), index=True)
    decision: Mapped[str] = mapped_column(String(20), index=True)
    notes: Mapped[str] = mapped_column(String(1000))
    decided_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), index=True)


class ProviderGoLiveDecision(Base):
    __tablename__ = "provider_go_live_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("provider_integrations.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    blockers_json: Mapped[str] = mapped_column(Text)
    snapshot_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    decided_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class WebhookEndpoint(TimestampMixin, Base):
    __tablename__ = "webhook_endpoints"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("provider_integrations.id"), index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    target_url: Mapped[str] = mapped_column(String(500))
    secret_ciphertext: Mapped[str] = mapped_column(Text)
    subscribed_events_json: Mapped[str] = mapped_column(Text, default="[]")
    max_attempts: Mapped[int] = mapped_column(default=5)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class WebhookDelivery(TimestampMixin, Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (UniqueConstraint("endpoint_id", "event_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    endpoint_id: Mapped[str] = mapped_column(ForeignKey("webhook_endpoints.id"), index=True)
    event_id: Mapped[str] = mapped_column(String(120), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    signature: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=5)
    response_code: Mapped[int | None]
    response_body: Mapped[str | None] = mapped_column(String(500))
    last_error: Mapped[str | None] = mapped_column(String(500))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
