import json
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import create_token, verify_password
from app.core.config import settings
from app.db import get_db
from app.dependencies import get_current_user, require_scope
from app.models import (
    Administrator, AuctionBid, AuctionLot, AuctionQualification, AuctionSettlement,
    AuthSession, Branch, CalculationMemory, CommunicationConsent, CommunicationDelivery,
    CommunicationTemplate, Contract, Document, AcceptanceTemplate, TransactionAcceptance, QuotaTransferVerification,
    SellerEvidenceAudit, StructuredPropertyCase, StructuredPropertyEvent,
    FlashCreditPolicy, SaaSPlan, SaaSSubscription, SaaSTermsTemplate, ValidStamp,
    EarlySettlementQuote, FinOpsDomainEvent, NinaRoutingPolicy, NinaRoutingAssessment,
    CollectionAction, CommissionEntry, CommissionRule, DelinquencyCase,
    EscrowAccount, FundingOpportunity, Invoice, RecoveredAsset,
    InvestmentPosition, InvestmentReservation, KycCase, Lead, LedgerEntry,
    LedgerTransaction, NetworkNode, PaymentReceipt, PayoutApproval, PayoutRequest, PreAnalysisPauta, Proposal, LeaseEquityPauta, QuitConOperacao, CollateralNativeInspection,
    Quota, QuotaReservation, SignatureEnvelope, User, UserInvitation,
    ReconciliationBatch, ReconciliationItem, TaxClosing, TaxDocument, TaxException,
    UnderwritingAssessment, UnderwritingDecision, UnderwritingPolicy, OperationalJob, SecurityEvent, TenantQuota,
    NinaCriticalApproval, NinaDistressCase, NinaDistressEvent, NinaLegalDocument,
    AdapterCertificationRun, AdapterExecution, HomologationEvidence, IntegrationMTLSConfig, ProviderGoLiveApproval, ProviderGoLiveDecision, ProviderIncident, ProviderIntegration,
    ProviderOnboardingProfile, ProviderReconciliationItem, ProviderReconciliationRun,
    ProviderRequestLog, SecretReference, WebhookDelivery, WebhookEndpoint,
)
from app.schemas import (
    AccountBalanceView, AuctionBidCreate, AuctionBidView, AuctionLotCreate, AuctionLotView, BISummaryView,
    AuctionQualificationRequest, AuctionQualificationView, AuctionSettlementView,
    BranchCreate, BranchView, CalculationRequest, CommunicationConsentRequest,
    CommunicationConsentView, CommunicationDeliveryView, CommunicationSendRequest,
    CommunicationTemplateCreate, CommunicationTemplateView,
    CalculationView, ContractAccept, ContractCreate, ContractView, DashboardSummary,
    AcceptanceTemplateCreate, AcceptanceTemplateView, CheckoutAcceptanceCreate, TransactionAcceptanceView,
    TransferWindowCreate, TransferReleaseCreate, TransferDisputeCreate, QuotaTransferVerificationView,
    SellerEvidenceAuditCreate, SellerEvidenceReview, SellerEvidenceAuditView,
    StructuredPropertyCreate, PropertyDocumentAttach, StructuredPropertyView, StructuredPropertyEventView,
    FlashCreditPolicyCreate, FlashCreditPolicyView, FlashCreditPartiesCreate, FlashCreditRouteView,
    NinaRoutingPolicyCreate, NinaRoutingPolicyView, NinaRoutingAssessmentCreate, NinaRoutingAssessmentView,
    FlashSimulatorRequest, SettlementCurveRequest, ContractSettlementRequest, EarlySettlementQuoteView,
    FlashCapitalSimulationParamsView, FlashCapitalSimulationParamsUpdate,
    FinOpsEventCreate, FinOpsEventView, InfraProviderCatalogItem, SdcBulletPreviewRequest,
    TapafSettlementView, TapafSplitPolicyView,
    ValidStampCreate, ValidStampView, SaaSTermsCreate, SaaSTermsView, SaaSPlanCreate, SaaSPlanView,
    SaaSSubscribeCreate, SaaSSubscriptionView,
    BillingGenerateRequest, CollectionActionView, CommissionAllocate, CommissionEntryView, CommissionRuleCreate,
    CommissionRuleView, DocumentView, EscrowAsaasStatusView, EscrowCreate, EscrowSubaccountPreviewView, EscrowView, EscrowWebhook,
    FiscalEvidenceView, SefazRobotStatusView,
    DelinquencyView, FiscalReleaseRequest, FundingOpportunityCreate, FundingOpportunityView, InvitationView,
    NinaApprovalRequest, NinaCriticalApprovalView, NinaDistressCaseCreate, NinaDistressCaseView,
    NinaDistressEventView, NinaDocumentCreate, NinaGateApplyRequest, NinaLegalDocumentView, NinaTimelineEvaluateRequest,
    InviteAccept, InviteCreate, KycCreate, KycDecision, KycView, LeadCreate,
    InvestmentPositionView, InvestmentReservationView, InvestmentReserveRequest, InvoicePaymentWebhook, InvoiceProcessorRequest, InvoiceView,
    PaymentReceiptView, PreAnalysisEngineRequest, PreAnalysisPautaView, PreAnalysisProposalRequest,
    PreAnalysisTapafCheckoutAcceptRequest, PreAnalysisTapafPaymentWebhook, PreAnalysisValidateDocumentsRequest,
    LeaseEquityPautaCreate, LeaseEquityPautaView, LeaseEquityTapafWebhook, LeaseEquityInspectionRequest,
    LeaseEquityComplianceReview, LeaseEquityFundingCapture, LeaseEquityActivateRequest,
    LeaseEquityAnticipationRequest, LeaseEquityMonthsRequest, LeaseEquityLtvSimulateRequest,
    LeaseEquityTokenizationRequest,
    QuitConOperacaoCreate, QuitConOperacaoView, QuitConTapafWebhook, QuitConInspectionRequest,
    QuitConComplianceReview, QuitConFundingCapture, QuitConActivateRequest,
    QuitConPublicSimulateRequest, QuitConSuccessFeeWebhook, QuitConCedentePaymentWebhook,
    QuitConOperationalServiceWebhook,
    PublicFlashPoolRequest, PublicLeadCaptureRequest, PublicQuotaCatalogItem, PublicSdcSimulateRequest,
    QuitConAdminRejectionRequest,
    QuitConSimulateRequest,
    SdcQuitConIntegrationView, SdcQuitConProjectionRequest,
    SdcStartQuitConRequest, SdcStartQuitConResponse,
    QuitConTokenizationRequest, QuitConCancelInadimplenciaRequest,
    ContractNativeInspectionRequest, CollateralNativeInspectionView,
    LeadUpdate, LeadView, LedgerPostRequest, LedgerTransactionView, LoginRequest,
    FlashCreditCalculationRequest, MfaSetupView, MfaVerify, ModuleView, PasswordResetConfirm, PasswordResetRequest,
    NetworkNodeCreate, NetworkNodeView, PayoutApprove, PayoutCreate, PayoutView, ProposalCreate, ProposalUpdate,
    ReconciliationBatchView, ReconciliationItemView, ReconciliationResolveRequest,
    MarketplaceEsteira1Request, MarketplaceEsteira1Response, MarketplaceEsteira2Request, MarketplaceEsteira2Response,
    ProposalView, QuotaCreate, QuotaUpdate, QuotaView, NinaQuotaScanView, RecoveredAssetCreate, RecoveredAssetView, RefreshRequest,
    ReservationCreate, ReservationView, SdcCalculationRequest, SessionView, SignatureComplete,
    SignatureCreate, SignatureView, SignatureZapSignStatusView, StepUpRequest, TaxClosingRequest, TaxClosingView,
    TaxDocumentCreate, TaxDocumentView, TaxExceptionResolve, TaxExceptionView,
    TokenPair, UnderwritingAssessmentCreate, UnderwritingAssessmentView, OperationalJobCreate, OperationalJobView, JobProcessRequest, TenantQuotaUpdate, TenantQuotaView, SecurityEventView,
    UnderwritingDecisionCreate, UnderwritingDecisionView, UnderwritingPolicyCreate,
    UnderwritingPolicyView, UserUpdate, UserView, QuotaRankingView,
    ProviderIntegrationCreate, ProviderIntegrationView, IntegrationProbeRequest,
    WebhookEndpointCreate, WebhookEndpointView, WebhookDispatchRequest, WebhookRetryRequest,
    WebhookDeliveryView, WebhookVerifyRequest,
    CredentialRotateRequest, DeadLetterBulkRequest, IncidentActionRequest,
    ProviderIncidentView, ProviderRequest, ProviderRequestLogView,
    HomologationEvidenceView, MTLSConfigCreate, MTLSConfigView, OnboardingProfileCreate,
    OnboardingProfileView, ProviderReconciliationItemView, ReconciliationRunView, SecretCreate, SecretReferenceView,
    AdapterCatalogItem, AdapterCertificationView, AdapterExecuteRequest, AdapterExecutionView,
    GoLiveApprovalRequest, GoLiveApprovalView, GoLiveDecisionView,
)
from app.services import (
    MODULES, audit, calculate_marketplace, create_contract, dashboard_summary,
    financial_guard, post_double_entry, release_expired_reservations,
    release_reservation, reserve_quota, validate_quota_combination,
)
from app.document_service import contract_pdf, persist_upload
from app.financial_service import account_balances, approve_payout, create_mock_escrow, create_payout, process_escrow_event
from app.quota_acceptance_service import accept_checkout, approve_template, confirm_release, create_template as create_acceptance_template, dispute, open_window
from app.compliance_property_service import (
    approve_iq, approve_registration, attach_iq_document, create_property_case,
    cross_validate_seller_evidence, evaluate_expiry, property_requirement_pdf,
    release_phase1, review_seller_audit, submit_registration,
)
from app.flash_valid_lss_service import (
    approve_flash_policy, approve_terms, cancel_subscription, configure_flash_parties, evaluate_subscription,
    create_flash_policy, create_plan, create_terms, issue_stamp, subscribe,
    subscription_allocation, verify_stamp,
)
from app.identity_service import (
    accept_invitation, confirm_password_reset, create_invitation, create_kyc_case,
    create_password_reset, create_session_tokens, rotate_refresh, setup_mfa,
    token_hash, verify_mfa,
)
from app.core.security import decode_token, hash_password, verify_password
from app.dependencies import require_step_up
from app.product_service import calculate_flash_credit, calculate_sdc
from app.sdc_quitcon_service import start_quitcon_from_sdc
from app.valid_stamp_requirements import valid_stamp_requirements
from app.invoice_processor_service import process_invoice_settlement, receipt_processor_response, receipt_view
from app.pre_analysis_service import (
    accept_tapaf_checkout, confirm_tapaf_payment, generate_tapaf_checkout, pauta_view,
    run_engine_phase3, validate_documents_phase1,
)
from app.collateral_native_inspection_service import (
    inspection_view, link_inspection_to_contract, register_contract_native_inspection,
    resolve_inspection_for_contract,
)
from app.lease_equity_engine import EngineLeaseEquityLetter
from app.lease_equity_service import (
    activate_ok, complete_gravame, confirm_tapaf_payment as confirm_lease_tapaf,
    create_pauta, generate_tapaf_checkout as generate_lease_tapaf, pauta_view as lease_pauta_view,
    process_tokenization, record_funding_capture, refresh_anticipation_eligibility,
    register_inspection_photos, run_compliance_review, sign_contract, simulate_anticipation,
    submit_registry_protocol,
)
from app.quitcon_engine import EngineQuitConLetter
from app.quitcon_service import (
    activate_ok as activate_quitcon_ok, cancel_desistencia_cedente, cancel_inadimplencia_cessionario,
    complete_gravame as complete_quitcon_gravame,
    confirm_tapaf_payment as confirm_quitcon_tapaf,
    create_operacao, generate_tapaf_checkout as generate_quitcon_tapaf,
    generate_success_fee_checkout, confirm_success_fee_payment,
    generate_operational_service_checkout, confirm_operational_service_payment,
    generate_cedente_payment_checkout, confirm_cedente_payment_escrow,
    register_administrator_rejection,
    operacao_view as quitcon_operacao_view,
    process_tokenization as process_quitcon_tokenization,
    record_funding_capture as record_quitcon_funding,
    register_administrator_approval, register_inspection_photos as register_quitcon_inspection,
    run_compliance_review as run_quitcon_compliance,
    sign_contract as sign_quitcon_contract,
    submit_registry_protocol as submit_quitcon_registry,
)
from app.storage_service import get_storage
from app.vehicle_registry_service import query_vehicle_registry
from app.finops_engine import create_contract_quote, four_scenarios, ingest_event, settlement_curve, sdc_bullet_and_split
from app.infra_inventory_service import catalog, get_settlement, list_settlements, settlement_view
from app.tapaf_constants import (
    TAPAF_ESTIMATED_INFRA_MARGIN,
    TAPAF_ESTIMATED_TOTAL_API_COST,
    TAPAF_LOTE_A_API_RESERVE,
    TAPAF_LOTE_B_FRANCHISE_SPREAD,
    TAPAF_NOMINAL,
)
from app.public_site_service import (
    capture_public_lead, list_public_quotas, simulate_flash_pool_public, simulate_sdc_public,
)
from app.flash_capital_params import get_active_flash_simulation_params, save_flash_simulation_params
from app.network_service import (
    allocate_commissions, confirm_investment, create_network_node, create_rule,
    downline_summary, reserve_investment,
)
from app.billing_service import (
    apply_payment, generate_billing_schedule, import_reconciliation_csv,
    refresh_delinquency, resolve_reconciliation,
)
from app.auction_service import (
    activate_lot, create_asset, create_lot, gated_asset_details, place_bid,
    qualify, settle_lot,
)
from app.tax_communication_service import (
    close_tax_month, create_template, issue_tax_document, mock_deliver,
    queue_delivery, resolve_tax_exception, update_consent,
)
from app.nina_bi_service import assess, bi_summary, create_policy, decide, rank_quota_combinations
from app.operations_service import enqueue_job, homologation_status, operational_metrics, process_job, system_readiness
from app.security_service import check_job_quota, get_or_create_quota, rate_limiter, record_security_event
from app.integration_service import (
    attempt_delivery, configure_integration, create_endpoint, dispatch_webhook,
    execute_provider_request, probe_integration, reprocess_dead_letters, rotate_credential, verify_webhook,
)
from app.provider_onboarding_service import (
    configure_mtls, configure_profile, create_secret, generate_evidence,
    import_reconciliation_csv as import_provider_reconciliation_csv,
)
from app.provider_adapters import adapter_catalog, execute_adapter
from app.provider_certification import certify_adapter, decide_approval, evaluate_go_live
from app.nina_asset_service import apply_gate, create_distress_case, evaluate_timeline, generate_legal_document, legal_document_pdf, record_approval, reduce_sandbox_prices
from app.nina_routing_service import approve_assessment as approve_routing_assessment, approve_policy as approve_routing_policy, assess as assess_nina_route, assessment_view as nina_routing_view, create_policy as create_routing_policy, source_policy as nina_source_policy

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health():
    return {"status": "ok", "service": "letter-api"}


@router.get("/platform/capabilities")
def platform_capabilities():
    return {
        "version": "0.24.0",
        "features": {
            "finops_pre_analysis_v6": True,
            "finops_invoice_processor_v3": True,
            "finops_lease_equity_v1": True,
            "finops_quitcon_v1": True,
            "finops_events": True,
            "nina_routing": True,
            "valid_stamp": True,
            "lss": True,
            "structured_properties": True,
        },
    }


@router.post("/auth/login", response_model=TokenPair)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip=request.client.host if request.client else "unknown";allowed,retry=rate_limiter.allow(f"login:{ip}:{payload.email.lower()}",settings.login_rate_limit_per_minute)
    if not allowed:
        record_security_event(db,"AUTH_RATE_LIMITED","HIGH",ip,payload.email.lower());db.commit()
        raise HTTPException(status_code=429,detail="Muitas tentativas de login",headers={"Retry-After":str(retry)})
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash) or not user.active:
        record_security_event(db,"LOGIN_FAILED","MEDIUM",ip,payload.email.lower(),user.organization_id if user else None);db.commit()
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    if user.mfa_enabled and (not payload.otp or not verify_mfa(user,payload.otp)):
        raise HTTPException(status_code=428,detail="Código MFA obrigatório ou inválido")
    access,refresh,_=create_session_tokens(db,user,request.headers.get("user-agent"),request.client.host if request.client else None)
    db.commit();return TokenPair(access_token=access,refresh_token=refresh)


@router.post("/auth/refresh",response_model=TokenPair)
def refresh(payload:RefreshRequest,db:Session=Depends(get_db)):
    access,refresh_token=rotate_refresh(db,payload.refresh_token);db.commit();return TokenPair(access_token=access,refresh_token=refresh_token)


@router.get("/auth/me", response_model=UserView)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/auth/sessions",response_model=list[SessionView])
def sessions(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(AuthSession).where(AuthSession.user_id==user.id).order_by(AuthSession.created_at.desc())))


@router.delete("/auth/sessions/{session_id}",status_code=204)
def revoke_session(session_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    session=db.scalar(select(AuthSession).where(AuthSession.id==session_id,AuthSession.user_id==user.id))
    if not session: raise HTTPException(status_code=404,detail="Sessão não encontrada")
    session.active=False;session.revoked_at=datetime.now(UTC);db.commit()


@router.post("/auth/mfa/setup",response_model=MfaSetupView)
def mfa_setup(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    secret,uri=setup_mfa(user);db.commit();return MfaSetupView(secret=secret,provisioning_uri=uri)


@router.post("/auth/mfa/enable")
def mfa_enable(payload:MfaVerify,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not verify_mfa(user,payload.otp): raise HTTPException(status_code=422,detail="Código MFA inválido")
    user.mfa_enabled=True;db.commit();return {"enabled":True}


@router.post("/auth/mfa/disable")
def mfa_disable(payload:MfaVerify,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not verify_mfa(user,payload.otp): raise HTTPException(status_code=422,detail="Código MFA inválido")
    user.mfa_enabled=False;user.mfa_secret=None;db.commit();return {"enabled":False}


@router.post("/auth/step-up")
def step_up(payload:StepUpRequest,request:Request,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not verify_password(payload.password,user.password_hash): raise HTTPException(status_code=401,detail="Senha inválida")
    if user.mfa_enabled and (not payload.otp or not verify_mfa(user,payload.otp)): raise HTTPException(status_code=422,detail="Código MFA inválido")
    raw=request.headers.get("authorization","").removeprefix("Bearer ");claims=decode_token(raw);session=db.get(AuthSession,claims.get("sid"));session.step_up_until=datetime.now(UTC)+__import__('datetime').timedelta(minutes=10);db.commit();return {"step_up_until":session.step_up_until}


@router.post("/auth/password-reset/request")
def password_reset_request(payload:PasswordResetRequest,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==str(payload.email).lower()));raw=None
    if user: raw=create_password_reset(db,user);db.commit()
    return {"status":"accepted","development_token":raw}


@router.post("/auth/password-reset/confirm")
def password_reset_confirm(payload:PasswordResetConfirm,db:Session=Depends(get_db)):
    confirm_password_reset(db,payload.token,payload.new_password);db.commit();return {"status":"password_updated"}


@router.get("/admin/users",response_model=list[UserView])
def admin_users(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return list(db.scalars(select(User).where(User.organization_id==user.organization_id).order_by(User.created_at.desc())))


@router.patch("/admin/users/{user_id}",response_model=UserView)
def admin_update_user(user_id:str,payload:UserUpdate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    target=db.scalar(select(User).where(User.id==user_id,User.organization_id==user.organization_id))
    if not target: raise HTTPException(status_code=404,detail="Usuário não encontrado")
    for field,value in payload.model_dump(exclude_unset=True).items():setattr(target,field,value)
    audit(db,user,"user.updated","user",target.id,payload.model_dump(exclude_unset=True,mode="json"));db.commit();db.refresh(target);return target


@router.get("/admin/branches",response_model=list[BranchView])
def branches(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return list(db.scalars(select(Branch).where(Branch.organization_id==user.organization_id).order_by(Branch.name)))


@router.post("/admin/branches",response_model=BranchView,status_code=201)
def create_branch(payload:BranchCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=Branch(organization_id=user.organization_id,**payload.model_dump());db.add(item);db.flush();audit(db,user,"branch.created","branch",item.id);db.commit();db.refresh(item);return item


@router.post("/admin/invitations",response_model=InvitationView,status_code=201)
def invite(payload:InviteCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item,raw=create_invitation(db,user,str(payload.email),payload.role,payload.branch_id);db.flush();audit(db,user,"invitation.created","invitation",item.id);db.commit();db.refresh(item)
    return InvitationView.model_validate(item).model_copy(update={"token":raw})


@router.post("/auth/invitations/accept",response_model=UserView)
def accept_invite(payload:InviteAccept,db:Session=Depends(get_db)):
    user=accept_invitation(db,payload.token,payload.name,payload.document,payload.password);db.commit();db.refresh(user);return user


@router.get("/admin/invitations",response_model=list[InvitationView])
def invitations(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return list(db.scalars(select(UserInvitation).where(UserInvitation.organization_id==user.organization_id).order_by(UserInvitation.created_at.desc())))


@router.post("/kyc/cases",response_model=KycView,status_code=201)
def start_kyc(payload:KycCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    item=create_kyc_case(user,payload.subject_type,payload.subject_id);db.add(item);db.flush();audit(db,user,"kyc.started","kyc_case",item.id);db.commit();db.refresh(item);return item


@router.get("/kyc/cases",response_model=list[KycView])
def kyc_cases(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(KycCase).where(KycCase.organization_id==user.organization_id).order_by(KycCase.created_at.desc())))


@router.post("/kyc/cases/{case_id}/mock-decision",response_model=KycView)
def decide_kyc(case_id:str,payload:KycDecision,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(KycCase).where(KycCase.id==case_id,KycCase.organization_id==user.organization_id))
    if not item: raise HTTPException(status_code=404,detail="Caso KYC não encontrado")
    if payload.status not in {"APPROVED","REJECTED","REVIEW"}: raise HTTPException(status_code=422,detail="Status inválido")
    item.status=payload.status;item.risk_level=payload.risk_level;item.result_json=json.dumps(payload.model_dump());item.reviewed_by_id=user.id;item.reviewed_at=datetime.now(UTC);audit(db,user,"kyc.decided","kyc_case",item.id,payload.model_dump());db.commit();db.refresh(item);return item


@router.post("/network/nodes", response_model=NetworkNodeView, status_code=201)
def network_node_create(payload: NetworkNodeCreate, user: User = Depends(require_scope("admin:users")), db: Session = Depends(get_db)):
    target = db.scalar(select(User).where(User.id == payload.user_id, User.organization_id == user.organization_id))
    if not target: raise HTTPException(status_code=404, detail="Usuário não encontrado")
    item = create_network_node(db, user, target, payload.tree_type, payload.sponsor_user_id)
    audit(db,user,"network.node_created","network_node",item.id,payload.model_dump());db.commit();db.refresh(item);return item


@router.get("/network/nodes", response_model=list[NetworkNodeView])
def network_nodes(tree_type: str = "SALES", user: User = Depends(require_scope("admin:users")), db: Session = Depends(get_db)):
    return list(db.scalars(select(NetworkNode).where(NetworkNode.organization_id == user.organization_id, NetworkNode.tree_type == tree_type).order_by(NetworkNode.created_at)))


@router.get("/network/me/summary")
def network_my_summary(tree_type: str = "SALES", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return downline_summary(db, user, tree_type)


@router.post("/commission-rules", response_model=CommissionRuleView, status_code=201)
def commission_rule_create(payload: CommissionRuleCreate, user: User = Depends(require_scope("admin:users")), db: Session = Depends(get_db)):
    item=create_rule(db,user,payload.product,payload.commission_type,payload.pool_rate_percent,payload.base_type)
    db.flush();audit(db,user,"commission.rule_created","commission_rule",item.id,payload.model_dump(mode="json"));db.commit();db.refresh(item);return item


@router.get("/commission-rules", response_model=list[CommissionRuleView])
def commission_rules(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(CommissionRule).where(CommissionRule.organization_id==user.organization_id).order_by(CommissionRule.created_at.desc())))


@router.post("/commissions/allocate", response_model=list[CommissionEntryView], status_code=201)
def commission_allocate(payload: CommissionAllocate, user: User = Depends(require_scope("admin:users")), db: Session = Depends(get_db)):
    entries=allocate_commissions(db,user,payload.originator_id,payload.proposal_id,payload.reference,payload.product,payload.commission_type,payload.calculation_base)
    audit(db,user,"commission.allocated","commission_entry",entries[0].id if entries else None,payload.model_dump(mode="json"));db.commit()
    for item in entries: db.refresh(item)
    return entries


@router.get("/wallet/commissions", response_model=list[CommissionEntryView])
def commission_wallet(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(CommissionEntry).where(CommissionEntry.organization_id==user.organization_id,CommissionEntry.beneficiary_id==user.id).order_by(CommissionEntry.created_at.desc())))


@router.get("/wallet/commissions/sefaz/status", response_model=SefazRobotStatusView)
def commission_sefaz_status(user: User = Depends(get_current_user)):
    from app.sefaz_nf_service import sefaz_robot_status

    _ = user
    return sefaz_robot_status()


@router.post("/wallet/commissions/release-fiscal")
def commission_fiscal_release(payload: FiscalReleaseRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.sefaz_nf_service import available_commission_balance, release_commissions_after_sefaz

    evidence = release_commissions_after_sefaz(
        db,
        user,
        reference_month=payload.reference_month,
        document_content=payload.document_content,
        access_key=payload.access_key,
        gross_amount=payload.gross_amount,
    )
    audit(
        db,
        user,
        "fiscal.sefaz_validated",
        "fiscal_evidence",
        evidence.id,
        {"reference_month": payload.reference_month, "access_key": evidence.access_key, "sefaz_status": evidence.sefaz_status},
    )
    db.commit()
    available = available_commission_balance(db, user)
    return {
        "status": evidence.sefaz_status or "VALID",
        "available_balance": str(available),
        "access_key": evidence.access_key,
        "provider": evidence.provider,
    }


@router.post("/funding/opportunities", response_model=FundingOpportunityView, status_code=201)
def funding_opportunity_create(payload: FundingOpportunityCreate, user: User = Depends(require_scope("admin:users")), db: Session = Depends(get_db)):
    if payload.capital_source not in {"RETAIL","INSTITUTIONAL"}: raise HTTPException(status_code=422,detail="Fonte de capital inválida")
    if payload.proposal_id and not db.scalar(select(Proposal).where(Proposal.id==payload.proposal_id,Proposal.organization_id==user.organization_id)): raise HTTPException(status_code=404,detail="Proposta não encontrada")
    item=FundingOpportunity(organization_id=user.organization_id,**payload.model_dump());db.add(item);db.flush();audit(db,user,"funding.opportunity_created","funding_opportunity",item.id);db.commit();db.refresh(item);return item


@router.get("/funding/opportunities", response_model=list[FundingOpportunityView])
def funding_opportunities(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(FundingOpportunity).where(FundingOpportunity.organization_id==user.organization_id).order_by(FundingOpportunity.created_at.desc())))


@router.post("/funding/opportunities/{opportunity_id}/reserve", response_model=InvestmentReservationView, status_code=201)
def investment_reserve(opportunity_id: str, payload: InvestmentReserveRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    opportunity=db.scalar(select(FundingOpportunity).where(FundingOpportunity.id==opportunity_id,FundingOpportunity.organization_id==user.organization_id))
    if not opportunity: raise HTTPException(status_code=404,detail="Oportunidade não encontrada")
    item=reserve_investment(db,user,opportunity,payload.amount);audit(db,user,"investment.reserved","investment_reservation",item.id,{"amount":str(payload.amount)});db.commit();db.refresh(item);return item


@router.post("/funding/reservations/{reservation_id}/mock-confirm", response_model=InvestmentPositionView)
def investment_confirm(reservation_id: str, user: User = Depends(require_scope("admin:users")), db: Session = Depends(get_db)):
    reservation=db.scalar(select(InvestmentReservation).where(InvestmentReservation.id==reservation_id,InvestmentReservation.organization_id==user.organization_id))
    if not reservation: raise HTTPException(status_code=404,detail="Reserva não encontrada")
    position=confirm_investment(db,reservation);audit(db,user,"investment.confirmed","investment_position",position.id);db.commit();db.refresh(position);return position


@router.get("/funding/reservations", response_model=list[InvestmentReservationView])
def investment_reservations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query=select(InvestmentReservation).where(InvestmentReservation.organization_id==user.organization_id)
    if user.role.value not in {"PLATFORM_ADMIN","INTERNAL_STAFF"}: query=query.where(InvestmentReservation.investor_id==user.id)
    return list(db.scalars(query.order_by(InvestmentReservation.created_at.desc())))


@router.get("/funding/positions", response_model=list[InvestmentPositionView])
def investment_positions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query=select(InvestmentPosition).where(InvestmentPosition.organization_id==user.organization_id)
    if user.role.value not in {"PLATFORM_ADMIN","INTERNAL_STAFF"}: query=query.where(InvestmentPosition.investor_id==user.id)
    return list(db.scalars(query.order_by(InvestmentPosition.created_at.desc())))


@router.post("/contracts/{contract_id}/billing", response_model=list[InvoiceView], status_code=201)
def billing_generate(contract_id: str, payload: BillingGenerateRequest, user: User = Depends(require_scope("proposals:write")), db: Session = Depends(get_db)):
    contract=db.scalar(select(Contract).where(Contract.id==contract_id,Contract.organization_id==user.organization_id))
    if not contract: raise HTTPException(status_code=404,detail="Contrato não encontrado")
    proposal=db.get(Proposal,contract.proposal_id);calculation=db.get(CalculationMemory,contract.calculation_memory_id)
    rows=generate_billing_schedule(db,contract,proposal,calculation,payload.start_date)
    audit(db,user,"billing.schedule_generated","contract",contract.id,{"invoice_count":len(rows)});db.commit()
    for row in rows: db.refresh(row)
    return rows


@router.get("/invoices", response_model=list[InvoiceView])
def invoices(status_filter: str | None = Query(default=None,alias="status"), contract_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query=select(Invoice).where(Invoice.organization_id==user.organization_id)
    if status_filter: query=query.where(Invoice.status==status_filter)
    if contract_id: query=query.where(Invoice.contract_id==contract_id)
    return list(db.scalars(query.order_by(Invoice.due_date,Invoice.installment_number)))


@router.post("/invoices/{invoice_id}/mock-payment-webhook")
def invoice_payment_webhook(invoice_id: str, payload: InvoicePaymentWebhook, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    invoice=db.scalar(select(Invoice).where(Invoice.id==invoice_id,Invoice.organization_id==user.organization_id))
    if not invoice: raise HTTPException(status_code=404,detail="Fatura não encontrada")
    event,processed,receipt_payload=apply_payment(db,user,invoice,payload.event_id,payload.amount,payload.metadata)
    if processed:audit(db,user,"invoice.payment_processed","invoice",invoice.id,{"event_id":payload.event_id,"status":event.status})
    db.commit();db.refresh(invoice)
    response={"event_id":event.provider_event_id,"processed":processed,"match_status":event.status,"invoice_status":invoice.status,"paid_amount":str(invoice.paid_amount)}
    if receipt_payload: response["invoice_processor"]=receipt_payload
    return response


@router.post("/reconciliation/import", response_model=ReconciliationBatchView, status_code=201)
async def reconciliation_import(file: UploadFile = File(...), user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    if file.content_type not in {"text/csv","application/vnd.ms-excel","application/octet-stream"}: raise HTTPException(status_code=415,detail="Envie um arquivo CSV")
    data=await file.read(5*1024*1024+1)
    if len(data)>5*1024*1024: raise HTTPException(status_code=413,detail="CSV excede 5 MB")
    batch=import_reconciliation_csv(db,user,data);db.flush();audit(db,user,"reconciliation.imported","reconciliation_batch",batch.id,{"records":batch.total_records});db.commit();db.refresh(batch);return batch


@router.get("/reconciliation/batches", response_model=list[ReconciliationBatchView])
def reconciliation_batches(user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    return list(db.scalars(select(ReconciliationBatch).where(ReconciliationBatch.organization_id==user.organization_id).order_by(ReconciliationBatch.created_at.desc())))


@router.get("/reconciliation/items", response_model=list[ReconciliationItemView])
def reconciliation_items(status_filter: str | None = Query(default=None,alias="status"), user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    query=select(ReconciliationItem).where(ReconciliationItem.organization_id==user.organization_id)
    if status_filter:query=query.where(ReconciliationItem.status==status_filter)
    return list(db.scalars(query.order_by(ReconciliationItem.created_at.desc())))


@router.post("/reconciliation/items/{item_id}/resolve", response_model=ReconciliationItemView)
def reconciliation_resolve(item_id: str, payload: ReconciliationResolveRequest, user: User = Depends(require_step_up), _: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    item=db.scalar(select(ReconciliationItem).where(ReconciliationItem.id==item_id,ReconciliationItem.organization_id==user.organization_id))
    if not item:raise HTTPException(status_code=404,detail="Divergência não encontrada")
    resolve_reconciliation(db,user,item,payload.decision,payload.note);audit(db,user,"reconciliation.resolved","reconciliation_item",item.id,payload.model_dump());db.commit();db.refresh(item);return item


@router.post("/collections/refresh", response_model=list[DelinquencyView])
def collections_refresh(as_of: date | None = None, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    rows=refresh_delinquency(db,user,as_of or date.today());audit(db,user,"collections.refreshed","delinquency_case",None,{"cases":len(rows),"as_of":str(as_of or date.today())});db.commit()
    for row in rows:db.refresh(row)
    return rows


@router.get("/collections/cases", response_model=list[DelinquencyView])
def collection_cases(user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    return list(db.scalars(select(DelinquencyCase).where(DelinquencyCase.organization_id==user.organization_id).order_by(DelinquencyCase.days_overdue.desc())))


@router.get("/collections/actions", response_model=list[CollectionActionView])
def collection_actions(user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    return list(db.scalars(select(CollectionAction).where(CollectionAction.organization_id==user.organization_id).order_by(CollectionAction.scheduled_at.desc())))


@router.post("/collections/actions/{action_id}/mock-execute", response_model=CollectionActionView)
def collection_action_execute(action_id: str, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    action=db.scalar(select(CollectionAction).where(CollectionAction.id==action_id,CollectionAction.organization_id==user.organization_id))
    if not action:raise HTTPException(status_code=404,detail="Ação não encontrada")
    if action.status!="SCHEDULED":raise HTTPException(status_code=409,detail="Ação já executada")
    action.status="EXECUTED";action.executed_at=datetime.now(UTC);audit(db,user,"collection.action_executed","collection_action",action.id,{"channel":action.channel});db.commit();db.refresh(action);return action


def nina_event_view(item:NinaDistressEvent)->NinaDistressEventView:
    return NinaDistressEventView.model_validate(item).model_copy(update={"payload":json.loads(item.payload_json)})


def nina_document_view(item:NinaLegalDocument)->NinaLegalDocumentView:
    return NinaLegalDocumentView.model_validate(item).model_copy(update={"content":json.loads(item.content_json)})


@router.post("/nina-asset/cases",response_model=NinaDistressCaseView,status_code=201)
def nina_case_create(payload:NinaDistressCaseCreate,user:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    delinquency=db.scalar(select(DelinquencyCase).where(DelinquencyCase.id==payload.delinquency_case_id,DelinquencyCase.organization_id==user.organization_id))
    if not delinquency:raise HTTPException(status_code=404,detail="Caso de inadimplência não encontrado")
    item=create_distress_case(db,user,delinquency,payload.appraisal_value_avm,payload.photo_storage_reference,payload.matched_quota_id,payload.daily_reduction_amount);db.flush();audit(db,user,"nina_asset.case_created","nina_distress_case",item.id,{"delinquency_case_id":delinquency.id});db.commit();db.refresh(item);return item


@router.get("/nina-asset/cases",response_model=list[NinaDistressCaseView])
def nina_cases(user:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    return list(db.scalars(select(NinaDistressCase).where(NinaDistressCase.organization_id==user.organization_id).order_by(NinaDistressCase.days_overdue.desc())))


@router.post("/nina-asset/cases/{case_id}/evaluate",response_model=NinaDistressCaseView)
def nina_case_evaluate(case_id:str,payload:NinaTimelineEvaluateRequest,user:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    item=db.scalar(select(NinaDistressCase).where(NinaDistressCase.id==case_id,NinaDistressCase.organization_id==user.organization_id))
    if not item:raise HTTPException(status_code=404,detail="Caso NINA Asset não encontrado")
    evaluate_timeline(db,user,item,payload.as_of);audit(db,user,"nina_asset.timeline_evaluated","nina_distress_case",item.id,{"days_overdue":item.days_overdue,"stage":item.stage});db.commit();db.refresh(item);return item


@router.post("/nina-asset/cases/{case_id}/approvals",response_model=NinaCriticalApprovalView,status_code=201)
def nina_case_approve(case_id:str,payload:NinaApprovalRequest,user:User=Depends(require_step_up),_:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    item=db.scalar(select(NinaDistressCase).where(NinaDistressCase.id==case_id,NinaDistressCase.organization_id==user.organization_id))
    if not item:raise HTTPException(status_code=404,detail="Caso NINA Asset não encontrado")
    approval=record_approval(db,user,item,payload.gate,payload.decision,payload.notes);db.flush();audit(db,user,"nina_asset.gate_decided","nina_distress_case",item.id,{"gate":approval.gate,"decision":approval.decision});db.commit();db.refresh(approval);return approval


@router.get("/nina-asset/approvals",response_model=list[NinaCriticalApprovalView])
def nina_approvals(user:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    return list(db.scalars(select(NinaCriticalApproval).where(NinaCriticalApproval.organization_id==user.organization_id).order_by(NinaCriticalApproval.decided_at.desc())))


@router.post("/nina-asset/cases/{case_id}/apply-gate",response_model=NinaDistressCaseView)
def nina_case_apply_gate(case_id:str,payload:NinaGateApplyRequest,user:User=Depends(require_step_up),_:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    item=db.scalar(select(NinaDistressCase).where(NinaDistressCase.id==case_id,NinaDistressCase.organization_id==user.organization_id))
    if not item:raise HTTPException(status_code=404,detail="Caso NINA Asset não encontrado")
    apply_gate(db,user,item,payload.gate);audit(db,user,"nina_asset.gate_applied","nina_distress_case",item.id,{"gate":payload.gate,"sandbox_only":True});db.commit();db.refresh(item);return item


@router.post("/nina-asset/cases/{case_id}/documents",response_model=NinaLegalDocumentView,status_code=201)
def nina_document_create(case_id:str,payload:NinaDocumentCreate,user:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    item=db.scalar(select(NinaDistressCase).where(NinaDistressCase.id==case_id,NinaDistressCase.organization_id==user.organization_id))
    if not item:raise HTTPException(status_code=404,detail="Caso NINA Asset não encontrado")
    document=generate_legal_document(db,user,item,payload.document_type,payload.variables);audit(db,user,"nina_asset.document_generated","nina_legal_document",document.id,{"type":document.document_type,"status":document.status});db.commit();db.refresh(document);return nina_document_view(document)


@router.get("/nina-asset/documents",response_model=list[NinaLegalDocumentView])
def nina_documents(user:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    return [nina_document_view(x) for x in db.scalars(select(NinaLegalDocument).where(NinaLegalDocument.organization_id==user.organization_id).order_by(NinaLegalDocument.created_at.desc()))]


@router.get("/nina-asset/documents/{document_id}/pdf")
def nina_document_download(document_id:str,user:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    item=db.scalar(select(NinaLegalDocument).where(NinaLegalDocument.id==document_id,NinaLegalDocument.organization_id==user.organization_id))
    if not item:raise HTTPException(status_code=404,detail="Documento NINA Asset não encontrado")
    data=legal_document_pdf(item);return Response(content=data,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="nina-{item.document_type.lower()}-v{item.version}.pdf"'})


@router.get("/nina-asset/events",response_model=list[NinaDistressEventView])
def nina_events(case_id:str|None=None,user:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    query=select(NinaDistressEvent).where(NinaDistressEvent.organization_id==user.organization_id)
    if case_id:query=query.where(NinaDistressEvent.case_id==case_id)
    return [nina_event_view(x) for x in db.scalars(query.order_by(NinaDistressEvent.occurred_at.desc()).limit(500))]


@router.post("/nina-asset/auction/reduce-prices",response_model=list[NinaDistressCaseView])
def nina_reduce_prices(user:User=Depends(require_step_up),_:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    items=reduce_sandbox_prices(db,user);audit(db,user,"nina_asset.prices_reduced","nina_distress_case",None,{"cases":len(items),"sandbox_only":True});db.commit()
    for item in items:db.refresh(item)
    return items


@router.get("/modules", response_model=list[ModuleView])
def modules(_: User = Depends(get_current_user)):
    return [ModuleView(key=k, name=n, description=d, status=s, route=r, critical=c) for k,n,d,s,r,c in MODULES]


@router.get("/dashboard", response_model=DashboardSummary)
def dashboard(user: User = Depends(require_scope("dashboard:read")), db: Session = Depends(get_db)):
    return dashboard_summary(db, user)


@router.get("/leads", response_model=list[LeadView])
def list_leads(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Lead).where(Lead.organization_id == user.organization_id).order_by(Lead.created_at.desc())))


@router.post("/leads", response_model=LeadView, status_code=201)
def create_lead(payload: LeadCreate, user: User = Depends(require_scope("leads:write")), db: Session = Depends(get_db)):
    lead = Lead(organization_id=user.organization_id, owner_id=user.id, **payload.model_dump())
    db.add(lead); db.flush(); audit(db, user, "lead.created", "lead", lead.id); db.commit(); db.refresh(lead)
    return lead


@router.patch("/leads/{lead_id}", response_model=LeadView)
def update_lead(lead_id: str, payload: LeadUpdate, user: User = Depends(require_scope("leads:write")), db: Session = Depends(get_db)):
    lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.organization_id == user.organization_id))
    if not lead: raise HTTPException(status_code=404, detail="Lead não encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items(): setattr(lead, field, value)
    audit(db, user, "lead.updated", "lead", lead.id, payload.model_dump(exclude_unset=True)); db.commit(); db.refresh(lead)
    return lead


@router.delete("/leads/{lead_id}", status_code=204)
def delete_lead(lead_id: str, user: User = Depends(require_scope("leads:write")), db: Session = Depends(get_db)):
    lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.organization_id == user.organization_id))
    if not lead: raise HTTPException(status_code=404, detail="Lead não encontrado")
    if db.scalar(select(Proposal).where(Proposal.lead_id == lead.id)):
        raise HTTPException(status_code=409, detail="Lead possui propostas e não pode ser excluído")
    audit(db, user, "lead.deleted", "lead", lead.id); db.delete(lead); db.commit()


@router.get("/administrators")
def list_administrators(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{"id": a.id, "name": a.name, "document": a.document, "authorization_status": a.authorization_status} for a in db.scalars(select(Administrator))]


@router.get("/quotas", response_model=list[QuotaView])
def list_quotas(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Quota).where(Quota.organization_id == user.organization_id).order_by(Quota.created_at.desc())))


@router.post("/quotas", response_model=QuotaView, status_code=201)
def create_quota(payload: QuotaCreate, user: User = Depends(require_scope("inventory:write")), db: Session = Depends(get_db)):
    if payload.category not in {"VEHICLE", "REAL_ESTATE"}:
        raise HTTPException(status_code=422, detail="Categoria deve ser VEHICLE ou REAL_ESTATE")
    if not db.get(Administrator, payload.administrator_id):
        raise HTTPException(status_code=404, detail="Administradora não encontrada")
    quota = Quota(organization_id=user.organization_id, seller_id=user.id, **payload.model_dump())
    db.add(quota); db.flush(); audit(db, user, "quota.created", "quota", quota.id); db.commit(); db.refresh(quota)
    return quota


@router.patch("/quotas/{quota_id}", response_model=QuotaView)
def update_quota(quota_id: str, payload: QuotaUpdate, user: User = Depends(require_scope("inventory:write")), db: Session = Depends(get_db)):
    quota = db.scalar(select(Quota).where(Quota.id == quota_id, Quota.organization_id == user.organization_id))
    if not quota: raise HTTPException(status_code=404, detail="Cota não encontrada")
    if quota.status in {"RESERVED", "SOLD"} and payload.status not in {None, quota.status}:
        raise HTTPException(status_code=409, detail="Status protegido por workflow de reserva/venda")
    for field, value in payload.model_dump(exclude_unset=True).items(): setattr(quota, field, value)
    audit(db, user, "quota.updated", "quota", quota.id, payload.model_dump(exclude_unset=True, mode="json")); db.commit(); db.refresh(quota)
    return quota


@router.post("/marketplace/esteira-1/assess", response_model=MarketplaceEsteira1Response)
def marketplace_esteira1(payload: MarketplaceEsteira1Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.marketplace_service import esteira1_partner_select

    result = esteira1_partner_select(
        db,
        user,
        quota_id=payload.quota_id,
        monthly_income=payload.monthly_income,
        monthly_commitment=payload.monthly_commitment,
        asset_value=payload.asset_value,
        asset_year=payload.asset_year,
    )
    audit(db, user, "marketplace.esteira1", "quota", payload.quota_id, {"eligible": result["eligible"]})
    db.commit()
    return result


@router.post("/marketplace/esteira-2/match", response_model=MarketplaceEsteira2Response)
def marketplace_esteira2(payload: MarketplaceEsteira2Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.marketplace_service import esteira2_nina_curated_match

    result = esteira2_nina_curated_match(
        db,
        user,
        target_amount=payload.target_amount,
        category=payload.category,
        asset_year=payload.asset_year,
        monthly_income=payload.monthly_income,
        monthly_commitment=payload.monthly_commitment,
        asset_value=payload.asset_value,
    )
    audit(db, user, "marketplace.esteira2", "marketplace", "match", {"matches": len(result["matches"])})
    db.commit()
    return result


@router.post("/quotas/{quota_id}/nina-scan", response_model=NinaQuotaScanView)
def nina_scan_quota(quota_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.quota_inventory_service import run_nina_quota_scan

    quota = db.scalar(select(Quota).where(Quota.id == quota_id, Quota.organization_id == user.organization_id))
    if not quota:
        raise HTTPException(status_code=404, detail="Cota não encontrada")
    try:
        result = run_nina_quota_scan(db, user, quota)
    except HTTPException:
        db.commit()
        raise
    audit(db, user, "quota.nina_scan", "quota", quota.id, {"status": quota.nina_scan_status})
    db.commit()
    db.refresh(quota)
    return {
        "quota_id": quota.id,
        "status": result["status"],
        "scanned_at": quota.nina_scanned_at,
        "message": result["message"],
    }


@router.post("/reservations", response_model=ReservationView, status_code=201)
def create_reservation(payload: ReservationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    quota = db.scalar(select(Quota).where(Quota.id == payload.quota_id, Quota.organization_id == user.organization_id))
    if not quota: raise HTTPException(status_code=404, detail="Cota não encontrada")
    reservation = reserve_quota(db, user, quota, payload.proposal_id, payload.ttl_minutes)
    db.flush(); audit(db, user, "quota.reserved", "reservation", reservation.id, {"quota_id": quota.id}); db.commit(); db.refresh(reservation)
    return reservation


@router.get("/reservations", response_model=list[ReservationView])
def list_reservations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    release_expired_reservations(db, user.organization_id); db.commit()
    return list(db.scalars(select(QuotaReservation).where(QuotaReservation.organization_id == user.organization_id).order_by(QuotaReservation.created_at.desc())))


@router.post("/reservations/{reservation_id}/release", response_model=ReservationView)
def release_reservation_route(reservation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reservation = db.scalar(select(QuotaReservation).where(QuotaReservation.id == reservation_id, QuotaReservation.organization_id == user.organization_id))
    if not reservation: raise HTTPException(status_code=404, detail="Reserva não encontrada")
    release_reservation(db, user, reservation); audit(db, user, "quota.released", "reservation", reservation.id); db.commit(); db.refresh(reservation)
    return reservation


@router.post("/nina/validate-combination")
def nina_validate_combination(
    quota_ids: list[str], target_amount: Decimal = Query(gt=0),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    quotas = list(db.scalars(select(Quota).where(Quota.id.in_(quota_ids), Quota.organization_id == user.organization_id)))
    if len(quotas) != len(set(quota_ids)):
        raise HTTPException(status_code=404, detail="Uma ou mais cotas não foram encontradas")
    return validate_quota_combination(quotas, float(target_amount), db=db, user_id=user.id)


@router.get("/proposals", response_model=list[ProposalView])
def list_proposals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Proposal).where(Proposal.organization_id == user.organization_id).order_by(Proposal.created_at.desc())))


@router.post("/proposals", response_model=ProposalView, status_code=201)
def create_proposal(payload: ProposalCreate, user: User = Depends(require_scope("proposals:write")), db: Session = Depends(get_db)):
    lead = db.scalar(select(Lead).where(Lead.id == payload.lead_id, Lead.organization_id == user.organization_id))
    if not lead: raise HTTPException(status_code=404, detail="Lead não encontrado")
    proposal = Proposal(
        organization_id=user.organization_id, lead_id=payload.lead_id, product=payload.product,
        requested_amount=payload.requested_amount, terms_json=json.dumps(payload.terms, ensure_ascii=False),
    )
    db.add(proposal); db.flush(); audit(db, user, "proposal.created", "proposal", proposal.id); db.commit(); db.refresh(proposal)
    return proposal


@router.patch("/proposals/{proposal_id}", response_model=ProposalView)
def update_proposal(proposal_id: str, payload: ProposalUpdate, user: User = Depends(require_scope("proposals:write")), db: Session = Depends(get_db)):
    proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id, Proposal.organization_id == user.organization_id))
    if not proposal: raise HTTPException(status_code=404, detail="Proposta não encontrada")
    changes = payload.model_dump(exclude_unset=True)
    if "terms" in changes: changes["terms_json"] = json.dumps(changes.pop("terms"), ensure_ascii=False)
    for field, value in changes.items(): setattr(proposal, field, value)
    audit(db, user, "proposal.updated", "proposal", proposal.id, payload.model_dump(exclude_unset=True, mode="json")); db.commit(); db.refresh(proposal)
    return proposal


@router.post("/proposals/{proposal_id}/calculate", response_model=CalculationView, status_code=201)
def calculate_proposal(proposal_id: str, payload: CalculationRequest, user: User = Depends(require_scope("proposals:write")), db: Session = Depends(get_db)):
    proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id, Proposal.organization_id == user.organization_id))
    if not proposal: raise HTTPException(status_code=404, detail="Proposta não encontrada")
    quotas = list(db.scalars(select(Quota).where(Quota.id.in_(payload.quota_ids), Quota.organization_id == user.organization_id)))
    if len(quotas) != len(set(payload.quota_ids)): raise HTTPException(status_code=404, detail="Uma ou mais cotas não foram encontradas")
    calculation = calculate_marketplace(db, user, proposal, quotas, payload.fee_percent, payload.start_fee)
    db.flush(); audit(db, user, "proposal.calculated", "calculation", calculation.id); db.commit(); db.refresh(calculation)
    return CalculationView(id=calculation.id, proposal_id=calculation.proposal_id, version=calculation.version, formula_version=calculation.formula_version, input=json.loads(calculation.input_json), output=json.loads(calculation.output_json), approved_at=calculation.approved_at)


def _sdc_quitcon_from_calculation(calculation: CalculationMemory) -> dict | None:
    if not calculation.formula_version.startswith("sdc-"):
        return None
    output = json.loads(calculation.output_json)
    input_data = json.loads(calculation.input_json)
    saldo = output.get("maturity_total") or output.get("principal")
    if not saldo:
        return None
    meses = output.get("duration_months") or input_data.get("duration_months")
    engine = EngineQuitConLetter()
    return engine.gerar_integracao_sdc_quitcon(Decimal(str(saldo)), int(meses) if meses is not None else None)


def calculation_view(calculation: CalculationMemory, *, attach_quitcon_sdc: bool = False) -> CalculationView:
    quitcon_sdc = _sdc_quitcon_from_calculation(calculation) if attach_quitcon_sdc else None
    return CalculationView(
        id=calculation.id, proposal_id=calculation.proposal_id, version=calculation.version,
        formula_version=calculation.formula_version, input=json.loads(calculation.input_json),
        output=json.loads(calculation.output_json), approved_at=calculation.approved_at,
        quitcon_sdc=quitcon_sdc,
    )


@router.post("/proposals/{proposal_id}/calculate-sdc", response_model=CalculationView, status_code=201)
def calculate_sdc_proposal(proposal_id: str, payload: SdcCalculationRequest, user: User = Depends(require_scope("proposals:write")), db: Session = Depends(get_db)):
    proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id, Proposal.organization_id == user.organization_id))
    if not proposal: raise HTTPException(status_code=404, detail="Proposta não encontrada")
    quotas = list(db.scalars(select(Quota).where(Quota.id.in_(payload.quota_ids), Quota.organization_id == user.organization_id)))
    if len(quotas) != len(set(payload.quota_ids)): raise HTTPException(status_code=404, detail="Uma ou mais cotas não foram encontradas")
    calculation = calculate_sdc(
        db, user, proposal, quotas, payload.duration_months, payload.capital_source,
        payload.pool_investor_rate_percent, payload.pool_investment_amount,
    )
    db.flush(); audit(db, user, "proposal.sdc_calculated", "calculation", calculation.id); db.commit(); db.refresh(calculation)
    return calculation_view(calculation, attach_quitcon_sdc=True)


@router.post("/proposals/{proposal_id}/calculate-flash-credit", response_model=CalculationView, status_code=201)
def calculate_flash_credit_proposal(proposal_id: str, payload: FlashCreditCalculationRequest, user: User = Depends(require_scope("proposals:write")), db: Session = Depends(get_db)):
    proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id, Proposal.organization_id == user.organization_id))
    if not proposal: raise HTTPException(status_code=404, detail="Proposta não encontrada")
    calculation = calculate_flash_credit(
        db, user, proposal, payload.asset_value, payload.capital_source,
        payload.term_months, payload.ipca_annual_percent,
        payload.pool_investor_rate_percent, payload.pool_investment_amount,
    )
    db.flush(); audit(db, user, "proposal.flash_credit_calculated", "calculation", calculation.id); db.commit(); db.refresh(calculation)
    return calculation_view(calculation)


@router.get("/proposals/{proposal_id}/calculations", response_model=list[CalculationView])
def list_calculations(proposal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id, Proposal.organization_id == user.organization_id))
    if not proposal: raise HTTPException(status_code=404, detail="Proposta não encontrada")
    rows = db.scalars(select(CalculationMemory).where(CalculationMemory.proposal_id == proposal.id).order_by(CalculationMemory.version.desc()))
    return [CalculationView(id=x.id, proposal_id=x.proposal_id, version=x.version, formula_version=x.formula_version, input=json.loads(x.input_json), output=json.loads(x.output_json), approved_at=x.approved_at) for x in rows]


@router.post("/public/quitcon/simulate")
def public_quitcon_simulator(payload: QuitConPublicSimulateRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    allowed, retry = rate_limiter.allow(f"public-quitcon:{ip}", settings.public_rate_limit_per_minute)
    if not allowed:
        raise HTTPException(429, "Limite do simulador atingido", headers={"Retry-After": str(retry)})
    engine = EngineQuitConLetter()
    return engine.simular_quitcon_doc253(
        payload.outstanding_balance,
        payload.meses_restantes,
        operational_service=payload.operational_service,
        administrator_name=payload.administrator_name,
        contemplada=payload.contemplada,
        bem_faturado=payload.bem_faturado,
        parcelas_em_dia=payload.parcelas_em_dia,
    )


@router.post("/public/site/leads/capture", status_code=201)
def public_site_lead_capture(payload: PublicLeadCaptureRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    allowed, retry = rate_limiter.allow(f"public-lead:{ip}", settings.public_rate_limit_per_minute)
    if not allowed:
        raise HTTPException(429, "Limite de captura atingido", headers={"Retry-After": str(retry)})
    result = capture_public_lead(
        db,
        razao_social=payload.razao_social,
        whatsapp=payload.whatsapp,
        produto=payload.produto,
        valor_base=payload.valor_base,
        autorizacao_scr_bacen=payload.autorizacao_scr_bacen,
    )
    db.commit()
    return result


@router.get("/public/site/quotas", response_model=list[PublicQuotaCatalogItem])
def public_site_quotas(request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    allowed, retry = rate_limiter.allow(f"public-quotas:{ip}", settings.public_rate_limit_per_minute)
    if not allowed:
        raise HTTPException(429, "Limite atingido", headers={"Retry-After": str(retry)})
    return list_public_quotas(db)


@router.post("/public/site/flash/simulate")
def public_site_flash_simulate(payload: PublicFlashPoolRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    allowed, retry = rate_limiter.allow(f"public-flash-pool:{ip}", settings.public_rate_limit_per_minute)
    if not allowed:
        raise HTTPException(429, "Limite do simulador atingido", headers={"Retry-After": str(retry)})
    return simulate_flash_pool_public(db, payload.asset_value, payload.requested_amount)


@router.post("/public/site/sdc/simulate")
def public_site_sdc_simulate(payload: PublicSdcSimulateRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    allowed, retry = rate_limiter.allow(f"public-sdc:{ip}", settings.public_rate_limit_per_minute)
    if not allowed:
        raise HTTPException(429, "Limite do simulador atingido", headers={"Retry-After": str(retry)})
    if payload.capital_source.upper() not in {"POOL", "FUND"}:
        raise HTTPException(422, "Fonte SDC deve ser POOL ou FUND")
    return simulate_sdc_public(
        db, payload.quota_ids, payload.requested_amount, payload.duration_months, payload.capital_source.upper(),
    )


@router.post("/public/site/chat/home")
def public_site_chat_home(request: Request, payload: dict | None = None):
    from app.public_chat_proxy import proxy_legacy_chat

    ip = request.client.host if request.client else "unknown"
    allowed, retry = rate_limiter.allow(f"public-chat:{ip}", settings.public_rate_limit_per_minute)
    if not allowed:
        raise HTTPException(429, "Limite do atendimento atingido", headers={"Retry-After": str(retry)})
    return proxy_legacy_chat(None, payload or {})


@router.post("/public/site/chat/home/{step}")
def public_site_chat_step(step: str, request: Request, payload: dict | None = None):
    from app.public_chat_proxy import proxy_legacy_chat

    ip = request.client.host if request.client else "unknown"
    allowed, retry = rate_limiter.allow(f"public-chat:{ip}", settings.public_rate_limit_per_minute)
    if not allowed:
        raise HTTPException(429, "Limite do atendimento atingido", headers={"Retry-After": str(retry)})
    return proxy_legacy_chat(step, payload or {})


@router.get("/finops/flash-capital/simulation-params", response_model=FlashCapitalSimulationParamsView)
def finops_flash_capital_simulation_params(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return FlashCapitalSimulationParamsView(**get_active_flash_simulation_params(db, user.organization_id))


@router.put("/finops/flash-capital/simulation-params", response_model=FlashCapitalSimulationParamsView)
def finops_flash_capital_simulation_params_update(
    payload: FlashCapitalSimulationParamsUpdate,
    user: User = Depends(require_scope("admin:users")),
    db: Session = Depends(get_db),
):
    save_flash_simulation_params(
        db,
        user,
        institutional_rate_annual=payload.institutional_rate_annual,
        retail_rate_monthly=payload.retail_rate_monthly,
    )
    audit(db, user, "finops.flash_capital.params_updated", "flash_credit_policy", user.organization_id)
    db.commit()
    return FlashCapitalSimulationParamsView(**get_active_flash_simulation_params(db, user.organization_id))


@router.post("/finops/flash-capital/simulate")
def finops_flash_capital_simulate(payload: FlashSimulatorRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    params = get_active_flash_simulation_params(db, user.organization_id)
    return four_scenarios(
        payload.asset_value,
        payload.requested_amount,
        payload.ipca_projected_percent,
        Decimal(params["institutional_rate_annual"]),
        Decimal(params["retail_rate_monthly"]),
    )


@router.post("/public/flash-credit/simulate")
def public_flash_simulator(payload:FlashSimulatorRequest,request:Request):
    ip=request.client.host if request.client else "unknown";allowed,retry=rate_limiter.allow(f"public-flash:{ip}",settings.public_rate_limit_per_minute)
    if not allowed:raise HTTPException(429,"Limite do simulador atingido",headers={"Retry-After":str(retry)})
    return four_scenarios(payload.asset_value,payload.requested_amount,payload.ipca_projected_percent)


@router.post("/public/flash-credit/settlement-curve")
def public_settlement_curve(payload:SettlementCurveRequest,request:Request):
    ip=request.client.host if request.client else "unknown";allowed,retry=rate_limiter.allow(f"public-settlement:{ip}",settings.public_rate_limit_per_minute)
    if not allowed:raise HTTPException(429,"Limite do simulador atingido",headers={"Retry-After":str(retry)})
    return settlement_curve(payload.principal,payload.track.upper(),payload.ipca_projected_percent,payload.balloon)


@router.post("/contracts/{contract_id}/early-settlement",response_model=EarlySettlementQuoteView,status_code=201)
def contract_early_settlement(contract_id:str,payload:ContractSettlementRequest,user:User=Depends(require_scope("contracts:read")),db:Session=Depends(get_db)):
    contract=db.scalar(select(Contract).where(Contract.id==contract_id,Contract.organization_id==user.organization_id))
    if not contract:raise HTTPException(404,"Contrato não encontrado")
    calculation=db.scalar(select(CalculationMemory).where(CalculationMemory.id==contract.calculation_memory_id,CalculationMemory.product=="FLASH_CREDIT"))
    if not calculation:raise HTTPException(422,"Contrato não possui memória Flash Capital")
    output=json.loads(calculation.output_json);principal=Decimal(str(output["principal"]))
    params = get_active_flash_simulation_params(db, user.organization_id)
    item=create_contract_quote(
        db, user, contract, principal, payload.track.upper(), payload.ipca_projected_percent,
        payload.balloon, payload.current_installment,
        Decimal(params["institutional_rate_annual"]), Decimal(params["retail_rate_monthly"]),
    )
    audit(db,user,"finops.early_settlement_quoted","early_settlement_quote",item.id,{"contract_id":contract.id,"sandbox_only":True});db.commit();db.refresh(item);return item


@router.get("/early-settlement-quotes",response_model=list[EarlySettlementQuoteView])
def early_settlement_quotes(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(EarlySettlementQuote).where(EarlySettlementQuote.organization_id==user.organization_id).order_by(EarlySettlementQuote.created_at.desc())))


@router.post("/finops/events",response_model=FinOpsEventView,status_code=202)
def finops_event_ingest(payload:FinOpsEventCreate,x_letter_signature:str=Header(alias="X-Letter-Signature"),user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    signed_payload=payload.model_dump()
    if not verify_webhook(settings.secret_key,x_letter_signature,signed_payload):raise HTTPException(401,"Assinatura HMAC inválida ou expirada")
    item,created=ingest_event(db,user,**signed_payload)
    if created:audit(db,user,"finops.event_received","finops_domain_event",item.id,{"event_type":item.event_type,"decision":item.decision})
    db.commit();db.refresh(item);return item


@router.get("/finops/events",response_model=list[FinOpsEventView])
def finops_events(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return list(db.scalars(select(FinOpsDomainEvent).where(FinOpsDomainEvent.organization_id==user.organization_id).order_by(FinOpsDomainEvent.received_at.desc())))


@router.get("/finops/tapaf/split-policy", response_model=TapafSplitPolicyView)
def finops_tapaf_split_policy(_: User = Depends(get_current_user)):
    return TapafSplitPolicyView(
        nominal_brl=str(TAPAF_NOMINAL),
        lote_a_api_reserve_brl=str(TAPAF_LOTE_A_API_RESERVE),
        lote_b_franchise_spread_brl=str(TAPAF_LOTE_B_FRANCHISE_SPREAD),
        estimated_api_cost_brl=str(TAPAF_ESTIMATED_TOTAL_API_COST),
        estimated_infra_margin_brl=str(TAPAF_ESTIMATED_INFRA_MARGIN),
    )


@router.get("/finops/tapaf/infra-catalog", response_model=list[InfraProviderCatalogItem])
def finops_tapaf_infra_catalog(_: User = Depends(get_current_user)):
    return [InfraProviderCatalogItem(**item) for item in catalog()]


@router.get("/finops/tapaf/settlements", response_model=list[TapafSettlementView])
def finops_tapaf_settlements(user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    return [TapafSettlementView(**item) for item in list_settlements(db, user)]


@router.get("/finops/tapaf/settlements/lookup", response_model=TapafSettlementView)
def finops_tapaf_settlement_lookup(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = get_settlement(db, user.organization_id, entity_type=entity_type, entity_id=entity_id)
    if not item:
        raise HTTPException(status_code=404, detail="Liquidação TAPAF não encontrada para esta entidade")
    return TapafSettlementView(**settlement_view(item))


@router.post("/finops/sdc/bullet-split-preview")
def sdc_bullet_split_preview(payload:SdcBulletPreviewRequest,user:User=Depends(require_scope("payments:review"))):
    return sdc_bullet_and_split(payload.capital,payload.turnover_days,payload.commission_pool,payload.level3_available)


@router.post("/finops/billing/invoice-processor")
def finops_invoice_processor(payload: InvoiceProcessorRequest, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    invoice = db.scalar(select(Invoice).where(Invoice.id == payload.invoice_id, Invoice.organization_id == user.organization_id))
    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura não encontrada")
    if invoice.status != "PAID":
        raise HTTPException(status_code=409, detail="Fatura deve estar PAID para emitir recibo FinOps")
    receipt = process_invoice_settlement(db, user, invoice)
    audit(db, user, "finops.invoice_processor", "payment_receipt", receipt.id)
    db.commit()
    return receipt_processor_response(receipt)


def _load_proposal(db: Session, user: User, proposal_id: str) -> Proposal:
    proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id, Proposal.organization_id == user.organization_id))
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    return proposal


@router.post("/finops/pre-analysis/validate-documents", response_model=PreAnalysisPautaView)
def pre_analysis_validate_documents(payload: PreAnalysisValidateDocumentsRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    proposal = _load_proposal(db, user, payload.proposal_id)
    pauta = validate_documents_phase1(db, user, proposal, [d.model_dump() for d in payload.documents])
    audit(db, user, "finops.pre_analysis.validate_documents", "pre_analysis_pauta", pauta.id)
    db.commit()
    return PreAnalysisPautaView(**pauta_view(pauta))


@router.post("/finops/pre-analysis/generate-tapaf")
def pre_analysis_generate_tapaf(payload: PreAnalysisProposalRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    proposal = _load_proposal(db, user, payload.proposal_id)
    pauta = db.scalar(select(PreAnalysisPauta).where(PreAnalysisPauta.proposal_id == proposal.id, PreAnalysisPauta.organization_id == user.organization_id))
    if not pauta:
        raise HTTPException(status_code=409, detail="Valide a documentação na Fase 1 antes de gerar TAPAF")
    return generate_tapaf_checkout(pauta)


@router.post("/finops/pre-analysis/tapaf-checkout-accept", response_model=PreAnalysisPautaView)
def pre_analysis_tapaf_checkout_accept(payload: PreAnalysisTapafCheckoutAcceptRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    proposal = _load_proposal(db, user, payload.proposal_id)
    pauta = db.scalar(select(PreAnalysisPauta).where(PreAnalysisPauta.proposal_id == proposal.id, PreAnalysisPauta.organization_id == user.organization_id))
    if not pauta:
        raise HTTPException(status_code=404, detail="Pauta de pré-análise não encontrada")
    accept_tapaf_checkout(db, pauta, scroll_completed=payload.scroll_completed, checkbox_1=payload.checkbox_1, checkbox_2=payload.checkbox_2)
    audit(db, user, "finops.pre_analysis.tapaf_checkout", "pre_analysis_pauta", pauta.id)
    db.commit()
    return PreAnalysisPautaView(**pauta_view(pauta))


@router.post("/finops/pre-analysis/tapaf-payment-webhook", response_model=PreAnalysisPautaView)
def pre_analysis_tapaf_payment_webhook(payload: PreAnalysisTapafPaymentWebhook, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    proposal = _load_proposal(db, user, payload.proposal_id)
    pauta = db.scalar(select(PreAnalysisPauta).where(PreAnalysisPauta.proposal_id == proposal.id, PreAnalysisPauta.organization_id == user.organization_id))
    if not pauta:
        raise HTTPException(status_code=404, detail="Pauta de pré-análise não encontrada")
    confirm_tapaf_payment(db, user, pauta, payload.event_id, payload.amount)
    audit(db, user, "finops.pre_analysis.tapaf_payment", "pre_analysis_pauta", pauta.id, {"event_id": payload.event_id})
    db.commit()
    return PreAnalysisPautaView(**pauta_view(pauta))


@router.post("/finops/pre-analysis/run-engine")
def pre_analysis_run_engine(payload: PreAnalysisEngineRequest, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    proposal = _load_proposal(db, user, payload.proposal_id)
    pauta = db.scalar(select(PreAnalysisPauta).where(PreAnalysisPauta.proposal_id == proposal.id, PreAnalysisPauta.organization_id == user.organization_id))
    if not pauta:
        raise HTTPException(status_code=404, detail="Pauta de pré-análise não encontrada")
    result = run_engine_phase3(db, user, pauta, proposal, payload.model_dump())
    audit(db, user, "finops.pre_analysis.run_engine", "pre_analysis_pauta", pauta.id, {"status_core": result.get("status_core")})
    db.commit()
    return {"pauta_id": pauta.pauta_code, "status": pauta.status, "result": result}


@router.get("/finops/pre-analysis/{proposal_id}", response_model=PreAnalysisPautaView)
def pre_analysis_get_pauta(proposal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    proposal = _load_proposal(db, user, proposal_id)
    pauta = db.scalar(select(PreAnalysisPauta).where(PreAnalysisPauta.proposal_id == proposal.id, PreAnalysisPauta.organization_id == user.organization_id))
    if not pauta:
        raise HTTPException(status_code=404, detail="Pauta de pré-análise não encontrada")
    return PreAnalysisPautaView(**pauta_view(pauta))


def _load_lease_pauta(db: Session, user: User, pauta_id: str) -> LeaseEquityPauta:
    pauta = db.scalar(select(LeaseEquityPauta).where(LeaseEquityPauta.id == pauta_id, LeaseEquityPauta.organization_id == user.organization_id))
    if not pauta:
        raise HTTPException(status_code=404, detail="Pauta Lease Equity não encontrada")
    return pauta


@router.post("/finops/lease-equity/pautas", response_model=LeaseEquityPautaView, status_code=201)
def lease_equity_create_pauta(payload: LeaseEquityPautaCreate, user: User = Depends(require_scope("proposals:write")), db: Session = Depends(get_db)):
    proposal = _load_proposal(db, user, payload.proposal_id)
    pauta = create_pauta(db, user, proposal, property_type=payload.property_type, appraisal_value=payload.appraisal_value, registry_number=payload.registry_number, registry_office=payload.registry_office, owner_user_id=payload.owner_user_id)
    audit(db, user, "finops.lease_equity.create", "lease_equity_pauta", pauta.id)
    db.commit()
    db.refresh(pauta)
    return LeaseEquityPautaView(**lease_pauta_view(pauta))


@router.get("/finops/lease-equity/pautas", response_model=list[LeaseEquityPautaView])
def lease_equity_list_pautas(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = list(db.scalars(select(LeaseEquityPauta).where(LeaseEquityPauta.organization_id == user.organization_id).order_by(LeaseEquityPauta.created_at.desc())))
    return [LeaseEquityPautaView(**lease_pauta_view(x)) for x in items]


@router.get("/finops/lease-equity/pautas/{pauta_id}", response_model=LeaseEquityPautaView)
def lease_equity_get_pauta(pauta_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return LeaseEquityPautaView(**lease_pauta_view(_load_lease_pauta(db, user, pauta_id)))


@router.post("/finops/lease-equity/tapaf-checkout")
def lease_equity_tapaf_checkout(pauta_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pauta = _load_lease_pauta(db, user, pauta_id)
    return generate_lease_tapaf(pauta)


@router.post("/finops/lease-equity/tapaf-payment-webhook", response_model=LeaseEquityPautaView)
def lease_equity_tapaf_webhook(payload: LeaseEquityTapafWebhook, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    pauta = _load_lease_pauta(db, user, payload.pauta_id)
    confirm_lease_tapaf(db, user, pauta, payload.event_id, payload.amount)
    audit(db, user, "finops.lease_equity.tapaf_paid", "lease_equity_pauta", pauta.id)
    db.commit()
    db.refresh(pauta)
    return LeaseEquityPautaView(**lease_pauta_view(pauta))


@router.post("/finops/lease-equity/inspection-photos", response_model=LeaseEquityPautaView)
def lease_equity_inspection(payload: LeaseEquityInspectionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pauta = _load_lease_pauta(db, user, payload.pauta_id)
    register_inspection_photos(db, user, pauta, [x.model_dump() for x in payload.photos])
    audit(db, user, "finops.lease_equity.inspection", "lease_equity_pauta", pauta.id)
    db.commit()
    db.refresh(pauta)
    return LeaseEquityPautaView(**lease_pauta_view(pauta))


@router.post("/finops/lease-equity/compliance-review", response_model=LeaseEquityPautaView)
def lease_equity_compliance(payload: LeaseEquityComplianceReview, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    pauta = _load_lease_pauta(db, user, payload.pauta_id)
    run_compliance_review(db, user, pauta, approved=payload.approved, blockers=payload.blockers)
    audit(db, user, "finops.lease_equity.compliance", "lease_equity_pauta", pauta.id, {"approved": payload.approved})
    db.commit()
    db.refresh(pauta)
    return LeaseEquityPautaView(**lease_pauta_view(pauta))


@router.post("/finops/lease-equity/sign-contract", response_model=LeaseEquityPautaView)
def lease_equity_sign(pauta_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pauta = _load_lease_pauta(db, user, pauta_id)
    sign_contract(db, user, pauta)
    db.commit()
    db.refresh(pauta)
    return LeaseEquityPautaView(**lease_pauta_view(pauta))


@router.post("/finops/lease-equity/submit-registry", response_model=LeaseEquityPautaView)
def lease_equity_registry(pauta_id: str, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    pauta = _load_lease_pauta(db, user, pauta_id)
    submit_registry_protocol(db, user, pauta)
    db.commit()
    db.refresh(pauta)
    return LeaseEquityPautaView(**lease_pauta_view(pauta))


@router.post("/finops/lease-equity/complete-gravame", response_model=LeaseEquityPautaView)
def lease_equity_gravame(pauta_id: str, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    pauta = _load_lease_pauta(db, user, pauta_id)
    complete_gravame(db, user, pauta)
    db.commit()
    db.refresh(pauta)
    return LeaseEquityPautaView(**lease_pauta_view(pauta))


@router.post("/finops/lease-equity/funding-capture", response_model=LeaseEquityPautaView)
def lease_equity_funding(payload: LeaseEquityFundingCapture, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    pauta = _load_lease_pauta(db, user, payload.pauta_id)
    record_funding_capture(db, user, pauta, payload.amount)
    db.commit()
    db.refresh(pauta)
    return LeaseEquityPautaView(**lease_pauta_view(pauta))


@router.post("/finops/lease-equity/activate", response_model=LeaseEquityPautaView)
def lease_equity_activate(payload: LeaseEquityActivateRequest, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    pauta = _load_lease_pauta(db, user, payload.pauta_id)
    activate_ok(db, user, pauta, manual=payload.manual)
    audit(db, user, "finops.lease_equity.activate", "lease_equity_pauta", pauta.id, {"manual": payload.manual})
    db.commit()
    db.refresh(pauta)
    return LeaseEquityPautaView(**lease_pauta_view(pauta))


@router.post("/finops/lease-equity/refresh-anticipation")
def lease_equity_refresh_anticipation(payload: LeaseEquityMonthsRequest, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    pauta = _load_lease_pauta(db, user, payload.pauta_id)
    refresh_anticipation_eligibility(db, user, pauta, payload.months_in_force)
    db.commit()
    db.refresh(pauta)
    return LeaseEquityPautaView(**lease_pauta_view(pauta))


@router.post("/finops/lease-equity/simulate-ltv")
def lease_equity_simulate_ltv(payload: LeaseEquityLtvSimulateRequest, user: User = Depends(get_current_user)):
    engine = EngineLeaseEquityLetter()
    return engine.processar_matriz_credito_ltv(payload.property_type, payload.appraisal_value)


@router.post("/finops/lease-equity/simulate-anticipation")
def lease_equity_simulate_anticipation(payload: LeaseEquityAnticipationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pauta = _load_lease_pauta(db, user, payload.pauta_id)
    return simulate_anticipation(pauta, payload.parcelas_restantes)


@router.post("/finops/lease-equity/tokenization-processor")
def lease_equity_tokenization(payload: LeaseEquityTokenizationRequest, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    pauta = _load_lease_pauta(db, user, payload.pauta_id)
    result = process_tokenization(pauta, payload.owner_uid)
    audit(db, user, "finops.lease_equity.tokenization", "lease_equity_pauta", pauta.id)
    db.commit()
    return result


def _load_quitcon_operacao(db: Session, user: User, operacao_id: str) -> QuitConOperacao:
    operacao = db.scalar(
        select(QuitConOperacao).where(
            QuitConOperacao.id == operacao_id,
            QuitConOperacao.organization_id == user.organization_id,
        )
    )
    if not operacao:
        raise HTTPException(status_code=404, detail="Operação QuitCon não encontrada")
    return operacao


@router.post("/finops/quitcon/operacoes", response_model=QuitConOperacaoView, status_code=201)
def quitcon_create_operacao(payload: QuitConOperacaoCreate, user: User = Depends(require_scope("proposals:write")), db: Session = Depends(get_db)):
    proposal = _load_proposal(db, user, payload.proposal_id)
    operacao = create_operacao(
        db, user, proposal,
        property_type=payload.property_type,
        appraisal_value=payload.appraisal_value,
        outstanding_balance=payload.outstanding_balance,
        registry_number=payload.registry_number,
        registry_office=payload.registry_office,
        quota_id=payload.quota_id,
        owner_user_id=payload.owner_user_id,
        meses_restantes=payload.meses_restantes,
        operational_service=payload.operational_service,
        contemplada=payload.contemplada,
        bem_faturado=payload.bem_faturado,
        parcelas_em_dia=payload.parcelas_em_dia,
    )
    audit(db, user, "finops.quitcon.create", "quitcon_operacao", operacao.id)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.get("/finops/quitcon/operacoes", response_model=list[QuitConOperacaoView])
def quitcon_list_operacoes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = list(db.scalars(
        select(QuitConOperacao).where(QuitConOperacao.organization_id == user.organization_id).order_by(QuitConOperacao.created_at.desc())
    ))
    return [QuitConOperacaoView(**quitcon_operacao_view(x)) for x in items]


@router.get("/finops/quitcon/operacoes/{operacao_id}", response_model=QuitConOperacaoView)
def quitcon_get_operacao(operacao_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return QuitConOperacaoView(**quitcon_operacao_view(_load_quitcon_operacao(db, user, operacao_id)))


@router.post("/finops/quitcon/tapaf-checkout")
def quitcon_tapaf_checkout(operacao_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, operacao_id)
    return generate_quitcon_tapaf(operacao)


@router.post("/finops/quitcon/tapaf-payment-webhook", response_model=QuitConOperacaoView)
def quitcon_tapaf_webhook(payload: QuitConTapafWebhook, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, payload.operacao_id)
    confirm_quitcon_tapaf(db, user, operacao, payload.event_id, payload.amount)
    audit(db, user, "finops.quitcon.tapaf_paid", "quitcon_operacao", operacao.id)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/inspection-photos", response_model=QuitConOperacaoView)
def quitcon_inspection(payload: QuitConInspectionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, payload.operacao_id)
    register_quitcon_inspection(db, user, operacao, [x.model_dump() for x in payload.photos])
    audit(db, user, "finops.quitcon.inspection", "quitcon_operacao", operacao.id)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/compliance-review", response_model=QuitConOperacaoView)
def quitcon_compliance(payload: QuitConComplianceReview, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, payload.operacao_id)
    run_quitcon_compliance(db, user, operacao, approved=payload.approved, blockers=payload.blockers)
    audit(db, user, "finops.quitcon.compliance", "quitcon_operacao", operacao.id, {"approved": payload.approved})
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/administrator-approval", response_model=QuitConOperacaoView)
def quitcon_administrator_approval(operacao_id: str, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, operacao_id)
    register_administrator_approval(db, user, operacao)
    audit(db, user, "finops.quitcon.administrator_approval", "quitcon_operacao", operacao.id)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/sign-contract", response_model=QuitConOperacaoView)
def quitcon_sign(operacao_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, operacao_id)
    sign_quitcon_contract(db, user, operacao)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/submit-registry", response_model=QuitConOperacaoView)
def quitcon_registry(operacao_id: str, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, operacao_id)
    submit_quitcon_registry(db, user, operacao)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/complete-gravame", response_model=QuitConOperacaoView)
def quitcon_gravame(operacao_id: str, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, operacao_id)
    complete_quitcon_gravame(db, user, operacao)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/funding-capture", response_model=QuitConOperacaoView)
def quitcon_funding(payload: QuitConFundingCapture, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, payload.operacao_id)
    record_quitcon_funding(db, user, operacao, payload.amount)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/activate", response_model=QuitConOperacaoView)
def quitcon_activate(payload: QuitConActivateRequest, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, payload.operacao_id)
    activate_quitcon_ok(db, user, operacao, manual=payload.manual)
    audit(db, user, "finops.quitcon.activate", "quitcon_operacao", operacao.id, {"manual": payload.manual})
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/cancel-inadimplencia", response_model=QuitConOperacaoView)
def quitcon_cancel_inadimplencia(payload: QuitConCancelInadimplenciaRequest, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, payload.operacao_id)
    cancel_inadimplencia_cessionario(db, user, operacao, days_overdue=payload.days_overdue)
    audit(db, user, "finops.quitcon.cancel_inadimplencia", "quitcon_operacao", operacao.id)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/cancel-desistencia", response_model=QuitConOperacaoView)
def quitcon_cancel_desistencia(operacao_id: str, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, operacao_id)
    cancel_desistencia_cedente(db, user, operacao)
    audit(db, user, "finops.quitcon.cancel_desistencia", "quitcon_operacao", operacao.id)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/sdc/start-quitcon", response_model=SdcStartQuitConResponse)
def sdc_start_quitcon(payload: SdcStartQuitConRequest, user: User = Depends(require_scope("proposals:write")), db: Session = Depends(get_db)):
    if not payload.confirmation:
        raise HTTPException(status_code=422, detail="Confirme o avanço para abrir a operação QuitCon")
    if not payload.proposal_id and not payload.contract_id:
        raise HTTPException(status_code=422, detail="Informe proposal_id ou contract_id")
    result = start_quitcon_from_sdc(
        db,
        user,
        proposal_id=payload.proposal_id,
        contract_id=payload.contract_id,
        calculation_memory_id=payload.calculation_memory_id,
        meses_restantes=payload.meses_restantes,
    )
    audit(
        db,
        user,
        "finops.sdc.quitcon_started" if result["created"] else "finops.sdc.quitcon_existing",
        "quitcon_operacao",
        result["operacao_id"],
        {"origem": "SDC_SIMULADOR"},
    )
    db.commit()
    body = SdcStartQuitConResponse(**result)
    if result["created"]:
        return JSONResponse(status_code=201, content=body.model_dump())
    return body


@router.post("/finops/sdc/quitcon-projection", response_model=SdcQuitConIntegrationView)
def sdc_quitcon_projection(payload: SdcQuitConProjectionRequest, user: User = Depends(get_current_user)):
    engine = EngineQuitConLetter()
    return engine.gerar_integracao_sdc_quitcon(payload.saldo_devedor_simulado, payload.meses_restantes)


@router.get("/contracts/{contract_id}/sdc-quitcon-card", response_model=SdcQuitConIntegrationView)
def contract_sdc_quitcon_card(contract_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contract = db.scalar(select(Contract).where(Contract.id == contract_id, Contract.organization_id == user.organization_id))
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    if not contract.template_version.startswith("sdc-"):
        raise HTTPException(status_code=422, detail="Contrato não é SDC")
    if contract.status not in {"ACCEPTED", "SIGNED"}:
        raise HTTPException(status_code=422, detail="Contrato SDC não está ativo para exibição QuitCon")
    calculation = db.get(CalculationMemory, contract.calculation_memory_id)
    if not calculation:
        raise HTTPException(status_code=404, detail="Memória de cálculo não encontrada")
    bundle = _sdc_quitcon_from_calculation(calculation)
    if not bundle:
        raise HTTPException(status_code=422, detail="Não foi possível derivar projeção QuitCon para este contrato")
    return bundle


@router.post("/finops/quitcon/simulate")
def quitcon_simulate(payload: QuitConSimulateRequest, user: User = Depends(get_current_user)):
    engine = EngineQuitConLetter()
    return engine.simular_quitcon_doc253(
        payload.outstanding_balance,
        payload.meses_restantes,
        operational_service=payload.operational_service,
        administrator_name=payload.administrator_name,
        contemplada=payload.contemplada,
        bem_faturado=payload.bem_faturado,
        parcelas_em_dia=payload.parcelas_em_dia,
    )


@router.get("/finops/quitcon/administradoras-whitelist")
def quitcon_administradoras_whitelist(user: User = Depends(get_current_user)):
    engine = EngineQuitConLetter()
    return {"administradoras": list(engine.administradoras_whitelist)}


@router.post("/finops/quitcon/operational-service-checkout")
def quitcon_operational_service_checkout(operacao_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, operacao_id)
    return generate_operational_service_checkout(operacao)


@router.post("/finops/quitcon/operational-service-payment-webhook", response_model=QuitConOperacaoView)
def quitcon_operational_service_webhook(payload: QuitConOperationalServiceWebhook, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, payload.operacao_id)
    confirm_operational_service_payment(db, user, operacao, payload.event_id, payload.amount)
    audit(db, user, "finops.quitcon.operational_service_paid", "quitcon_operacao", operacao.id)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/success-fee-checkout")
def quitcon_success_fee_checkout(operacao_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, operacao_id)
    return generate_success_fee_checkout(operacao)


@router.post("/finops/quitcon/success-fee-payment-webhook", response_model=QuitConOperacaoView)
def quitcon_success_fee_webhook(payload: QuitConSuccessFeeWebhook, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, payload.operacao_id)
    confirm_success_fee_payment(db, user, operacao, payload.event_id, payload.amount)
    audit(db, user, "finops.quitcon.success_fee_paid", "quitcon_operacao", operacao.id)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/administrator-rejection", response_model=QuitConOperacaoView)
def quitcon_admin_rejection(payload: QuitConAdminRejectionRequest, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, payload.operacao_id)
    register_administrator_rejection(db, user, operacao, reason=payload.reason or "")
    audit(db, user, "finops.quitcon.admin_rejection", "quitcon_operacao", operacao.id)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/cedente-payment-checkout")
def quitcon_cedente_payment_checkout(operacao_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, operacao_id)
    return generate_cedente_payment_checkout(operacao)


@router.post("/finops/quitcon/cedente-payment-webhook", response_model=QuitConOperacaoView)
def quitcon_cedente_payment_webhook(payload: QuitConCedentePaymentWebhook, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, payload.operacao_id)
    confirm_cedente_payment_escrow(db, user, operacao, payload.event_id, payload.amount)
    audit(db, user, "finops.quitcon.cedente_payment_escrow", "quitcon_operacao", operacao.id)
    db.commit()
    db.refresh(operacao)
    return QuitConOperacaoView(**quitcon_operacao_view(operacao))


@router.post("/finops/quitcon/simulate-ltv")
def quitcon_simulate_ltv_legacy(payload: QuitConSimulateRequest, user: User = Depends(get_current_user)):
    """Legado — QuitCon não usa LTV assimétrico; redireciona para simulação por saldo devedor."""
    return quitcon_simulate(payload, user)


@router.post("/finops/quitcon/tokenization-processor")
def quitcon_tokenization(payload: QuitConTokenizationRequest, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    operacao = _load_quitcon_operacao(db, user, payload.operacao_id)
    result = process_quitcon_tokenization(operacao, payload.owner_uid)
    audit(db, user, "finops.quitcon.tokenization", "quitcon_operacao", operacao.id)
    db.commit()
    return result


@router.get("/help/what-is-flash-capital")
def help_what_is_flash_capital():
    return {
        "title": "Flash Capital",
        "summary": (
            "Esteira alternativa de crédito estruturado com compra e pacto de retrovenda imobiliária B2B, "
            "sem exigência de score Bacen tradicional nem comprovação de faturamento PJ no formato SDC."
        ),
        "rate": "2,5% a.m. fruição (pool e fundo — Tabela Price)",
        "use_when": [
            "Restrição cadastral identificada na Fase 3",
            "Bem com idade superior a 10 anos",
            "Parcela acima de 30% da renda com migração voluntária",
        ],
    }


@router.get("/contracts/{contract_id}/receipts", response_model=list[PaymentReceiptView])
def contract_receipts(contract_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contract = db.scalar(select(Contract).where(Contract.id == contract_id, Contract.organization_id == user.organization_id))
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    rows = db.scalars(select(PaymentReceipt).where(PaymentReceipt.contract_id == contract_id).order_by(PaymentReceipt.reference_month))
    return [PaymentReceiptView(**receipt_view(x)) for x in rows]


@router.post("/contracts/{contract_id}/native-inspection", response_model=CollateralNativeInspectionView, status_code=201)
def contract_native_inspection(
    contract_id: str,
    payload: ContractNativeInspectionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = db.scalar(select(Contract).where(Contract.id == contract_id, Contract.organization_id == user.organization_id))
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    item = register_contract_native_inspection(db, user, contract, [x.model_dump() for x in payload.photos])
    audit(db, user, "collateral.native_inspection", "collateral_native_inspection", item.id, {"contract_id": contract_id})
    db.commit()
    db.refresh(item)
    return CollateralNativeInspectionView(**inspection_view(item))


@router.get("/contracts/{contract_id}/native-inspection", response_model=CollateralNativeInspectionView)
def contract_native_inspection_get(contract_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contract = db.scalar(select(Contract).where(Contract.id == contract_id, Contract.organization_id == user.organization_id))
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    item = resolve_inspection_for_contract(db, contract_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vistoria nativa não registrada para este contrato")
    return CollateralNativeInspectionView(**inspection_view(item))


@router.get("/customer/dashboard/contracts/{contract_id}/receipts", response_model=list[PaymentReceiptView])
def customer_contract_receipts(contract_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return contract_receipts(contract_id, user, db)


@router.get("/contracts/{contract_id}/receipts/{receipt_id}/pdf")
def receipt_pdf_by_id(contract_id: str, receipt_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _receipt_pdf_response(contract_id, user, db, receipt_id=receipt_id)


@router.get("/customer/dashboard/contracts/{contract_id}/receipts/{filename}")
def customer_receipt_pdf(contract_id: str, filename: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _receipt_pdf_response(contract_id, user, db, filename=filename)


def _receipt_pdf_response(contract_id: str, user: User, db: Session, *, receipt_id: str | None = None, filename: str | None = None):
    contract = db.scalar(select(Contract).where(Contract.id == contract_id, Contract.organization_id == user.organization_id))
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    query = select(PaymentReceipt).where(PaymentReceipt.contract_id == contract_id)
    if receipt_id:
        query = query.where(PaymentReceipt.id == receipt_id)
    else:
        query = query.where(PaymentReceipt.filename == filename)
    receipt = db.scalar(query)
    if not receipt:
        raise HTTPException(status_code=404, detail="Recibo não encontrado")
    doc = db.get(Document, receipt.document_id) if receipt.document_id else None
    key = doc.storage_key if doc else f"customer-vault/contracts/{contract_id}/receipts/{receipt.filename}"
    try:
        pdf = get_storage().get(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo PDF não encontrado no acervo")
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{receipt.filename}"'})


@router.post("/flash-credit/policies",response_model=FlashCreditPolicyView,status_code=201)
def flash_policy_create(payload:FlashCreditPolicyCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=create_flash_policy(db,user,**payload.model_dump());audit(db,user,"flash_credit.policy_created","flash_credit_policy",item.id);db.commit();db.refresh(item);return item


@router.get("/flash-credit/policies",response_model=list[FlashCreditPolicyView])
def flash_policy_list(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(FlashCreditPolicy).where(FlashCreditPolicy.organization_id==user.organization_id).order_by(FlashCreditPolicy.version.desc())))


@router.post("/flash-credit/policies/{policy_id}/approve",response_model=FlashCreditPolicyView)
def flash_policy_approve(policy_id:str,user:User=Depends(require_step_up),_:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(FlashCreditPolicy).where(FlashCreditPolicy.id==policy_id,FlashCreditPolicy.organization_id==user.organization_id))
    if not item:raise HTTPException(404,"Política Flash Capital não encontrada")
    approve_flash_policy(db,user,item);audit(db,user,"flash_credit.policy_approved","flash_credit_policy",item.id);db.commit();db.refresh(item);return item


@router.post("/flash-credit/proposals/{proposal_id}/parties",response_model=FlashCreditRouteView)
def flash_parties(proposal_id:str,payload:FlashCreditPartiesCreate,user:User=Depends(require_scope("proposals:write")),db:Session=Depends(get_db)):
    proposal=db.scalar(select(Proposal).where(Proposal.id==proposal_id,Proposal.organization_id==user.organization_id))
    if not proposal:raise HTTPException(404,"Proposta não encontrada")
    route=configure_flash_parties(db,user,proposal,**payload.model_dump());audit(db,user,"flash_credit.parties_configured","proposal",proposal.id,{"route":route["route"]});db.commit();return route


@router.post("/nina-routing/policies",response_model=NinaRoutingPolicyView,status_code=201)
def nina_routing_policy_create(payload:NinaRoutingPolicyCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=create_routing_policy(db,user,**payload.model_dump());audit(db,user,"nina.routing_policy_created","nina_routing_policy",item.id);db.commit();db.refresh(item);return item


@router.get("/nina-routing/policies",response_model=list[NinaRoutingPolicyView])
def nina_routing_policies(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(NinaRoutingPolicy).where(NinaRoutingPolicy.organization_id==user.organization_id).order_by(NinaRoutingPolicy.version.desc())))


@router.post("/nina-routing/policies/{policy_id}/approve",response_model=NinaRoutingPolicyView)
def nina_routing_policy_approve(policy_id:str,user:User=Depends(require_step_up),_:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(NinaRoutingPolicy).where(NinaRoutingPolicy.id==policy_id,NinaRoutingPolicy.organization_id==user.organization_id))
    if not item:raise HTTPException(404,"Política de roteamento não encontrada")
    approve_routing_policy(db,user,item);audit(db,user,"nina.routing_policy_approved","nina_routing_policy",item.id);db.commit();db.refresh(item);return item


@router.post("/nina-routing/proposals/{proposal_id}/assess",response_model=NinaRoutingAssessmentView,status_code=201)
def nina_routing_assess(proposal_id:str,payload:NinaRoutingAssessmentCreate,user:User=Depends(require_scope("proposals:write")),db:Session=Depends(get_db)):
    proposal=db.scalar(select(Proposal).where(Proposal.id==proposal_id,Proposal.organization_id==user.organization_id));policy=db.scalar(select(NinaRoutingPolicy).where(NinaRoutingPolicy.organization_id==user.organization_id,NinaRoutingPolicy.status=="ACTIVE").order_by(NinaRoutingPolicy.version.desc()))
    if not proposal:raise HTTPException(404,"Proposta não encontrada")
    if not policy:raise HTTPException(409,"Não há política NINA ativa")
    item=assess_nina_route(db,user,proposal,policy,**payload.model_dump());audit(db,user,"nina.routing_assessed","nina_routing_assessment",item.id,{"product_route":item.product_route,"capital_route":item.capital_route});db.commit();db.refresh(item);return nina_routing_view(item)


@router.get("/nina-routing/assessments",response_model=list[NinaRoutingAssessmentView])
def nina_routing_assessments(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return [nina_routing_view(x) for x in db.scalars(select(NinaRoutingAssessment).where(NinaRoutingAssessment.organization_id==user.organization_id).order_by(NinaRoutingAssessment.created_at.desc()))]


@router.post("/nina-routing/assessments/{assessment_id}/approve",response_model=NinaRoutingAssessmentView)
def nina_routing_assessment_approve(assessment_id:str,user:User=Depends(require_step_up),_:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(NinaRoutingAssessment).where(NinaRoutingAssessment.id==assessment_id,NinaRoutingAssessment.organization_id==user.organization_id))
    if not item:raise HTTPException(404,"Avaliação NINA não encontrada")
    _,stamp=approve_routing_assessment(db,user,item);audit(db,user,"nina.routing_assessment_approved","nina_routing_assessment",item.id,{"stamp_code":stamp.stamp_code,"payout_authorized":False});db.commit();db.refresh(item);return nina_routing_view(item)


@router.get("/nina-routing/source-policy")
def nina_routing_source_policy(_:User=Depends(get_current_user)):return nina_source_policy()


@router.get("/valid-stamps/requirements")
def valid_stamp_requirements_list(asset_type: str, product: str = "FLASH_CAPITAL", _: User = Depends(get_current_user)):
    return valid_stamp_requirements(asset_type, product)


@router.post("/vehicles/registry-check")
def vehicle_registry_check(
    payload: dict,
    user: User = Depends(require_scope("proposals:write")),
):
    return query_vehicle_registry(
        plate=str(payload.get("plate", "")),
        uf=str(payload.get("uf", "")),
        vehicle_class=str(payload.get("vehicle_class", "")),
        renavam=str(payload.get("renavam")) if payload.get("renavam") else None,
    )


@router.post("/valid-stamps",response_model=ValidStampView,status_code=201)
def valid_stamp_create(payload:ValidStampCreate,user:User=Depends(require_step_up),_:User=Depends(require_scope("documents:write")),db:Session=Depends(get_db)):
    item=issue_stamp(db,user,**payload.model_dump());audit(db,user,"valid_stamp.issued","valid_stamp",item.id,{"stamp_code":item.stamp_code,"chain_hash":item.chain_hash});db.commit();db.refresh(item);return item


@router.get("/valid-stamps",response_model=list[ValidStampView])
def valid_stamp_list(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(ValidStamp).where(ValidStamp.organization_id==user.organization_id).order_by(ValidStamp.issued_at.desc())))


@router.get("/valid-stamps/{stamp_code}/verify")
def valid_stamp_verify(stamp_code:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    item=db.scalar(select(ValidStamp).where(ValidStamp.stamp_code==stamp_code,ValidStamp.organization_id==user.organization_id))
    if not item:raise HTTPException(404,"Selo não encontrado")
    return verify_stamp(item)


@router.post("/lss/terms",response_model=SaaSTermsView,status_code=201)
def lss_terms_create(payload:SaaSTermsCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=create_terms(db,user,**payload.model_dump());audit(db,user,"lss.terms_created","saas_terms",item.id);db.commit();db.refresh(item);return item


@router.get("/lss/terms",response_model=list[SaaSTermsView])
def lss_terms_list(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(SaaSTermsTemplate).where(SaaSTermsTemplate.organization_id==user.organization_id).order_by(SaaSTermsTemplate.version.desc())))


@router.post("/lss/terms/{terms_id}/approve",response_model=SaaSTermsView)
def lss_terms_approve(terms_id:str,user:User=Depends(require_step_up),_:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(SaaSTermsTemplate).where(SaaSTermsTemplate.id==terms_id,SaaSTermsTemplate.organization_id==user.organization_id))
    if not item:raise HTTPException(404,"Termos não encontrados")
    approve_terms(db,user,item);audit(db,user,"lss.terms_approved","saas_terms",item.id);db.commit();db.refresh(item);return item


@router.post("/lss/plans",response_model=SaaSPlanView,status_code=201)
def lss_plan_create(payload:SaaSPlanCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=create_plan(db,user,**payload.model_dump());audit(db,user,"lss.plan_created","saas_plan",item.id);db.commit();db.refresh(item);return item


@router.get("/lss/plans",response_model=list[SaaSPlanView])
def lss_plans(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(SaaSPlan).where(SaaSPlan.organization_id==user.organization_id,SaaSPlan.active.is_(True)).order_by(SaaSPlan.monthly_price)))


@router.post("/lss/subscriptions",response_model=SaaSSubscriptionView,status_code=201)
def lss_subscribe(payload:SaaSSubscribeCreate,request:Request,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    plan=db.scalar(select(SaaSPlan).where(SaaSPlan.id==payload.plan_id,SaaSPlan.organization_id==user.organization_id,SaaSPlan.active.is_(True)))
    terms=db.scalar(select(SaaSTermsTemplate).where(SaaSTermsTemplate.id==payload.terms_template_id,SaaSTermsTemplate.organization_id==user.organization_id))
    if not plan or not terms:raise HTTPException(404,"Plano ou termos não encontrados")
    values=payload.model_dump(exclude={"plan_id","terms_template_id"});values["ip_address"]=values["ip_address"] or (request.client.host if request.client else None);values["user_agent"]=values["user_agent"] or request.headers.get("user-agent")
    item=subscribe(db,user,plan,terms,**values);audit(db,user,"lss.subscription_accepted","saas_subscription",item.id,{"acceptance_hash":item.acceptance_hash});db.commit();db.refresh(item);return item


@router.get("/lss/subscriptions",response_model=list[SaaSSubscriptionView])
def lss_subscriptions(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(SaaSSubscription).where(SaaSSubscription.organization_id==user.organization_id).order_by(SaaSSubscription.created_at.desc())))


@router.post("/lss/subscriptions/{subscription_id}/cancel",response_model=SaaSSubscriptionView)
def lss_cancel(subscription_id:str,user:User=Depends(require_step_up),db:Session=Depends(get_db)):
    item=db.scalar(select(SaaSSubscription).where(SaaSSubscription.id==subscription_id,SaaSSubscription.organization_id==user.organization_id))
    if not item:raise HTTPException(404,"Assinatura não encontrada")
    cancel_subscription(item);audit(db,user,"lss.cancellation_scheduled","saas_subscription",item.id);db.commit();db.refresh(item);return item


@router.post("/lss/subscriptions/{subscription_id}/evaluate",response_model=SaaSSubscriptionView)
def lss_evaluate(subscription_id:str,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(SaaSSubscription).where(SaaSSubscription.id==subscription_id,SaaSSubscription.organization_id==user.organization_id))
    if not item:raise HTTPException(404,"Assinatura não encontrada")
    evaluate_subscription(item);audit(db,user,"lss.subscription_evaluated","saas_subscription",item.id,{"sandbox_only":True});db.commit();db.refresh(item);return item


@router.get("/lss/plans/{plan_id}/allocation-preview")
def lss_allocation(plan_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    item=db.scalar(select(SaaSPlan).where(SaaSPlan.id==plan_id,SaaSPlan.organization_id==user.organization_id))
    if not item:raise HTTPException(404,"Plano não encontrado")
    return subscription_allocation(item)


@router.post("/proposals/{proposal_id}/contracts", response_model=ContractView, status_code=201)
def create_contract_route(proposal_id: str, payload: ContractCreate, user: User = Depends(require_scope("proposals:write")), db: Session = Depends(get_db)):
    proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id, Proposal.organization_id == user.organization_id))
    calculation = db.scalar(select(CalculationMemory).where(CalculationMemory.id == payload.calculation_memory_id, CalculationMemory.organization_id == user.organization_id))
    if not proposal or not calculation: raise HTTPException(status_code=404, detail="Proposta ou memória de cálculo não encontrada")
    contract = create_contract(db, user, proposal, calculation)
    link_inspection_to_contract(db, proposal.id, contract.id)
    db.flush()
    audit(db, user, "contract.created", "contract", contract.id)
    db.commit()
    db.refresh(contract)
    return contract


@router.get("/contracts", response_model=list[ContractView])
def list_contracts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Contract).where(Contract.organization_id == user.organization_id).order_by(Contract.created_at.desc())))


@router.post("/contracts/{contract_id}/accept", response_model=ContractView)
def accept_contract(contract_id: str, payload: ContractAccept, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contract = db.scalar(select(Contract).where(Contract.id == contract_id, Contract.organization_id == user.organization_id))
    if not contract: raise HTTPException(status_code=404, detail="Contrato não encontrado")
    if not payload.confirmation: raise HTTPException(status_code=422, detail="Confirmação expressa obrigatória")
    if contract.status != "DRAFT": raise HTTPException(status_code=409, detail="Contrato não está disponível para aceite")
    contract.status = "ACCEPTED"; contract.accepted_at = datetime.now(UTC); contract.accepted_by_id = user.id
    contract.evidence_json = json.dumps(payload.model_dump(), ensure_ascii=False)
    audit(db, user, "contract.accepted", "contract", contract.id, payload.model_dump()); db.commit(); db.refresh(contract)
    return contract


@router.post("/acceptance-templates", response_model=AcceptanceTemplateView, status_code=201)
def acceptance_template_create(payload: AcceptanceTemplateCreate, user: User=Depends(require_scope("admin:users")), db: Session=Depends(get_db)):
    item=create_acceptance_template(db,user,**payload.model_dump());audit(db,user,"acceptance_template.created","acceptance_template",item.id,{"type":item.acceptance_type,"version":item.version});db.commit();db.refresh(item);return item


@router.get("/acceptance-templates", response_model=list[AcceptanceTemplateView])
def acceptance_templates(user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    return list(db.scalars(select(AcceptanceTemplate).where(AcceptanceTemplate.organization_id==user.organization_id).order_by(AcceptanceTemplate.acceptance_type,AcceptanceTemplate.version.desc())))


@router.post("/acceptance-templates/{template_id}/approve", response_model=AcceptanceTemplateView)
def acceptance_template_approve(template_id: str, user: User=Depends(require_step_up), _: User=Depends(require_scope("admin:users")), db: Session=Depends(get_db)):
    item=db.scalar(select(AcceptanceTemplate).where(AcceptanceTemplate.id==template_id,AcceptanceTemplate.organization_id==user.organization_id))
    if not item: raise HTTPException(404,"Texto de aceite não encontrado")
    approve_template(db,user,item);audit(db,user,"acceptance_template.legally_approved","acceptance_template",item.id,{"body_hash":item.body_hash});db.commit();db.refresh(item);return item


@router.post("/contracts/{contract_id}/checkout-acceptance", response_model=TransactionAcceptanceView, status_code=201)
def checkout_acceptance(contract_id: str, payload: CheckoutAcceptanceCreate, request: Request, user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    contract=db.scalar(select(Contract).where(Contract.id==contract_id,Contract.organization_id==user.organization_id))
    if not contract: raise HTTPException(404,"Contrato não encontrado")
    values=payload.model_dump(); values["ip_address"]=values["ip_address"] or (request.client.host if request.client else None);values["user_agent"]=values["user_agent"] or request.headers.get("user-agent")
    item=accept_checkout(db,user,contract,**values);audit(db,user,"contract.checkout_acceptance","transaction_acceptance",item.id,{"hash":item.evidence_hash});db.commit();db.refresh(item);return item


@router.get("/transaction-acceptances", response_model=list[TransactionAcceptanceView])
def transaction_acceptances(user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    return list(db.scalars(select(TransactionAcceptance).where(TransactionAcceptance.organization_id==user.organization_id).order_by(TransactionAcceptance.accepted_at.desc())))


@router.post("/contracts/{contract_id}/transfer-verification", response_model=QuotaTransferVerificationView, status_code=201)
def transfer_verification_open(contract_id: str, payload: TransferWindowCreate, user: User=Depends(require_scope("payments:review")), db: Session=Depends(get_db)):
    contract=db.scalar(select(Contract).where(Contract.id==contract_id,Contract.organization_id==user.organization_id))
    if not contract: raise HTTPException(404,"Contrato não encontrado")
    item=open_window(db,user,contract,payload.administrator_reference,payload.quota_id);audit(db,user,"quota.audit_window_opened","quota_transfer_verification",item.id,{"deadline":item.audit_deadline_at.isoformat()});db.commit();db.refresh(item);return item


@router.get("/transfer-verifications", response_model=list[QuotaTransferVerificationView])
def transfer_verifications(user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    return list(db.scalars(select(QuotaTransferVerification).where(QuotaTransferVerification.organization_id==user.organization_id).order_by(QuotaTransferVerification.created_at.desc())))


@router.post("/transfer-verifications/{verification_id}/confirm-release", response_model=TransactionAcceptanceView, status_code=201)
def transfer_verification_confirm(verification_id: str, payload: TransferReleaseCreate, request: Request, user: User=Depends(require_step_up), db: Session=Depends(get_db)):
    item=db.scalar(select(QuotaTransferVerification).where(QuotaTransferVerification.id==verification_id,QuotaTransferVerification.organization_id==user.organization_id))
    if not item: raise HTTPException(404,"Verificação não encontrada")
    values=payload.model_dump();values["ip_address"]=values["ip_address"] or (request.client.host if request.client else None);values["user_agent"]=values["user_agent"] or request.headers.get("user-agent")
    try: acceptance=confirm_release(db,user,item,**values)
    except HTTPException as exc:
        if item.status=="EXPIRED_REVIEW": audit(db,user,"quota.audit_window_expired","quota_transfer_verification",item.id);db.commit()
        raise exc
    audit(db,user,"quota.transfer_release_accepted","transaction_acceptance",acceptance.id,{"hash":acceptance.evidence_hash});db.commit();db.refresh(acceptance);return acceptance


@router.post("/transfer-verifications/{verification_id}/dispute", response_model=QuotaTransferVerificationView)
def transfer_verification_dispute(verification_id: str, payload: TransferDisputeCreate, user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    item=db.scalar(select(QuotaTransferVerification).where(QuotaTransferVerification.id==verification_id,QuotaTransferVerification.organization_id==user.organization_id))
    if not item: raise HTTPException(404,"Verificação não encontrada")
    dispute(db,item,payload.reason);audit(db,user,"quota.transfer_disputed","quota_transfer_verification",item.id);db.commit();db.refresh(item);return item


@router.get("/transfer-verifications/{verification_id}/release-readiness")
def transfer_release_readiness(verification_id: str, user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    item=db.scalar(select(QuotaTransferVerification).where(QuotaTransferVerification.id==verification_id,QuotaTransferVerification.organization_id==user.organization_id))
    if not item: raise HTTPException(404,"Verificação não encontrada")
    return {"verification_id":item.id,"status":item.status,"payout_unlocked":item.payout_unlocked,"automatic_release_on_silence":False,"requires_manual_review":item.status in {"EXPIRED_REVIEW","DISPUTED"}}


@router.post("/contracts/{contract_id}/seller-evidence-audit",response_model=SellerEvidenceAuditView,status_code=201)
def seller_evidence_create(contract_id:str,payload:SellerEvidenceAuditCreate,user:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    contract=db.scalar(select(Contract).where(Contract.id==contract_id,Contract.organization_id==user.organization_id))
    if not contract:raise HTTPException(404,"Contrato não encontrado")
    item=cross_validate_seller_evidence(db,user,contract,**payload.model_dump());audit(db,user,"seller_evidence.ocr_cross_validated","seller_evidence_audit",item.id,{"status":item.status,"hash":item.evidence_hash});db.commit();db.refresh(item);return item


@router.get("/seller-evidence-audits",response_model=list[SellerEvidenceAuditView])
def seller_evidence_list(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(SellerEvidenceAudit).where(SellerEvidenceAudit.organization_id==user.organization_id).order_by(SellerEvidenceAudit.created_at.desc())))


@router.post("/seller-evidence-audits/{audit_id}/review",response_model=SellerEvidenceAuditView)
def seller_evidence_review(audit_id:str,payload:SellerEvidenceReview,user:User=Depends(require_step_up),_:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    item=db.scalar(select(SellerEvidenceAudit).where(SellerEvidenceAudit.id==audit_id,SellerEvidenceAudit.organization_id==user.organization_id))
    if not item:raise HTTPException(404,"Auditoria não encontrada")
    review_seller_audit(user,item,payload.decision,payload.notes);audit(db,user,"seller_evidence.reviewed","seller_evidence_audit",item.id,{"decision":payload.decision});db.commit();db.refresh(item);return item


@router.post("/structured-properties",response_model=StructuredPropertyView,status_code=201)
def structured_property_create(payload:StructuredPropertyCreate,user:User=Depends(require_scope("proposals:write")),db:Session=Depends(get_db)):
    item=create_property_case(db,user,**payload.model_dump());audit(db,user,"structured_property.created","structured_property",item.id,{"route":item.route,"hash":item.evidence_hash});db.commit();db.refresh(item);return item


@router.get("/structured-properties",response_model=list[StructuredPropertyView])
def structured_property_list(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(StructuredPropertyCase).where(StructuredPropertyCase.organization_id==user.organization_id).order_by(StructuredPropertyCase.created_at.desc())))


@router.get("/structured-properties/events",response_model=list[StructuredPropertyEventView])
def structured_property_events(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(StructuredPropertyEvent).where(StructuredPropertyEvent.organization_id==user.organization_id).order_by(StructuredPropertyEvent.occurred_at.desc())))


def property_case(db:Session,user:User,case_id:str)->StructuredPropertyCase:
    item=db.scalar(select(StructuredPropertyCase).where(StructuredPropertyCase.id==case_id,StructuredPropertyCase.organization_id==user.organization_id))
    if not item:raise HTTPException(404,"Caso de imóvel estruturado não encontrado")
    return item


@router.post("/structured-properties/{case_id}/iq-document",response_model=StructuredPropertyView)
def structured_property_iq_document(case_id:str,payload:PropertyDocumentAttach,user:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    item=property_case(db,user,case_id);attach_iq_document(db,user,item,payload.document_id);audit(db,user,"structured_property.iq_document","structured_property",item.id);db.commit();db.refresh(item);return item


@router.post("/structured-properties/{case_id}/iq-approve",response_model=StructuredPropertyView)
def structured_property_iq_approve(case_id:str,user:User=Depends(require_step_up),_:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    item=property_case(db,user,case_id);approve_iq(db,user,item);audit(db,user,"structured_property.iq_approved","structured_property",item.id);db.commit();db.refresh(item);return item


@router.post("/structured-properties/{case_id}/phase-1-release",response_model=StructuredPropertyView)
def structured_property_phase1(case_id:str,user:User=Depends(require_step_up),_:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    item=property_case(db,user,case_id);release_phase1(db,user,item);audit(db,user,"structured_property.phase1_sandbox","structured_property",item.id,{"real_transfer":False});db.commit();db.refresh(item);return item


@router.post("/structured-properties/{case_id}/registration",response_model=StructuredPropertyView)
def structured_property_registration(case_id:str,payload:PropertyDocumentAttach,user:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    item=property_case(db,user,case_id);submit_registration(db,user,item,payload.document_id);audit(db,user,"structured_property.registration_submitted","structured_property",item.id);db.commit();db.refresh(item);return item


@router.post("/structured-properties/{case_id}/registration-approve",response_model=StructuredPropertyView)
def structured_property_registration_approve(case_id:str,user:User=Depends(require_step_up),_:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    item=property_case(db,user,case_id);approve_registration(db,user,item);audit(db,user,"structured_property.phase2_sandbox_ready","structured_property",item.id,{"automatic_payout":False});db.commit();db.refresh(item);return item


@router.post("/structured-properties/{case_id}/evaluate-expiry",response_model=StructuredPropertyView)
def structured_property_expiry(case_id:str,user:User=Depends(require_scope("payments:review")),db:Session=Depends(get_db)):
    item=property_case(db,user,case_id);evaluate_expiry(db,user,item);audit(db,user,"structured_property.expiry_evaluated","structured_property",item.id);db.commit();db.refresh(item);return item


@router.get("/structured-properties/{case_id}/registry-requirement.pdf")
def structured_property_pdf(case_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    item=property_case(db,user,case_id);return Response(content=property_requirement_pdf(item),media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="{item.case_reference}-requerimento.pdf"'})


@router.get("/contracts/{contract_id}/pdf")
def download_contract_pdf(contract_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contract = db.scalar(select(Contract).where(Contract.id == contract_id, Contract.organization_id == user.organization_id))
    if not contract: raise HTTPException(status_code=404, detail="Contrato não encontrado")
    proposal = db.get(Proposal, contract.proposal_id); calculation = db.get(CalculationMemory, contract.calculation_memory_id)
    data = contract_pdf(contract, proposal, calculation)
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition":f'attachment; filename="{contract.contract_number}.pdf"'})


@router.post("/documents", response_model=DocumentView, status_code=201)
async def upload_document(
    entity_type: str = Form(...), entity_id: str = Form(...), kind: str = Form(...),
    file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    document = await persist_upload(file, user, entity_type, entity_id, kind)
    db.add(document); db.flush(); audit(db,user,"document.uploaded","document",document.id,{"sha256":document.sha256,"status":"QUARANTINED"}); db.commit(); db.refresh(document)
    return document


@router.get("/documents", response_model=list[DocumentView])
def list_documents(entity_type: str | None = None, entity_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query=select(Document).where(Document.organization_id==user.organization_id)
    if entity_type: query=query.where(Document.entity_type==entity_type)
    if entity_id: query=query.where(Document.entity_id==entity_id)
    return list(db.scalars(query.order_by(Document.created_at.desc())))


@router.post("/documents/{document_id}/mock-scan", response_model=DocumentView)
def mock_scan_document(document_id: str, user: User = Depends(require_scope("documents:write")), db: Session = Depends(get_db)):
    document=db.scalar(select(Document).where(Document.id==document_id,Document.organization_id==user.organization_id))
    if not document: raise HTTPException(status_code=404,detail="Documento não encontrado")
    document.status="CLEAN";audit(db,user,"document.scan_completed","document",document.id,{"engine":"MOCK"});db.commit();db.refresh(document);return document


@router.post("/contracts/{contract_id}/signature", response_model=SignatureView, status_code=201)
def create_signature(contract_id: str, payload: SignatureCreate, user: User = Depends(require_scope("documents:write")), db: Session = Depends(get_db)):
    from app.zapsign_signature_service import create_mock_envelope, create_zapsign_envelope, envelope_to_view, zapsign_configured

    contract=db.scalar(select(Contract).where(Contract.id==contract_id,Contract.organization_id==user.organization_id))
    if not contract: raise HTTPException(status_code=404,detail="Contrato não encontrado")
    if db.scalar(select(SignatureEnvelope).where(SignatureEnvelope.contract_id==contract.id)): raise HTTPException(status_code=409,detail="Envelope já criado")
    envelope = create_zapsign_envelope(db, user, contract, payload) if zapsign_configured() else create_mock_envelope(db, user, contract, payload)
    db.flush();audit(db,user,"signature.sent","signature_envelope",envelope.id,{"provider":envelope.provider});db.commit();db.refresh(envelope)
    return SignatureView(**envelope_to_view(envelope))


@router.get("/signatures/zapsign/status", response_model=SignatureZapSignStatusView)
def signature_zapsign_status(user: User = Depends(require_scope("documents:write"))):
    from app.zapsign_signature_service import zapsign_status

    _ = user
    return zapsign_status()


@router.post("/signatures/{envelope_id}/refresh", response_model=SignatureView)
def refresh_signature(envelope_id: str, user: User = Depends(require_scope("documents:write")), db: Session = Depends(get_db)):
    from app.zapsign_signature_service import envelope_to_view, refresh_zapsign_envelope

    envelope=db.scalar(select(SignatureEnvelope).where(SignatureEnvelope.id==envelope_id,SignatureEnvelope.organization_id==user.organization_id))
    if not envelope: raise HTTPException(status_code=404,detail="Envelope não encontrado")
    envelope = refresh_zapsign_envelope(db, envelope)
    audit(db,user,"signature.refreshed","signature_envelope",envelope.id,{"status":envelope.status});db.commit();db.refresh(envelope)
    return SignatureView(**envelope_to_view(envelope))


@router.post("/signatures/{envelope_id}/mock-complete", response_model=SignatureView)
def complete_signature(envelope_id: str, payload: SignatureComplete, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.zapsign_signature_service import envelope_to_view

    envelope=db.scalar(select(SignatureEnvelope).where(SignatureEnvelope.id==envelope_id,SignatureEnvelope.organization_id==user.organization_id))
    if not envelope: raise HTTPException(status_code=404,detail="Envelope não encontrado")
    if envelope.provider != "MOCK": raise HTTPException(status_code=409,detail="Conclusão simulada disponível apenas para envelopes MOCK.")
    if not payload.confirmation: raise HTTPException(status_code=422,detail="Confirmação obrigatória")
    if envelope.status!="SENT": raise HTTPException(status_code=409,detail="Envelope não está pendente")
    envelope.status="SIGNED";envelope.signed_at=datetime.now(UTC);envelope.evidence_json=json.dumps(payload.model_dump())
    contract=db.get(Contract,envelope.contract_id);contract.status="SIGNED"
    audit(db,user,"signature.completed","signature_envelope",envelope.id,payload.model_dump());db.commit();db.refresh(envelope)
    return SignatureView(**envelope_to_view(envelope))


@router.post("/ledger/transactions", response_model=LedgerTransactionView, status_code=201)
def post_ledger(payload: LedgerPostRequest, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    transaction = post_double_entry(db, user, **payload.model_dump()); db.flush(); audit(db, user, "ledger.posted", "ledger_transaction", transaction.id); db.commit(); db.refresh(transaction)
    entries = list(db.scalars(select(LedgerEntry).where(LedgerEntry.transaction_id == transaction.id)))
    debit = next(x for x in entries if x.direction == "DEBIT"); credit = next(x for x in entries if x.direction == "CREDIT")
    return LedgerTransactionView(id=transaction.id, reference=transaction.reference, event_type=transaction.event_type, description=transaction.description, amount=Decimal(str(debit.amount)), debit_account=debit.account, credit_account=credit.account, created_at=transaction.created_at)


@router.get("/ledger/transactions", response_model=list[LedgerTransactionView])
def list_ledger(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    txs = list(db.scalars(select(LedgerTransaction).where(LedgerTransaction.organization_id == user.organization_id).order_by(LedgerTransaction.created_at.desc())))
    result = []
    for transaction in txs:
        entries = list(db.scalars(select(LedgerEntry).where(LedgerEntry.transaction_id == transaction.id)))
        debit = next(x for x in entries if x.direction == "DEBIT"); credit = next(x for x in entries if x.direction == "CREDIT")
        result.append(LedgerTransactionView(id=transaction.id, reference=transaction.reference, event_type=transaction.event_type, description=transaction.description, amount=Decimal(str(debit.amount)), debit_account=debit.account, credit_account=credit.account, created_at=transaction.created_at))
    return result


@router.get("/ledger/balances", response_model=list[AccountBalanceView])
def balances(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result=account_balances(db,user);db.commit();return result


@router.post("/escrow/accounts", response_model=EscrowView, status_code=201)
def create_escrow(payload: EscrowCreate, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    account = create_mock_escrow(
        db,
        user,
        payload.operation_id,
        create_subaccount=payload.create_subaccount,
        enable_escrow=payload.enable_escrow,
        profile=payload.profile,
    )
    db.flush()
    audit(
        db,
        user,
        "escrow.created",
        "escrow_account",
        account.id,
        {
            "provider": account.provider,
            "subaccount": payload.create_subaccount,
            "escrow_enabled": account.escrow_enabled,
        },
    )
    db.commit()
    db.refresh(account)
    return account


@router.post("/escrow/subaccount/preview", response_model=EscrowSubaccountPreviewView)
def escrow_subaccount_preview(payload: EscrowCreate, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    from app.asaas_subaccount_service import subaccount_profile_preview

    return subaccount_profile_preview(db, user, payload.operation_id, payload.profile)


@router.get("/escrow/asaas/status", response_model=EscrowAsaasStatusView)
def escrow_asaas_status(user: User = Depends(require_scope("payments:review"))):
    from app.asaas_escrow_service import asaas_status

    _ = user
    return asaas_status()


@router.get("/escrow/accounts", response_model=list[EscrowView])
def list_escrow(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(EscrowAccount).where(EscrowAccount.organization_id==user.organization_id).order_by(EscrowAccount.created_at.desc())))


@router.post("/escrow/accounts/{account_id}/mock-webhook")
def escrow_webhook(account_id: str, payload: EscrowWebhook, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    account=db.scalar(select(EscrowAccount).where(EscrowAccount.id==account_id,EscrowAccount.organization_id==user.organization_id))
    if not account: raise HTTPException(status_code=404,detail="Conta escrow não encontrada")
    event,processed=process_escrow_event(db,user,account,payload.event_id,payload.event_type,payload.amount,payload.metadata)
    if processed: audit(db,user,"escrow.webhook_processed","escrow_event",event.id,{"event_id":payload.event_id})
    db.commit();return {"event_id":event.provider_event_id,"processed":processed,"status":"ok"}


def payout_view(db: Session, item: PayoutRequest) -> PayoutView:
    count=db.scalar(select(__import__('sqlalchemy').func.count()).select_from(PayoutApproval).where(PayoutApproval.payout_request_id==item.id,PayoutApproval.decision=="APPROVE")) or 0
    return PayoutView.model_validate(item,from_attributes=True).model_copy(update={"approval_count":count})


@router.post("/payouts", response_model=PayoutView, status_code=201)
def request_payout(payload: PayoutCreate, user: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    account=db.scalar(select(EscrowAccount).where(EscrowAccount.id==payload.escrow_account_id,EscrowAccount.organization_id==user.organization_id))
    if not account: raise HTTPException(status_code=404,detail="Conta escrow não encontrada")
    verification=None
    if payload.transfer_verification_id:
        verification=db.scalar(select(QuotaTransferVerification).where(QuotaTransferVerification.id==payload.transfer_verification_id,QuotaTransferVerification.organization_id==user.organization_id))
        if not verification: raise HTTPException(status_code=404,detail="Verificação de transferência não encontrada")
        if verification.status!="BUYER_CONFIRMED" or not verification.payout_unlocked: raise HTTPException(status_code=409,detail="Payout da carta permanece bloqueado até o segundo aceite")
    item=create_payout(db,user,account,beneficiary_name=payload.beneficiary_name,beneficiary_document=payload.beneficiary_document,pix_key=payload.pix_key,amount=payload.amount,condition_evidence=payload.condition_evidence)
    item.transfer_verification_id=verification.id if verification else None
    db.flush();audit(db,user,"payout.requested","payout",item.id);db.commit();db.refresh(item);return payout_view(db,item)


@router.get("/payouts", response_model=list[PayoutView])
def list_payouts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [payout_view(db,x) for x in db.scalars(select(PayoutRequest).where(PayoutRequest.organization_id==user.organization_id).order_by(PayoutRequest.created_at.desc()))]


@router.post("/payouts/{payout_id}/approve", response_model=PayoutView)
def approve_payout_route(payout_id: str, payload: PayoutApprove, user: User = Depends(require_step_up), _: User = Depends(require_scope("payments:review")), db: Session = Depends(get_db)):
    item=db.scalar(select(PayoutRequest).where(PayoutRequest.id==payout_id,PayoutRequest.organization_id==user.organization_id))
    if not item: raise HTTPException(status_code=404,detail="Payout não encontrado")
    item=approve_payout(db,user,item,payload.decision,payload.comment);audit(db,user,f"payout.{payload.decision.lower()}","payout",item.id);db.commit();db.refresh(item);return payout_view(db,item)


@router.post("/payments/payout")
def payout(_: User = Depends(require_scope("payments:review"))):
    financial_guard()
    return {"status": "accepted"}


@router.post("/recovered-assets", response_model=RecoveredAssetView, status_code=201)
def recovered_asset_create(payload: RecoveredAssetCreate, user: User = Depends(require_scope("admin:users")), db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"gated_details"})
    data["gated_details_json"] = json.dumps(payload.gated_details, ensure_ascii=False)
    item = create_asset(db, user, **data)
    db.flush(); audit(db,user,"auction.asset_created","recovered_asset",item.id); db.commit(); db.refresh(item); return item


@router.get("/recovered-assets", response_model=list[RecoveredAssetView])
def recovered_assets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(RecoveredAsset).where(RecoveredAsset.organization_id==user.organization_id).order_by(RecoveredAsset.created_at.desc())))


@router.post("/auction-lots", response_model=AuctionLotView, status_code=201)
def auction_lot_create(payload: AuctionLotCreate, user: User = Depends(require_scope("admin:users")), db: Session = Depends(get_db)):
    asset=db.scalar(select(RecoveredAsset).where(RecoveredAsset.id==payload.asset_id,RecoveredAsset.organization_id==user.organization_id))
    if not asset: raise HTTPException(status_code=404,detail="Ativo recuperado não encontrado")
    item=create_lot(db,user,asset,**payload.model_dump(exclude={"asset_id"}))
    db.flush();audit(db,user,"auction.lot_created","auction_lot",item.id);db.commit();db.refresh(item);return item


@router.get("/auction-lots", response_model=list[AuctionLotView])
def auction_lots(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(AuctionLot).where(AuctionLot.organization_id==user.organization_id).order_by(AuctionLot.created_at.desc())))


@router.post("/auction-lots/{lot_id}/activate", response_model=AuctionLotView)
def auction_lot_activate(lot_id:str,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    lot=db.scalar(select(AuctionLot).where(AuctionLot.id==lot_id,AuctionLot.organization_id==user.organization_id))
    if not lot: raise HTTPException(status_code=404,detail="Lote não encontrado")
    activate_lot(lot);audit(db,user,"auction.lot_activated","auction_lot",lot.id);db.commit();db.refresh(lot);return lot


@router.post("/auction-lots/{lot_id}/qualify", response_model=AuctionQualificationView, status_code=201)
def auction_qualify(lot_id:str,payload:AuctionQualificationRequest,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    lot=db.scalar(select(AuctionLot).where(AuctionLot.id==lot_id,AuctionLot.organization_id==user.organization_id))
    if not lot: raise HTTPException(status_code=404,detail="Lote não encontrado")
    item=qualify(db,user,lot,payload.confirmation);db.flush();audit(db,user,"auction.qualified","auction_qualification",item.id);db.commit();db.refresh(item);return item


@router.get("/auction-lots/{lot_id}/gated-details")
def auction_gated_details(lot_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    lot=db.scalar(select(AuctionLot).where(AuctionLot.id==lot_id,AuctionLot.organization_id==user.organization_id))
    if not lot: raise HTTPException(status_code=404,detail="Lote não encontrado")
    return gated_asset_details(db,user,lot)


@router.post("/auction-lots/{lot_id}/bids", response_model=AuctionBidView, status_code=201)
def auction_bid_create(lot_id:str,payload:AuctionBidCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    lot=db.scalar(select(AuctionLot).where(AuctionLot.id==lot_id,AuctionLot.organization_id==user.organization_id))
    if not lot: raise HTTPException(status_code=404,detail="Lote não encontrado")
    item,created=place_bid(db,user,lot,payload.amount,payload.idempotency_key)
    if created: db.flush();audit(db,user,"auction.bid_placed","auction_bid",item.id,{"amount":str(payload.amount)})
    db.commit();db.refresh(item);return item


@router.get("/auction-lots/{lot_id}/bids", response_model=list[AuctionBidView])
def auction_bids(lot_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    lot=db.scalar(select(AuctionLot).where(AuctionLot.id==lot_id,AuctionLot.organization_id==user.organization_id))
    if not lot: raise HTTPException(status_code=404,detail="Lote não encontrado")
    return list(db.scalars(select(AuctionBid).where(AuctionBid.lot_id==lot.id).order_by(AuctionBid.amount.desc(),AuctionBid.placed_at)))


@router.post("/auction-lots/{lot_id}/mock-settle", response_model=AuctionSettlementView)
def auction_mock_settle(lot_id:str,user:User=Depends(require_step_up),_:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    lot=db.scalar(select(AuctionLot).where(AuctionLot.id==lot_id,AuctionLot.organization_id==user.organization_id))
    if not lot: raise HTTPException(status_code=404,detail="Lote não encontrado")
    item=settle_lot(db,user,lot);db.flush();audit(db,user,"auction.settled","auction_settlement",item.id);db.commit();db.refresh(item);return item


@router.get("/auction-settlements", response_model=list[AuctionSettlementView])
def auction_settlements(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(AuctionSettlement).where(AuctionSettlement.organization_id==user.organization_id).order_by(AuctionSettlement.created_at.desc())))


@router.post("/tax/documents",response_model=TaxDocumentView,status_code=201)
def tax_document_create(payload:TaxDocumentCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    target=db.scalar(select(User).where(User.id==payload.user_id,User.organization_id==user.organization_id))
    if not target: raise HTTPException(status_code=404,detail="Usuário não encontrado")
    item=issue_tax_document(db,user,target,payload.reference_month,payload.gross_amount,payload.tax_amount,payload.content);db.flush();audit(db,user,"tax.document_issued","tax_document",item.id);db.commit();db.refresh(item);return item

@router.get("/tax/documents",response_model=list[TaxDocumentView])
def tax_documents(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(TaxDocument).where(TaxDocument.organization_id==user.organization_id).order_by(TaxDocument.created_at.desc())))

@router.post("/tax/closings",response_model=TaxClosingView,status_code=201)
def tax_closing_create(payload:TaxClosingRequest,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=close_tax_month(db,user,payload.reference_month);db.flush();audit(db,user,"tax.month_closed","tax_closing",item.id);db.commit();db.refresh(item);return item

@router.get("/tax/closings",response_model=list[TaxClosingView])
def tax_closings(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(TaxClosing).where(TaxClosing.organization_id==user.organization_id).order_by(TaxClosing.reference_month.desc())))

@router.get("/tax/exceptions",response_model=list[TaxExceptionView])
def tax_exceptions(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(TaxException).where(TaxException.organization_id==user.organization_id).order_by(TaxException.created_at.desc())))

@router.post("/tax/exceptions/{exception_id}/resolve",response_model=TaxExceptionView)
def tax_exception_resolve(exception_id:str,payload:TaxExceptionResolve,user:User=Depends(require_step_up),_:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(TaxException).where(TaxException.id==exception_id,TaxException.organization_id==user.organization_id))
    if not item: raise HTTPException(status_code=404,detail="Exceção fiscal não encontrada")
    resolve_tax_exception(item,user,payload.note);audit(db,user,"tax.exception_resolved","tax_exception",item.id);db.commit();db.refresh(item);return item

@router.post("/communications/templates",response_model=CommunicationTemplateView,status_code=201)
def communication_template_create(payload:CommunicationTemplateCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    if payload.channel not in {"WHATSAPP","EMAIL","IN_APP"}: raise HTTPException(status_code=422,detail="Canal inválido")
    if payload.purpose not in {"TRANSACTIONAL","MARKETING"}: raise HTTPException(status_code=422,detail="Finalidade inválida")
    item=create_template(db,user,**payload.model_dump());db.flush();audit(db,user,"communication.template_created","communication_template",item.id);db.commit();db.refresh(item);return item

@router.get("/communications/templates",response_model=list[CommunicationTemplateView])
def communication_templates(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(CommunicationTemplate).where(CommunicationTemplate.organization_id==user.organization_id).order_by(CommunicationTemplate.created_at.desc())))

@router.post("/communications/consents",response_model=CommunicationConsentView)
def communication_consent(payload:CommunicationConsentRequest,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if payload.status not in {"OPT_IN","OPT_OUT"}: raise HTTPException(status_code=422,detail="Status de consentimento inválido")
    item=update_consent(db,user,**payload.model_dump());db.flush();audit(db,user,"communication.consent_changed","communication_consent",item.id,{"status":payload.status});db.commit();db.refresh(item);return item

@router.get("/communications/consents",response_model=list[CommunicationConsentView])
def communication_consents(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(CommunicationConsent).where(CommunicationConsent.organization_id==user.organization_id).order_by(CommunicationConsent.changed_at.desc())))

@router.post("/communications/send",response_model=CommunicationDeliveryView,status_code=201)
def communication_send(payload:CommunicationSendRequest,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    template=db.scalar(select(CommunicationTemplate).where(CommunicationTemplate.id==payload.template_id,CommunicationTemplate.organization_id==user.organization_id,CommunicationTemplate.active.is_(True)))
    if not template: raise HTTPException(status_code=404,detail="Template ativo não encontrado")
    item,created=queue_delivery(db,user,template,payload.subject_type,payload.subject_id,payload.destination,payload.idempotency_key,payload.variables)
    if created: db.flush();audit(db,user,"communication.queued","communication_delivery",item.id)
    db.commit();db.refresh(item);return item

@router.post("/communications/deliveries/{delivery_id}/mock-deliver",response_model=CommunicationDeliveryView)
def communication_mock_deliver(delivery_id:str,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(CommunicationDelivery).where(CommunicationDelivery.id==delivery_id,CommunicationDelivery.organization_id==user.organization_id))
    if not item: raise HTTPException(status_code=404,detail="Entrega não encontrada")
    mock_deliver(item);audit(db,user,"communication.delivered","communication_delivery",item.id);db.commit();db.refresh(item);return item

@router.get("/communications/deliveries",response_model=list[CommunicationDeliveryView])
def communication_deliveries(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(CommunicationDelivery).where(CommunicationDelivery.organization_id==user.organization_id).order_by(CommunicationDelivery.created_at.desc())))


@router.post("/nina/policies",response_model=UnderwritingPolicyView,status_code=201)
def nina_policy_create(payload:UnderwritingPolicyCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=create_policy(db,user,payload.product,**payload.model_dump(exclude={"product"}));db.flush();audit(db,user,"nina.policy_created","underwriting_policy",item.id);db.commit();db.refresh(item);return item

@router.get("/nina/policies",response_model=list[UnderwritingPolicyView])
def nina_policies(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return list(db.scalars(select(UnderwritingPolicy).where(UnderwritingPolicy.organization_id==user.organization_id).order_by(UnderwritingPolicy.created_at.desc())))

def assessment_view(item:UnderwritingAssessment)->UnderwritingAssessmentView:
    return UnderwritingAssessmentView.model_validate(item).model_copy(update={"explanation":json.loads(item.explanation_json)})

@router.post("/nina/proposals/{proposal_id}/assess",response_model=UnderwritingAssessmentView,status_code=201)
def nina_assess(proposal_id:str,payload:UnderwritingAssessmentCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    proposal=db.scalar(select(Proposal).where(Proposal.id==proposal_id,Proposal.organization_id==user.organization_id));policy=db.scalar(select(UnderwritingPolicy).where(UnderwritingPolicy.id==payload.policy_id,UnderwritingPolicy.organization_id==user.organization_id,UnderwritingPolicy.active.is_(True)))
    if not proposal or not policy: raise HTTPException(status_code=404,detail="Proposta ou política ativa não encontrada")
    inputs=payload.model_dump(exclude={"policy_id"},mode="json");item=assess(db,user,proposal,policy,inputs);db.flush();audit(db,user,"nina.assessed","underwriting_assessment",item.id,{"score":item.score});db.commit();db.refresh(item);return assessment_view(item)

@router.get("/nina/assessments",response_model=list[UnderwritingAssessmentView])
def nina_assessments(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return [assessment_view(x) for x in db.scalars(select(UnderwritingAssessment).where(UnderwritingAssessment.organization_id==user.organization_id).order_by(UnderwritingAssessment.created_at.desc()))]

@router.post("/nina/assessments/{assessment_id}/decide",response_model=UnderwritingDecisionView)
def nina_decide(assessment_id:str,payload:UnderwritingDecisionCreate,user:User=Depends(require_step_up),_:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    if payload.decision not in {"APPROVE","REJECT"}: raise HTTPException(status_code=422,detail="Decisão inválida")
    assessment=db.scalar(select(UnderwritingAssessment).where(UnderwritingAssessment.id==assessment_id,UnderwritingAssessment.organization_id==user.organization_id))
    if not assessment: raise HTTPException(status_code=404,detail="Avaliação não encontrada")
    item=decide(db,user,assessment,payload.decision,payload.reason);db.flush();audit(db,user,"nina.decision","underwriting_decision",item.id,{"decision":payload.decision});db.commit();db.refresh(item);return item

@router.get("/nina/quota-ranking",response_model=list[QuotaRankingView])
def nina_quota_ranking(target_amount:Decimal=Query(gt=0),category:str="REAL_ESTATE",limit:int=Query(default=10,ge=1,le=50),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return rank_quota_combinations(db,user,target_amount,category,limit)

@router.get("/bi/summary",response_model=BISummaryView)
def business_intelligence_summary(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return bi_summary(db,user)

@router.get("/bi/executive-report.csv")
def business_intelligence_csv(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    summary=bi_summary(db,user);lines=["section,metric,value"]
    for section,metrics in summary.items():
        for metric,value in metrics.items():lines.append(f"{section},{metric},{value}")
    data=("\ufeff"+"\n".join(lines)).encode("utf-8")
    return Response(content=data,media_type="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=letter-executive-report.csv"})

@router.get("/system/readiness")
def readiness(db:Session=Depends(get_db)): return system_readiness(db)

@router.post("/system/jobs",response_model=OperationalJobView,status_code=201)
def job_create(payload:OperationalJobCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    check_job_quota(db,user)
    item,created=enqueue_job(db,user,**payload.model_dump())
    if created: db.flush();audit(db,user,"system.job_enqueued","operational_job",item.id,{"job_type":item.job_type})
    db.commit();db.refresh(item);return item

@router.get("/system/jobs",response_model=list[OperationalJobView])
def jobs(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return list(db.scalars(select(OperationalJob).where(OperationalJob.organization_id==user.organization_id).order_by(OperationalJob.created_at.desc())))

@router.post("/system/jobs/{job_id}/process",response_model=OperationalJobView)
def job_process(job_id:str,payload:JobProcessRequest,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(OperationalJob).where(OperationalJob.id==job_id,OperationalJob.organization_id==user.organization_id))
    if not item: raise HTTPException(status_code=404,detail="Job não encontrado")
    process_job(item,payload.simulate_failure);audit(db,user,"system.job_processed","operational_job",item.id,{"status":item.status,"attempts":item.attempts});db.commit();db.refresh(item);return item

@router.get("/system/metrics")
def metrics(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)): return operational_metrics(db,user)

@router.get("/system/homologation")
def homologation(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)): return homologation_status(db,user.organization_id)

@router.get("/system/quota",response_model=TenantQuotaView)
def tenant_quota(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=get_or_create_quota(db,user);db.commit();db.refresh(item);return item

@router.patch("/system/quota",response_model=TenantQuotaView)
def tenant_quota_update(payload:TenantQuotaUpdate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=get_or_create_quota(db,user)
    for key,value in payload.model_dump(exclude_unset=True).items():setattr(item,key,value)
    audit(db,user,"security.quota_updated","tenant_quota",item.id,payload.model_dump(exclude_unset=True));db.commit();db.refresh(item);return item

@router.get("/system/security-events",response_model=list[SecurityEventView])
def security_events(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return list(db.scalars(select(SecurityEvent).where(or_(SecurityEvent.organization_id==user.organization_id,SecurityEvent.organization_id.is_(None))).order_by(SecurityEvent.created_at.desc()).limit(200)))


@router.post("/system/integrations",response_model=ProviderIntegrationView,status_code=201)
def integration_create(payload:ProviderIntegrationCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=configure_integration(db,user,**payload.model_dump());db.flush();audit(db,user,"integration.configured","provider_integration",item.id,{"provider":item.provider,"environment":item.environment});db.commit();db.refresh(item);return integration_view(item)


def integration_view(item:ProviderIntegration)->ProviderIntegrationView:
    uptime=round((item.successful_checks/item.total_checks*100) if item.total_checks else 0,2)
    return ProviderIntegrationView.model_validate(item).model_copy(update={"allowed_hosts":json.loads(item.allowed_hosts_json),"uptime_percent":uptime})


@router.get("/system/integrations",response_model=list[ProviderIntegrationView])
def integrations(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return [integration_view(x) for x in db.scalars(select(ProviderIntegration).where(ProviderIntegration.organization_id==user.organization_id).order_by(ProviderIntegration.category,ProviderIntegration.provider))]


@router.post("/system/integrations/{integration_id}/probe",response_model=ProviderIntegrationView)
def integration_probe(integration_id:str,payload:IntegrationProbeRequest,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(ProviderIntegration).where(ProviderIntegration.id==integration_id,ProviderIntegration.organization_id==user.organization_id))
    if not item: raise HTTPException(status_code=404,detail="Integração não encontrada")
    probe_integration(db,item,payload.simulate_status,payload.latency_ms);audit(db,user,"integration.probed","provider_integration",item.id,{"health":item.health_status,"circuit":item.circuit_status});db.commit();db.refresh(item);return integration_view(item)


@router.post("/system/integrations/{integration_id}/rotate-credential",response_model=ProviderIntegrationView)
def integration_rotate(integration_id:str,payload:CredentialRotateRequest,user:User=Depends(require_step_up),_:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(ProviderIntegration).where(ProviderIntegration.id==integration_id,ProviderIntegration.organization_id==user.organization_id))
    if not item:raise HTTPException(status_code=404,detail="Integração não encontrada")
    rotate_credential(item,payload.credential);audit(db,user,"integration.credential_rotated","provider_integration",item.id,{"credential_version":item.credential_version});db.commit();db.refresh(item);return integration_view(item)


@router.post("/system/integrations/{integration_id}/request",response_model=ProviderRequestLogView)
def integration_request(integration_id:str,payload:ProviderRequest,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(ProviderIntegration).where(ProviderIntegration.id==integration_id,ProviderIntegration.organization_id==user.organization_id,ProviderIntegration.active.is_(True)))
    if not item:raise HTTPException(status_code=404,detail="Integração ativa não encontrada")
    log=execute_provider_request(db,item,payload.method,payload.path,payload.payload);db.flush();audit(db,user,"integration.request","provider_request_log",log.id,{"success":log.success,"response_code":log.response_code});db.commit();db.refresh(log);return log


@router.get("/system/provider-requests",response_model=list[ProviderRequestLogView])
def provider_requests(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return list(db.scalars(select(ProviderRequestLog).where(ProviderRequestLog.organization_id==user.organization_id).order_by(ProviderRequestLog.created_at.desc()).limit(200)))


@router.post("/system/secrets",response_model=SecretReferenceView,status_code=201)
def secret_create(payload:SecretCreate,user:User=Depends(require_step_up),_:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=create_secret(db,user,**payload.model_dump());db.flush();audit(db,user,"secret.configured","secret_reference",item.id,{"backend":item.backend,"version":item.version});db.commit();db.refresh(item);return item


@router.get("/system/secrets",response_model=list[SecretReferenceView])
def secrets(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return list(db.scalars(select(SecretReference).where(SecretReference.organization_id==user.organization_id,SecretReference.active.is_(True)).order_by(SecretReference.name)))


@router.put("/system/integrations/{integration_id}/mtls",response_model=MTLSConfigView)
def mtls_configure(integration_id:str,payload:MTLSConfigCreate,user:User=Depends(require_step_up),_:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    integration=db.scalar(select(ProviderIntegration).where(ProviderIntegration.id==integration_id,ProviderIntegration.organization_id==user.organization_id))
    refs={x.id:x for x in db.scalars(select(SecretReference).where(SecretReference.organization_id==user.organization_id,SecretReference.id.in_([payload.certificate_secret_id,payload.private_key_secret_id]+([payload.ca_secret_id] if payload.ca_secret_id else []))))}
    if not integration or payload.certificate_secret_id not in refs or payload.private_key_secret_id not in refs:raise HTTPException(status_code=404,detail="Integração ou segredo não encontrado")
    item=configure_mtls(db,user,integration,refs[payload.certificate_secret_id],refs[payload.private_key_secret_id],refs.get(payload.ca_secret_id),payload.verify_peer,payload.enabled);db.flush();audit(db,user,"integration.mtls_configured","integration_mtls_config",item.id,{"enabled":item.enabled});db.commit();db.refresh(item);return item


def onboarding_view(item:ProviderOnboardingProfile)->OnboardingProfileView:
    return OnboardingProfileView.model_validate(item).model_copy(update={"checklist":json.loads(item.checklist_json)})


@router.put("/system/integrations/{integration_id}/onboarding",response_model=OnboardingProfileView)
def onboarding_configure(integration_id:str,payload:OnboardingProfileCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    integration=db.scalar(select(ProviderIntegration).where(ProviderIntegration.id==integration_id,ProviderIntegration.organization_id==user.organization_id))
    if not integration:raise HTTPException(status_code=404,detail="Integração não encontrada")
    item=configure_profile(db,user,integration,**payload.model_dump());db.flush();audit(db,user,"integration.onboarding_configured","provider_onboarding_profile",item.id);db.commit();db.refresh(item);return onboarding_view(item)


@router.get("/system/onboarding-profiles",response_model=list[OnboardingProfileView])
def onboarding_profiles(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return [onboarding_view(x) for x in db.scalars(select(ProviderOnboardingProfile).where(ProviderOnboardingProfile.organization_id==user.organization_id).order_by(ProviderOnboardingProfile.created_at.desc()))]


@router.post("/system/integrations/{integration_id}/reconciliation/import",response_model=ReconciliationRunView,status_code=201)
async def provider_reconciliation_import(integration_id:str,file:UploadFile=File(...),user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    integration=db.scalar(select(ProviderIntegration).where(ProviderIntegration.id==integration_id,ProviderIntegration.organization_id==user.organization_id))
    if not integration:raise HTTPException(status_code=404,detail="Integração não encontrada")
    content=await file.read()
    if len(content)>settings.max_upload_mb*1024*1024:raise HTTPException(status_code=413,detail="Arquivo excede o limite")
    item,created=import_provider_reconciliation_csv(db,user,integration,file.filename or "reconciliation.csv",content)
    if created:db.flush();audit(db,user,"integration.reconciliation_imported","provider_reconciliation_run",item.id,{"status":item.status,"divergences":item.divergent_items})
    db.commit();db.refresh(item);return item


@router.get("/system/reconciliation-runs",response_model=list[ReconciliationRunView])
def provider_reconciliation_runs(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return list(db.scalars(select(ProviderReconciliationRun).where(ProviderReconciliationRun.organization_id==user.organization_id).order_by(ProviderReconciliationRun.created_at.desc())))


@router.get("/system/reconciliation-runs/{run_id}/items",response_model=list[ProviderReconciliationItemView])
def provider_reconciliation_items(run_id:str,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    run=db.scalar(select(ProviderReconciliationRun).where(ProviderReconciliationRun.id==run_id,ProviderReconciliationRun.organization_id==user.organization_id))
    if not run:raise HTTPException(status_code=404,detail="Conciliação não encontrada")
    return list(db.scalars(select(ProviderReconciliationItem).where(ProviderReconciliationItem.run_id==run.id).order_by(ProviderReconciliationItem.external_id)))


@router.post("/system/integrations/{integration_id}/evidence",response_model=list[HomologationEvidenceView],status_code=201)
def evidence_generate(integration_id:str,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    integration=db.scalar(select(ProviderIntegration).where(ProviderIntegration.id==integration_id,ProviderIntegration.organization_id==user.organization_id))
    if not integration:raise HTTPException(status_code=404,detail="Integração não encontrada")
    items=generate_evidence(db,user,integration);db.flush();audit(db,user,"integration.evidence_generated","homologation_evidence",integration.id,{"pass":sum(x.result=="PASS" for x in items)});db.commit();return items


@router.get("/system/homologation-evidences",response_model=list[HomologationEvidenceView])
def homologation_evidences(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return list(db.scalars(select(HomologationEvidence).where(HomologationEvidence.organization_id==user.organization_id).order_by(HomologationEvidence.executed_at.desc()).limit(500)))


@router.get("/system/adapter-catalog",response_model=list[AdapterCatalogItem])
def adapters_catalog(user:User=Depends(require_scope("admin:users"))):return adapter_catalog()


def adapter_execution_view(item:AdapterExecution)->AdapterExecutionView:
    return AdapterExecutionView.model_validate(item).model_copy(update={"output":json.loads(item.output_json)})


@router.post("/system/integrations/{integration_id}/adapter/execute",response_model=AdapterExecutionView,status_code=201)
def adapter_execute(integration_id:str,payload:AdapterExecuteRequest,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    integration=db.scalar(select(ProviderIntegration).where(ProviderIntegration.id==integration_id,ProviderIntegration.organization_id==user.organization_id,ProviderIntegration.active.is_(True)))
    if not integration:raise HTTPException(status_code=404,detail="Integração ativa não encontrada")
    item,created=execute_adapter(db,user,integration,payload.operation,payload.payload,payload.idempotency_key)
    if created:db.flush();audit(db,user,"adapter.executed","adapter_execution",item.id,{"category":item.category,"operation":item.operation,"status":item.status})
    db.commit();db.refresh(item);return adapter_execution_view(item)


@router.get("/system/adapter-executions",response_model=list[AdapterExecutionView])
def adapter_executions(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return [adapter_execution_view(x) for x in db.scalars(select(AdapterExecution).where(AdapterExecution.organization_id==user.organization_id).order_by(AdapterExecution.created_at.desc()).limit(300))]


def certification_view(item:AdapterCertificationRun)->AdapterCertificationView:
    return AdapterCertificationView.model_validate(item).model_copy(update={"report":json.loads(item.report_json)})


def go_live_decision_view(item:ProviderGoLiveDecision)->GoLiveDecisionView:
    return GoLiveDecisionView.model_validate(item).model_copy(update={"blockers":json.loads(item.blockers_json)})


@router.post("/system/integrations/{integration_id}/certify",response_model=AdapterCertificationView,status_code=201)
def adapter_certify(integration_id:str,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    integration=db.scalar(select(ProviderIntegration).where(ProviderIntegration.id==integration_id,ProviderIntegration.organization_id==user.organization_id))
    if not integration:raise HTTPException(status_code=404,detail="Integração não encontrada")
    item=certify_adapter(db,user,integration);db.flush();audit(db,user,"adapter.certified","adapter_certification",item.id,{"status":item.status,"passed":item.passed_checks});db.commit();db.refresh(item);return certification_view(item)


@router.get("/system/adapter-certifications",response_model=list[AdapterCertificationView])
def adapter_certifications(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return [certification_view(x) for x in db.scalars(select(AdapterCertificationRun).where(AdapterCertificationRun.organization_id==user.organization_id).order_by(AdapterCertificationRun.executed_at.desc()).limit(300))]


@router.put("/system/integrations/{integration_id}/go-live-approval",response_model=GoLiveApprovalView)
def go_live_approval(integration_id:str,payload:GoLiveApprovalRequest,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    integration=db.scalar(select(ProviderIntegration).where(ProviderIntegration.id==integration_id,ProviderIntegration.organization_id==user.organization_id))
    if not integration:raise HTTPException(status_code=404,detail="Integração não encontrada")
    item=decide_approval(db,user,integration,payload.area,payload.decision,payload.notes);db.flush();audit(db,user,"provider.go_live_approval","provider_integration",integration.id,{"area":item.area,"decision":item.decision});db.commit();db.refresh(item);return item


@router.get("/system/go-live-approvals",response_model=list[GoLiveApprovalView])
def go_live_approvals(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return list(db.scalars(select(ProviderGoLiveApproval).where(ProviderGoLiveApproval.organization_id==user.organization_id).order_by(ProviderGoLiveApproval.decided_at.desc())))


@router.post("/system/integrations/{integration_id}/go-live/evaluate",response_model=GoLiveDecisionView,status_code=201)
def go_live_evaluate(integration_id:str,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    integration=db.scalar(select(ProviderIntegration).where(ProviderIntegration.id==integration_id,ProviderIntegration.organization_id==user.organization_id))
    if not integration:raise HTTPException(status_code=404,detail="Integração não encontrada")
    item=evaluate_go_live(db,user,integration);db.flush();audit(db,user,"provider.go_live_evaluated","provider_go_live_decision",item.id,{"status":item.status,"blockers":json.loads(item.blockers_json)});db.commit();db.refresh(item);return go_live_decision_view(item)


@router.get("/system/go-live-decisions",response_model=list[GoLiveDecisionView])
def go_live_decisions(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return [go_live_decision_view(x) for x in db.scalars(select(ProviderGoLiveDecision).where(ProviderGoLiveDecision.organization_id==user.organization_id).order_by(ProviderGoLiveDecision.decided_at.desc()).limit(300))]


@router.get("/system/provider-incidents",response_model=list[ProviderIncidentView])
def provider_incidents(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return list(db.scalars(select(ProviderIncident).where(ProviderIncident.organization_id==user.organization_id).order_by(ProviderIncident.created_at.desc()).limit(200)))


@router.post("/system/provider-incidents/{incident_id}/action",response_model=ProviderIncidentView)
def provider_incident_action(incident_id:str,payload:IncidentActionRequest,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(ProviderIncident).where(ProviderIncident.id==incident_id,ProviderIncident.organization_id==user.organization_id))
    if not item:raise HTTPException(status_code=404,detail="Incidente não encontrado")
    now=datetime.now(UTC);action=payload.action.upper()
    if action=="ACKNOWLEDGE":item.status="ACKNOWLEDGED";item.acknowledged_by_id=user.id;item.acknowledged_at=now
    elif action=="RESOLVE":item.status="RESOLVED";item.resolved_by_id=user.id;item.resolved_at=now
    else:raise HTTPException(status_code=422,detail="Ação inválida")
    audit(db,user,"integration.incident_action","provider_incident",item.id,{"action":action});db.commit();db.refresh(item);return item


def endpoint_view(item:WebhookEndpoint)->WebhookEndpointView:
    return WebhookEndpointView.model_validate(item).model_copy(update={"subscribed_events":json.loads(item.subscribed_events_json)})


@router.post("/system/webhook-endpoints",response_model=WebhookEndpointView,status_code=201)
def webhook_endpoint_create(payload:WebhookEndpointCreate,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    integration=db.scalar(select(ProviderIntegration).where(ProviderIntegration.id==payload.integration_id,ProviderIntegration.organization_id==user.organization_id,ProviderIntegration.active.is_(True)))
    if not integration: raise HTTPException(status_code=404,detail="Integração ativa não encontrada")
    item=create_endpoint(db,user,integration,payload.name,payload.target_url,payload.secret,payload.subscribed_events,payload.max_attempts);db.flush();audit(db,user,"webhook.endpoint_created","webhook_endpoint",item.id);db.commit();db.refresh(item);return endpoint_view(item)


@router.get("/system/webhook-endpoints",response_model=list[WebhookEndpointView])
def webhook_endpoints(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return [endpoint_view(x) for x in db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.organization_id==user.organization_id).order_by(WebhookEndpoint.created_at.desc()))]


@router.post("/system/webhook-endpoints/{endpoint_id}/dispatch",response_model=WebhookDeliveryView,status_code=201)
def webhook_dispatch(endpoint_id:str,payload:WebhookDispatchRequest,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    endpoint=db.scalar(select(WebhookEndpoint).where(WebhookEndpoint.id==endpoint_id,WebhookEndpoint.organization_id==user.organization_id,WebhookEndpoint.active.is_(True)))
    if not endpoint: raise HTTPException(status_code=404,detail="Endpoint ativo não encontrado")
    integration=db.scalar(select(ProviderIntegration).where(ProviderIntegration.id==endpoint.integration_id,ProviderIntegration.organization_id==user.organization_id))
    item,created=dispatch_webhook(db,user,endpoint,integration,**payload.model_dump())
    if created:audit(db,user,"webhook.dispatched","webhook_delivery",item.id,{"event_id":item.event_id,"status":item.status})
    db.commit();db.refresh(item);return item


@router.post("/system/webhook-deliveries/{delivery_id}/retry",response_model=WebhookDeliveryView)
def webhook_retry(delivery_id:str,payload:WebhookRetryRequest,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    item=db.scalar(select(WebhookDelivery).where(WebhookDelivery.id==delivery_id,WebhookDelivery.organization_id==user.organization_id))
    if not item: raise HTTPException(status_code=404,detail="Entrega não encontrada")
    if item.status in {"DELIVERED","DEAD_LETTER"}: raise HTTPException(status_code=409,detail="Entrega não aceita nova tentativa")
    endpoint=db.get(WebhookEndpoint,item.endpoint_id);integration=db.get(ProviderIntegration,endpoint.integration_id)
    attempt_delivery(item,integration,payload.simulate_failure,db,endpoint);audit(db,user,"webhook.retried","webhook_delivery",item.id,{"status":item.status,"attempts":item.attempts});db.commit();db.refresh(item);return item


@router.get("/system/webhook-deliveries",response_model=list[WebhookDeliveryView])
def webhook_deliveries(user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    return list(db.scalars(select(WebhookDelivery).where(WebhookDelivery.organization_id==user.organization_id).order_by(WebhookDelivery.created_at.desc()).limit(200)))


@router.post("/system/webhook-deliveries/reprocess-dead-letter")
def webhook_dead_letter_bulk(payload:DeadLetterBulkRequest,user:User=Depends(require_scope("admin:users")),db:Session=Depends(get_db)):
    result=reprocess_dead_letters(db,user,payload.delivery_ids);audit(db,user,"webhook.dead_letter_requeued","webhook_delivery","bulk",result);db.commit();return result


@router.post("/system/webhooks/verify")
def webhook_verify(payload:WebhookVerifyRequest,user:User=Depends(require_scope("admin:users"))):
    return {"valid":verify_webhook(payload.secret,payload.signature,payload.payload)}
