import { fetchWithRetry } from "@/lib/fetch-with-retry";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL?.trim() || "http://localhost:8000/api/v1").replace(/\s+/g, "");

export type Module = { key: string; name: string; description: string; status: string; route: string; critical: boolean };
export type Summary = { leads: number; available_quotas: number; active_proposals: number; active_operations: number; modules: number; financial_transactions_enabled: boolean };
export type User = { id: string; name: string; email: string; role: string; organization_id: string; branch_id: string | null; active: boolean; mfa_enabled: boolean; last_login_at: string | null };
export type Branch = { id: string; name: string; code: string; region: string | null; active: boolean };
export type Invitation = { id: string; email: string; role: string; branch_id: string | null; status: string; expires_at: string; token?: string | null };
export type AuthSession = { id: string; user_agent: string | null; ip_address: string | null; active: boolean; created_at: string; expires_at: string; last_seen_at: string; step_up_until: string | null };
export type KycCase = { id: string; subject_type: string; subject_id: string; provider: string; status: string; risk_level: string | null; created_at: string; reviewed_at: string | null };
export type NetworkNode = { id:string; user_id:string; sponsor_user_id:string|null; tree_type:string; referral_code:string; status:string };
export type NetworkDownlineMember = { user_id:string; name:string; email:string; role:string; referral_code:string; level:number; sponsor_user_id:string|null; sponsor_name:string|null; status:string };
export type NetworkSummary = { tree_type:string; total_downline:number; levels:Record<string,number>; privacy_mode:string; visible_proposals?:number; pending_proposals?:number; visible_leads?:number; open_leads?:number; downline_size?:number };
export type CommissionRule = { id:string; product:string; commission_type:string; version:number; base_type:string; pool_rate_percent:string; levels_json:string; active:boolean };
export type CommissionEntry = { id:string; beneficiary_id:string; reference:string; product:string; level:number; amount:string; status:string };
export type FundingOpportunity = { id:string; title:string; product:string; capital_source:string; target_amount:string; funded_amount:string; min_investment:string; annual_return_reference:string|null; status:string; created_at:string };
export type InvestmentReservation = { id:string; opportunity_id:string; investor_id:string; amount:string; status:string; confirmed_at:string|null };
export type InvestmentPosition = { id:string; opportunity_id:string; investor_id:string; principal:string; accrued_return:string; status:string };
export type Invoice = { id:string; contract_id:string; invoice_number:string; installment_number:number; kind:string; due_date:string; principal_amount:string; interest_amount:string; fee_amount:string; total_amount:string; paid_amount:string; status:string };
export type PaymentReceipt = { id:string; contract_id:string; invoice_id:string; partner_id:string; reference_month:number; filename:string; total_paid:string; fruicao_amount:string; amortizacao_amount:string; tax_withheld:string; authenticity_hash:string; customer_route:string; vault_s3_uri:string; email_status:string; push_status:string; issued_at:string };
export type DelinquencyCase = { id:string; invoice_id:string; days_overdue:number; penalty_amount:string; late_interest_amount:string; status:string; caducity_eligible:boolean };
export type NinaDistressCase = { id:string; delinquency_case_id:string; operation_id:string|null; stage:string; days_overdue:number; fiscal_check_status:string; cash_hold_status:string; legal_notice_status:string; caducity_status:string; auction_status:string; appraisal_value_avm:string|null; opening_price_percent:string; floor_price_percent:string; daily_reduction_amount:string; current_auction_price:string|null; voluntary_vacate_deadline:string|null; photo_storage_reference:string|null; matched_quota_id:string|null; legal_hold:boolean; next_action_at:string|null; created_at:string };
export type NinaCriticalApproval = { id:string; case_id:string; gate:string; decision:string; notes:string; approver_id:string; decided_at:string };
export type NinaLegalDocument = { id:string; case_id:string; document_type:string; version:number; status:string; content_hash:string; created_at:string; content:Record<string,unknown> };
export type NinaDistressEvent = { id:string; case_id:string; event_key:string; event_type:string; status:string; evidence_hash:string; actor_id:string|null; occurred_at:string; payload:Record<string,unknown> };
export type ReconciliationBatch = { id:string; source:string; status:string; total_records:number; matched_records:number; divergent_records:number; created_at:string };
export type ReconciliationItem = { id:string; invoice_id:string|null; external_reference:string; expected_amount:string; received_amount:string; status:string; reason:string|null };
export type CollectionAction = { id:string; invoice_id:string; action_type:string; channel:string; status:string; scheduled_at:string; executed_at:string|null };
export type RecoveredAsset = { id:string; delinquency_case_id:string|null; title:string; asset_type:string; public_description:string; appraisal_value:string; debt_balance:string; recovery_costs:string; custody_reference:string; status:string; created_at:string };
export type AuctionLot = { id:string; asset_id:string; lot_number:string; opening_price:string; reserve_price:string; min_increment:string; platform_fee_percent:string; starts_at:string; ends_at:string; extension_minutes:number; status:string; winning_bid_id:string|null; created_at:string };
export type AuctionBid = { id:string; lot_id:string; bidder_id:string; amount:string; status:string; placed_at:string };
export type AuctionSettlement = { id:string; lot_id:string; winning_bid_id:string; gross_amount:string; recovery_costs:string; debt_paid:string; platform_fee:string; owner_surplus:string; status:string; settled_at:string };
export type TaxDocument = { id:string; user_id:string; reference_month:string; document_number:string; provider:string; gross_amount:string; tax_amount:string; status:string; issued_at:string };
export type TaxClosing = { id:string; reference_month:string; gross_commissions:string; documented_amount:string; eligible_payout:string; exception_count:number; status:string; closed_at:string|null };
export type TaxException = { id:string; closing_id:string; user_id:string; reason:string; amount:string; status:string; resolved_at:string|null; resolution_note:string|null };
export type CommunicationTemplate = { id:string; key:string; channel:string; version:number; subject:string|null; body:string; purpose:string; active:boolean };
export type CommunicationConsent = { id:string; subject_type:string; subject_id:string; channel:string; status:string; source:string; changed_at:string };
export type CommunicationDelivery = { id:string; template_id:string; subject_type:string; subject_id:string; destination_masked:string; status:string; rendered_body:string; provider_message_id:string|null; delivered_at:string|null; created_at:string };
export type ProviderIntegration = { id:string; provider:string; category:string; environment:string; base_url:string|null; active:boolean; health_status:string; latency_ms:number|null; last_health_at:string|null; consecutive_failures:number; circuit_status:string; allowed_hosts:string[]; credential_version:number; credential_rotated_at:string|null; sla_latency_ms:number; total_checks:number; successful_checks:number; uptime_percent:number; created_at:string };
export type WebhookEndpoint = { id:string; integration_id:string; name:string; target_url:string; subscribed_events:string[]; max_attempts:number; active:boolean; created_at:string };
export type WebhookDelivery = { id:string; endpoint_id:string; event_id:string; event_type:string; signature:string; status:string; attempts:number; max_attempts:number; response_code:number|null; response_body:string|null; last_error:string|null; next_attempt_at:string|null; delivered_at:string|null; created_at:string };
export type ProviderIncident = { id:string; integration_id:string; incident_type:string; severity:string; status:string; title:string; details:string; acknowledged_at:string|null; resolved_at:string|null; created_at:string };
export type OnboardingProfile = { id:string; integration_id:string; api_version:string; authentication_type:string; health_path:string; reconciliation_mode:string; status:string; homologated_at:string|null; checklist:Record<string,boolean>; created_at:string };
export type ProviderReconciliationRun = { id:string; integration_id:string; source_type:string; source_reference:string; content_hash:string; total_items:number; matched_items:number; divergent_items:number; status:string; processed_at:string|null; created_at:string };
export type HomologationEvidence = { id:string; integration_id:string; control_key:string; result:string; evidence_hash:string; executed_at:string };
export type AdapterCatalogItem = { category:string; adapter:string; version:string; capabilities:string[]; mode:string };
export type AdapterExecution = { id:string; integration_id:string; category:string; operation:string; idempotency_key:string; input_hash:string; external_id:string; status:string; adapter_name:string; adapter_version:string; output:Record<string,unknown>; created_at:string };
export type AdapterCertification = { id:string; integration_id:string; status:string; passed_checks:number; total_checks:number; report_hash:string; report:{checks:Record<string,boolean>}; executed_at:string };
export type GoLiveApproval = { id:string; integration_id:string; area:string; decision:string; notes:string; decided_by_id:string; decided_at:string };
export type GoLiveDecision = { id:string; integration_id:string; status:string; snapshot_hash:string; blockers:string[]; decided_at:string };
export type UnderwritingPolicy = { id:string; product:string; version:number; minimum_score:number; maximum_ltv_percent:string; maximum_commitment_percent:string; manual_review_score:number; active:boolean; created_at:string };
export type UnderwritingAssessment = { id:string; proposal_id:string; policy_id:string; version:number; score:number; risk_band:string; recommendation:string; status:string; created_at:string; explanation:Record<string,unknown> };
export type BISummary = { funnel:{leads:number;proposals:number;approved:number}; portfolio:{invoiced:string;paid:string;open:string;delinquency_charges:string}; risk:{assessments:number;high_risk:number;pending_decisions:number}; funding:{target:string;funded:string}; recovery:{settled:string} };
export type OperationalJob = { id:string; job_type:string; idempotency_key:string; status:string; attempts:number; max_attempts:number; scheduled_at:string; completed_at:string|null; last_error:string|null; created_at:string };
export type Lead = { id: string; name: string; phone: string; product_interest: string; status: string; source: string; scr_status?: string | null; scr_reference?: string | null; scr_consulted_at?: string | null; created_at: string; owner_id?: string | null; owner_name?: string | null; owner_role?: string | null };
export type Administrator = { id: string; name: string; document: string; authorization_status: string };
export type Quota = { id: string; administrator_id: string; group_code: string; quota_code: string; category: string; credit_value: string; outstanding_balance: string; premium_value: string; installment_due_date?: string | null; nina_scan_status?: string | null; nina_scanned_at?: string | null; status: string; created_at: string };
export type Proposal = { id: string; lead_id: string; product: string; requested_amount: string; status: string; calculation_version: string; created_at: string; owner_id?: string | null; owner_name?: string | null; owner_role?: string | null; lead_name?: string | null; sale_channel?: string | null; client_user_id?: string | null; client_name?: string | null; served_by_user_id?: string | null; served_by_name?: string | null; commission_originator_id?: string | null; commission_originator_name?: string | null };
export type CommercialClient = { id: string; name: string; email: string; phone?: string | null; referred_by_user_id?: string | null };
export type LeaseEquityPauta = {
  id: string; proposal_id: string; pauta_code: string; status: string; property_type: string;
  appraisal_value: string; registry_number: string; registry_office: string;
  tapaf_payment_reference: string | null; tapaf_paid_at: string | null;
  compliance_dossier_uri: string | null; inspection_photos_count: number;
  funding_captured_amount: string; funding_target_amount: string; funding_capture_percent: string;
  activation_at: string | null; activated_manually: boolean; months_in_force: number;
  anticipation_unlock_at: string | null;
  credit_matrix: Record<string, string>;
  anticipation_preview: Record<string, string | number>;
  tokenization_json: Record<string, unknown> | null;
  created_at: string; updated_at: string;
};
export type QuitConOperacao = {
  id: string; proposal_id: string; quota_id: string | null; operacao_code: string; status: string;
  property_type: string; appraisal_value: string; outstanding_balance: string;
  registry_number: string; registry_office: string;
  tapaf_payment_reference: string | null; tapaf_paid_at: string | null;
  compliance_dossier_uri: string | null; inspection_photos_count: number;
  administrator_approved_at: string | null; sla_estimated_completion_at: string | null;
  sla_dias_estimados: number; success_fee_escrow_amount: string;
  funding_captured_amount: string; funding_target_amount: string; funding_capture_percent: string;
  activation_at: string | null; activated_manually: boolean;
  cancellation_reason: string | null; penalty_amount: string | null;
  penalty_detail_json: Record<string, unknown> | null;
  meses_restantes?: number;
  quitacao_vp_amount?: string | null;
  operational_service_enabled?: boolean;
  operational_service_fee_amount?: string | null;
  operational_service_paid_at?: string | null;
  success_fee_escrow_paid_at?: string | null;
  success_fee_refunded?: boolean;
  cedente_payment_amount?: string | null;
  cedente_payment_due_at?: string | null;
  cedente_payment_escrow_reference?: string | null;
  product_snapshot?: Record<string, unknown> | null;
  custos_entrada?: QuitConCustosEntrada | null;
  credit_matrix: Record<string, string>;
  penalty_preview: Record<string, unknown> | null;
  tokenization_json: Record<string, unknown> | null;
  created_at: string; updated_at: string;
};
export type QuitConCustoEntradaItem = {
  codigo: string;
  nome: string;
  valor: string | null;
  obrigatorio?: boolean;
  aplicavel?: boolean;
  reembolsavel?: boolean;
  reembolsavel_se_reprovado_adm?: boolean;
  descricao?: string;
};
export type QuitConCustosEntrada = {
  titulo: string;
  itens: QuitConCustoEntradaItem[];
  total_obrigatorio_abertura: string;
  total_com_servico_operacional: string;
};
export type CollateralNativeInspection = {
  id: string; product: string; proposal_id: string; contract_id: string | null;
  lease_equity_pauta_id: string | null; quitcon_operacao_id: string | null; photos_count: number; vault_s3_uri: string;
  auction_evidence_ready: boolean; created_at: string; updated_at: string;
};
export type SdcQuitConProjectionLine = {
  prazo_meses: number;
  valor_bruto_referencia: string;
  valor_quitcon_estimado_vp: string;
  desconto_financeiro_obtido: string;
  status_operacao: string;
  nota_compliance: string;
};
export type SdcQuitConIntegration = {
  card: {
    saldo_devedor_atual: string;
    quitacao_vista_quitcon_vp: string;
    pagamento_total_cedente_vp_mais_3_porcento?: string;
    meses_restantes_referencia: number;
    taxa_desconto_mensal_percent: string;
    modal: { titulo: string; corpo: string };
  };
  projecao_temporal: {
    saldo_devedor_referencia: string;
    taxa_desconto_mensal: string;
    formula: string;
    nota_compliance_rodape: string;
    linhas: SdcQuitConProjectionLine[];
    tabela: Record<string, SdcQuitConProjectionLine>;
  };
};
export type SdcStartQuitConResponse = {
  created: boolean;
  operacao_id: string;
  operacao_code: string;
  status: string;
  quitcon_sdc: SdcQuitConIntegration;
  tapaf_checkout: { valor_tapaf_brl: string; status: string; operacao_id?: string };
  next_step: string;
  finops_route: string;
  message: string;
};
export type Calculation = {
  id: string; proposal_id: string; version: number; formula_version: string;
  input: Record<string, unknown>; output: Record<string, string | number | null>;
  approved_at: string | null; quitcon_sdc?: SdcQuitConIntegration | null;
};
export type Reservation = { id: string; quota_id: string; proposal_id: string | null; status: string; expires_at: string; created_at: string };
export type Contract = { id: string; proposal_id: string; contract_number: string; status: string; template_version: string; content_hash: string; accepted_at: string | null };
export type TransactionAcceptance = { id:string; contract_id:string; template_id:string; acceptance_type:string; accepted_by_id:string; accepted_at:string; evidence_hash:string };
export type TransferVerification = { id:string; contract_id:string; quota_id:string|null; status:string; administrator_reference:string; transfer_reported_at:string|null; audit_deadline_at:string|null; confirmed_at:string|null; disputed_at:string|null; payout_unlocked:boolean; created_at:string };
export type SellerEvidenceAudit = { id:string; contract_id:string; status:string; buyer_document_masked:string; seller_document_masked:string; statement_contemplated:boolean; administrator_protocol:string|null; parties_matched:boolean; signature_evidence_detected:boolean; manual_review_status:string; rejection_reason:string|null; evidence_hash:string; reviewed_at:string|null; created_at:string };
export type StructuredProperty = { id:string; operation_id:string|null; case_reference:string; buyer_document_masked:string; seller_document_masked:string; has_lien_debt:boolean; unregistered_construction:boolean; route:string; land_appraisal_value:string; future_appraisal_value:string; gross_payout:string; estimated_debt:string; phase1_amount:string; phase2_amount:string; iq_status:string; phase_status:string; registration_deadline_at:string|null; legal_hold:boolean; evidence_hash:string; created_at:string };
export type StructuredPropertyEvent = { id:string; case_id:string; event_key:string; event_type:string; status:string; evidence_hash:string; occurred_at:string };
export type SaaSPlan = {id:string;code:string;name:string;monthly_price:string;central_share_percent:string;network_pool_percent:string;active:boolean};
export type CompanyProfile = {legal_name:string;trade_name:string;cnpj:string;email?:string;phone?:string;footer_line:string;address_line?:string;city_state?:string};
export type LegalManualPublic = {slug:string;title:string;category:string;product:string;audience:string;description:string;document_type:string;requires_login:boolean};
export type LegalManual = LegalManualPublic & {filename:string;available:boolean;size_bytes:number};
export type SaaSTerms = {id:string;code:string;version:number;title:string;body:string;body_hash:string;legal_review_status:string;active:boolean};
export type SaaSSubscription = {id:string;plan_id:string;terms_template_id:string;subscriber_company_name:string;subscriber_document_masked:string;legal_representative_name:string;legal_representative_document_masked:string;status:string;current_period_start:string;current_period_end:string;cancel_at_period_end:boolean;recurring_authorized:boolean;acceptance_hash:string;billing_type?:string|null;subscriber_email?:string|null;asaas_subscription_id?:string|null;last_payment_id?:string|null;last_payment_status?:string|null;payment_checkout_url?:string|null;created_at:string};
export type ValidStampRecord = {id:string;stamp_code:string;entity_type:string;entity_id:string;purpose:string;algorithm:string;payload_hash:string;previous_hash:string|null;chain_hash:string;signature:string;status:string;issued_at:string};
export type FlashScheduleRow = {month:number;opening_balance:string;installment:string;interest:string;principal_amortization:string;settlement_balance:string;ipca_adjusted:boolean};
export type FlashSimulation = {asset_value:string;principal:string;ltv_percent:string;coverage_factor:string;ipca_projected_percent:string;institutional_rate_annual?:string;retail_rate_monthly?:string;platform_fee_percent?:string;platform_fee?:string;itbi_percent?:string;itbi_provision?:string;net_payout?:string;partner_commission_base?:string;interest_basis?:string;execution:string;scenarios:Record<string,FlashScheduleRow[]>};
export type FlashCapitalSimulationParams = {
  institutional_rate_annual: string;
  retail_rate_monthly: string;
  default_ipca_projected_percent: string;
  labels: { funds: string; pool: string };
  source: string;
  policy_id?: string | null;
  policy_version?: number | null;
  nota: string;
};
export type EarlySettlementQuote = {id:string;contract_id:string;installment_number:number;track:string;balloon:boolean;principal:string;settlement_amount:string;future_interest_discount:string;calculation_hash:string;status:string;expires_at:string;created_at:string};
export type FinOpsDomainEvent = {id:string;event_id:string;event_type:string;aggregate_id:string;payload_hash:string;signature_valid:boolean;decision:string;execution_mode:string;received_at:string};
export type NinaRoutingPolicy = {id:string;version:number;population_threshold:number;income_per_capita_threshold:string;tapaf_amount:string;accepted_encumbrances_json:string;rejected_encumbrances_json:string;status:string;approved_at:string|null};
export type NinaRoutingAssessment = {id:string;proposal_id:string;policy_id:string;version:number;asset_type:string;municipality_code:string;population:number;income_per_capita:string;encumbrances:string[];risk_flags:string[];tapaf_evidence_reference:string|null;physical_appraisal_required:boolean;product_route:string;capital_route:string|null;status:string;blockers:string[];evidence_hash:string;approved_at:string|null;created_at:string};
export type AccountBalance = { code: string; name: string; account_type: string; balance: string };
export type LedgerTransaction = { id: string; reference: string; event_type: string; description: string; amount: string; debit_account: string; credit_account: string; created_at: string };
export type EscrowAccount = {
  id: string;
  operation_id: string | null;
  provider: string;
  external_account_id: string;
  asaas_account_id?: string | null;
  subaccount_name?: string | null;
  escrow_enabled?: boolean;
  status: string;
  available_balance: string;
  locked_balance: string;
};
export type EscrowAsaasStatus = {
  configured: boolean;
  connected: boolean;
  provider: string;
  wallet_id: string | null;
  wallet_id_masked: string | null;
  environment: string;
  balance: string | null;
  subaccounts_enabled?: boolean;
  message: string;
};
export type EscrowSubaccountPreview = {
  name: string;
  email: string;
  cpf_cnpj: string;
  mobile_phone: string;
  income_value: string;
  address: string;
  address_number: string;
  province: string;
  postal_code: string;
  person_type: string;
  operation_id: string | null;
};
export type SignatureZapSignStatus = {
  configured: boolean;
  connected: boolean;
  provider: string;
  environment: string;
  documents_total: number | null;
  message: string;
};
export type SignatureEnvelopeView = {
  id: string;
  contract_id: string;
  provider: string;
  external_id: string;
  signer_email: string;
  status: string;
  sent_at: string | null;
  signed_at: string | null;
  sign_url: string | null;
};
export type Payout = { id: string; escrow_account_id: string; beneficiary_name: string; beneficiary_document: string; pix_key_masked: string; amount: string; status: string; provider_transaction_id: string | null; approval_count: number; created_at: string };

export function getToken() {
  return typeof window === "undefined" ? null : localStorage.getItem("letter_access_token");
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  let response: Response;
  try {
    response = await fetchWithRetry(`${API_URL}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
    });
  } catch {
    throw new Error(
      "Não foi possível conectar à API LETTER. O servidor pode estar iniciando — aguarde até 1 minuto e tente novamente.",
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    if (response.status === 404) {
      throw new Error("Endpoint não encontrado na API de produção. Faça redeploy do serviço letter-api no Render.");
    }
    throw new Error(body.detail ?? "Não foi possível concluir a solicitação");
  }
  return response.json();
}

export async function apiForm<T>(path:string, body:FormData):Promise<T>{
  const token=getToken();const response=await fetch(`${API_URL}${path}`,{method:"POST",body,headers:{...(token?{Authorization:`Bearer ${token}`}:{})}});
  if(!response.ok){const payload=await response.json().catch(()=>({}));throw new Error(payload.detail??"Não foi possível enviar o arquivo")}
  return response.json();
}

export async function downloadApi(path:string,filename:string){const token=getToken();const response=await fetch(`${API_URL}${path}`,{headers:{...(token?{Authorization:`Bearer ${token}`}:{})}});if(!response.ok)throw new Error("Não foi possível exportar o relatório");const url=URL.createObjectURL(await response.blob());const link=document.createElement("a");link.href=url;link.download=filename;link.click();URL.revokeObjectURL(url)}

export async function login(email: string, password: string, otp?: string) {
  const result = await api<{ access_token: string; refresh_token: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password, otp: otp || undefined }),
  });
  localStorage.setItem("letter_access_token", result.access_token);
  localStorage.setItem("letter_refresh_token", result.refresh_token);
}

export function logout() {
  localStorage.removeItem("letter_access_token");
  localStorage.removeItem("letter_refresh_token");
  window.location.href = "/";
}
