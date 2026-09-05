export type WalletPeek = {
  has_subaccount: boolean;
  kyc_case?: { status: string } | null;
};

export type WalletProfile = {
  document: string | null;
  phone: string | null;
  company_cnpj?: string | null;
};

/** Perfis operacionais que podem usar o portal sem carteira LETTER aberta. */
const WALLET_OPTIONAL_ROLES = new Set(["PLATFORM_ADMIN", "INTERNAL_STAFF", "AUDITOR"]);

/** Cliente, parceiro e demais perfis comerciais — exigem conta LETTER antes do escritório. */
const WALLET_REQUIRED_ROLES = new Set([
  "CLIENT",
  "PARTNER",
  "QUOTA_SELLER",
  "MASTER_FRANCHISEE",
  "MANAGER",
  "RETAIL_INVESTOR",
  "INSTITUTIONAL_FUND",
]);

export function roleRequiresWalletAccount(role: string): boolean {
  return WALLET_REQUIRED_ROLES.has(role);
}

export function walletAccountReady(wallet: WalletPeek): boolean {
  return wallet.has_subaccount;
}

export function profileHasWalletBasics(profile: WalletProfile): boolean {
  const document = profile.document?.replace(/\D/g, "") ?? "";
  const cnpj = profile.company_cnpj?.replace(/\D/g, "") ?? "";
  const phone = profile.phone?.replace(/\D/g, "") ?? "";
  const hasDocument = document.length >= 11 || cnpj.length === 14;
  return hasDocument && phone.length >= 10;
}

export function shouldForceWalletOnboarding(role: string, wallet: WalletPeek): boolean {
  if (WALLET_OPTIONAL_ROLES.has(role)) return false;
  if (!roleRequiresWalletAccount(role)) return false;
  return !walletAccountReady(wallet);
}

export function walletOnboardingPath(): string {
  return "/modules/my-wallet?onboarding=1";
}

export function isWalletOnboardingRoute(pathname: string): boolean {
  return pathname.startsWith("/cadastro/conta") || pathname.startsWith("/modules/my-wallet");
}
