import { api } from "@/lib/api";
import { redirectAfterOnboarding } from "@/lib/contract-onboarding";

export type WalletActivationProfile = {
  document: string | null;
  phone: string | null;
  company_name: string | null;
  company_cnpj: string | null;
};

export type WalletActivationResult = {
  message: string;
  hasSubaccount: boolean;
  onboardingUrl: string | null;
  kycStatus: string | null;
};

function digitsOnly(value: string) {
  return value.replace(/\D/g, "");
}

export function profileFieldsMatch(
  saved: WalletActivationProfile,
  fields: { document: string; phone: string; companyName: string; companyCnpj: string },
) {
  return (
    digitsOnly(saved.document ?? "") === digitsOnly(fields.document)
    && (saved.phone ?? "").trim() === fields.phone.trim()
    && (saved.company_name ?? "").trim() === fields.companyName.trim()
    && digitsOnly(saved.company_cnpj ?? "") === digitsOnly(fields.companyCnpj)
  );
}

export async function activateWalletAccount(
  fields: { document: string; phone: string; companyName: string; companyCnpj: string },
  saved: WalletActivationProfile,
): Promise<WalletActivationResult> {
  if (!profileFieldsMatch(saved, fields)) {
    await api("/auth/me/profile", {
      method: "PATCH",
      body: JSON.stringify({
        document: fields.document.trim() || undefined,
        phone: fields.phone.trim() || undefined,
        company_cnpj: fields.companyCnpj.trim() || undefined,
        company_name: fields.companyName.trim() || undefined,
      }),
    });
  }

  const kyc = await api<{ message: string; kyc_status?: string }>("/kyc/me/complete", { method: "POST" });
  const wallet = await api<{
    has_subaccount: boolean;
    kyc_case?: { status: string } | null;
    account?: { asaas_onboarding_url: string | null };
  }>("/wallet/me");

  return {
    message: kyc.message,
    hasSubaccount: wallet.has_subaccount,
    onboardingUrl: wallet.account?.asaas_onboarding_url ?? null,
    kycStatus: wallet.kyc_case?.status ?? kyc.kyc_status ?? null,
  };
}

export function walletActivationErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : "Não foi possível abrir a conta";
  if (message.toLowerCase().includes("cpf já cadastrado")) {
    return "Este CPF já está vinculado a outro e-mail na LETTER. Entre com a conta original ou contate o suporte.";
  }
  return message;
}

export async function redirectToPortalAfterWallet(role: string | undefined) {
  await redirectAfterOnboarding(role);
}
