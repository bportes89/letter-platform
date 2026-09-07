import { api } from "@/lib/api";
import { portalHomeForRole } from "@/lib/portal-routes";

export type ContractStatus = {
  required: boolean;
  completed: boolean;
  template_slug: string | null;
  template_title: string | null;
  template_version: string | null;
  contract_excerpt: string | null;
  requires_pj_fields: boolean;
};

const CONTRACT_OPTIONAL_ROLES = new Set([
  "PLATFORM_ADMIN",
  "INTERNAL_STAFF",
  "AUDITOR",
  "RETAIL_INVESTOR",
  "INSTITUTIONAL_FUND",
]);

export function roleRequiresPlatformContract(role: string): boolean {
  return !CONTRACT_OPTIONAL_ROLES.has(role);
}

export function contractOnboardingPath(): string {
  return "/contrato?onboarding=1";
}

export function isContractOnboardingRoute(pathname: string): boolean {
  return pathname.startsWith("/contrato");
}

export function shouldForceContractOnboarding(role: string, status: ContractStatus): boolean {
  if (!roleRequiresPlatformContract(role)) return false;
  return status.required && !status.completed;
}

export async function fetchContractStatus(): Promise<ContractStatus> {
  return api<ContractStatus>("/contracts/me/status");
}

export async function acceptPlatformContract(payload: {
  terms_accepted: boolean;
  scroll_completed: boolean;
  verification_reference: string;
  company_name?: string;
  company_cnpj?: string;
  company_address?: string;
  company_city?: string;
  company_state?: string;
  phone?: string;
}): Promise<ContractStatus> {
  return api<ContractStatus>("/contracts/me/accept", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function redirectAfterOnboarding(role: string | undefined) {
  const status = await fetchContractStatus();
  if (shouldForceContractOnboarding(role ?? "", status)) {
    window.location.href = contractOnboardingPath();
    return;
  }
  window.location.href = portalHomeForRole(role);
}
