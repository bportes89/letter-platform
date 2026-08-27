import type { FlashMockResult, SdcMockResult } from "@/lib/public-simulator-mock";

const API_URL = (process.env.NEXT_PUBLIC_API_URL?.trim() || "http://localhost:8001/api/v1").replace(/\s+/g, "");

async function publicFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error("Não foi possível conectar à API. Tente novamente em instantes.");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string | { msg?: string }[] };
    if (typeof body.detail === "string") throw new Error(body.detail);
    if (Array.isArray(body.detail) && body.detail[0]?.msg) throw new Error(body.detail[0].msg);
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
}): Promise<{ status: string; id: string }> {
  return publicFetch("/public/site/leads/capture", {
    method: "POST",
    body: JSON.stringify({
      razao_social: payload.razao_social,
      whatsapp: payload.whatsapp,
      produto: payload.produto,
      valor_base: payload.valor_base != null ? String(payload.valor_base) : undefined,
      autorizacao_scr_bacen: payload.autorizacao_scr_bacen,
    }),
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
  quota_ids: string[];
  requested_amount: number;
  duration_months: number;
}): Promise<SdcMockResult> {
  return publicFetch<SdcMockResult>("/public/site/sdc/simulate", {
    method: "POST",
    body: JSON.stringify({
      quota_ids: payload.quota_ids,
      requested_amount: String(payload.requested_amount),
      duration_months: payload.duration_months,
      capital_source: "POOL",
    }),
  });
}
