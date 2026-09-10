import type { FlashMockResult, SdcMockResult } from "@/lib/public-simulator-mock";
import { fetchWithRetry } from "@/lib/fetch-with-retry";

const API_URL = (process.env.NEXT_PUBLIC_API_URL?.trim() || "http://localhost:8001/api/v1").replace(/\s+/g, "");

async function publicFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetchWithRetry(`${API_URL}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error(
      "Não foi possível conectar à API LETTER. O servidor pode estar iniciando — aguarde até 1 minuto e tente novamente.",
    );
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: string | { msg?: string }[] | { message?: string; motivos?: string[] };
    };
    if (typeof body.detail === "string") {
      const detail = body.detail.trim();
      if (/^not found$/i.test(detail) || response.status === 404) {
        throw new Error(
          "Serviço de cálculo ainda não disponível nesta API (rota não publicada). Aguarde o deploy do backend ou tente novamente em alguns minutos.",
        );
      }
      throw new Error(detail);
    }
    if (Array.isArray(body.detail) && body.detail[0]?.msg) throw new Error(body.detail[0].msg);
    if (body.detail && typeof body.detail === "object" && !Array.isArray(body.detail)) {
      const d = body.detail as { message?: string; motivos?: string[] };
      const extra = d.motivos?.length ? ` ${d.motivos.join(" ")}` : "";
      throw new Error(`${d.message || "Não foi possível concluir a solicitação."}${extra}`);
    }
    if (response.status === 404) {
      throw new Error(
        "Serviço de cálculo ainda não disponível nesta API (rota não publicada). Aguarde o deploy do backend.",
      );
    }
    throw new Error("Não foi possível concluir a solicitação.");
  }
  return response.json() as Promise<T>;
}

export type PublicQuotaItem = {
  id: string;
  group_code: string;
  quota_code: string;
  category: string;
  credit_value: string;
  status: string;
};

export async function fetchPublicQuotas(): Promise<PublicQuotaItem[]> {
  return publicFetch<PublicQuotaItem[]>("/public/site/quotas");
}

export async function capturePublicLead(payload: {
  razao_social: string;
  whatsapp: string;
  produto: "flash" | "sdc";
  valor_base?: number;
  autorizacao_scr_bacen: boolean;
  document?: string;
  referral_code?: string;
}): Promise<{ status: string; id: string; scr_status?: string; scr_reference?: string; scr_mode?: string }> {
  return publicFetch("/public/site/leads/capture", {
    method: "POST",
    body: JSON.stringify({
      razao_social: payload.razao_social,
      whatsapp: payload.whatsapp,
      produto: payload.produto,
      valor_base: payload.valor_base != null ? String(payload.valor_base) : undefined,
      autorizacao_scr_bacen: payload.autorizacao_scr_bacen,
      document: payload.document,
      referral_code: payload.referral_code,
    }),
  });
}

export type PublicReferralPreview = {
  valid: boolean;
  referral_code: string | null;
  referrer_name: string | null;
  message: string | null;
};

export type PublicClientRegisterResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: { id: string; name: string; email: string; role: string };
  referrer: PublicReferralPreview | null;
  lead_id: string;
};

export async function fetchPublicReferral(referralCode: string): Promise<PublicReferralPreview> {
  return publicFetch<PublicReferralPreview>(`/public/site/referral/${encodeURIComponent(referralCode)}`);
}

export async function registerPublicClient(payload: {
  name: string;
  email: string;
  phone: string;
  password: string;
  document?: string;
  referral_code?: string;
  terms_accepted: boolean;
}): Promise<PublicClientRegisterResponse> {
  return publicFetch<PublicClientRegisterResponse>("/public/site/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function requestPasswordReset(email: string): Promise<{ status: string; development_token: string | null }> {
  return publicFetch("/auth/password-reset/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function confirmPasswordReset(
  token: string,
  newPassword: string,
): Promise<{ status: string }> {
  return publicFetch("/auth/password-reset/confirm", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}

export type AccountRecoveryLookupResult = {
  found: boolean;
  masked_email: string | null;
  message: string;
};

export async function lookupAccountEmail(document: string, phone: string): Promise<AccountRecoveryLookupResult> {
  return publicFetch<AccountRecoveryLookupResult>("/auth/account-recovery/lookup", {
    method: "POST",
    body: JSON.stringify({ document, phone }),
  });
}

export async function simulateFlashPublic(
  assetValue: number,
  requestedAmount: number | null,
): Promise<FlashMockResult> {
  return publicFetch<FlashMockResult>("/public/site/flash/simulate", {
    method: "POST",
    body: JSON.stringify({
      asset_value: String(assetValue),
      requested_amount: requestedAmount != null ? String(requestedAmount) : undefined,
    }),
  });
}

export async function simulateSdcPublic(payload: {
  requested_amount: number;
  duration_months: number;
  asset_category: "REAL_ESTATE" | "VEHICLE" | "OTHER";
  asset_value?: number;
  scr_restrictions?: boolean;
}): Promise<SdcMockResult> {
  return publicFetch<SdcMockResult>("/public/site/sdc/simulate", {
    method: "POST",
    body: JSON.stringify({
      requested_amount: String(payload.requested_amount),
      duration_months: payload.duration_months,
      capital_source: "POOL",
      asset_category: payload.asset_category,
      asset_value: payload.asset_value != null ? String(payload.asset_value) : undefined,
      scr_restrictions: payload.scr_restrictions ?? false,
    }),
  });
}

export type InvitationPreview = {
  email: string;
  role: string;
  expires_at: string;
  contract_required: boolean;
  contract_title: string;
  contract_version: string;
  contract_excerpt: string;
  inviter_name: string | null;
  company_legal_name: string;
  company_cnpj: string;
};

export async function fetchInvitationPreview(token: string): Promise<InvitationPreview> {
  return publicFetch<InvitationPreview>(`/auth/invitations/preview?token=${encodeURIComponent(token)}`);
}

export async function acceptPartnerInvitation(payload: {
  token: string;
  name: string;
  document: string;
  password: string;
  company_name: string;
  company_cnpj: string;
  company_address: string;
  company_city: string;
  company_state: string;
  phone: string;
  terms_accepted: boolean;
  scroll_completed: boolean;
  verification_reference: string;
}): Promise<{ id: string; email: string; role: string; name: string }> {
  return publicFetch("/auth/invitations/accept", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function invitationContractPreviewUrl(token: string): string {
  return `${API_URL}/auth/invitations/preview/contract?token=${encodeURIComponent(token)}`;
}

export type VenderCotaBootstrap = {
  title: string;
  administrators: { id: string; name: string }[];
  tipos: { id: string; label: string }[];
  rules_summary: string;
};

export type VenderCotaResult = {
  viable: boolean;
  motivos: string[];
  tipo_faixa: string;
  credit_value: string;
  paid_percent: string;
  offer_percent: string;
  offer_value: string;
  range_name?: string;
};

export async function fetchVenderCotaBootstrap(): Promise<VenderCotaBootstrap> {
  return publicFetch("/public/site/vender-minha-cota");
}

export async function calculateVenderCota(payload: Record<string, unknown>): Promise<{ result: VenderCotaResult }> {
  return publicFetch("/public/site/vender-minha-cota/calculate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function storeVenderCota(payload: Record<string, unknown>): Promise<{
  offer_id: string;
  status: string;
  offer_value: string;
  offer_percent: string;
  message: string;
  link_dashboard: string;
}> {
  return publicFetch("/public/site/vender-minha-cota/store", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function uploadVenderCotaStatement(offerId: string, contactEmail: string, file: File): Promise<{
  status: string;
  statement_filename: string | null;
}> {
  const body = new FormData();
  body.append("contact_email", contactEmail);
  body.append("file", file);
  const response = await fetch(
    `${API_URL}/public/site/vender-minha-cota/offers/${encodeURIComponent(offerId)}/statement`,
    { method: "POST", body },
  );
  if (!response.ok) {
    const err = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(typeof err.detail === "string" ? err.detail : "Falha ao enviar extrato");
  }
  return response.json();
}
