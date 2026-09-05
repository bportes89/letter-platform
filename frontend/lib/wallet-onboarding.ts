export type WalletPeek = {
  has_subaccount: boolean;
  kyc_case?: { status: string } | null;
};

export type WalletProfile = {
  document: string | null;
  phone: string | null;
  company_cnpj?: string | null;
};

const WALLET_OPTIONAL_ROLES = new Set(["PLATFORM_ADMIN", "INTERNAL_STAFF", "AUDITOR"]);

export function profileHasWalletBasics(profile: WalletProfile): boolean {
  const document = profile.document?.replace(/\D/g, "") ?? "";
  const cnpj = profile.company_cnpj?.replace(/\D/g, "") ?? "";
  const phone = profile.phone?.replace(/\D/g, "") ?? "";
  const hasDocument = document.length >= 11 || cnpj.length === 14;
  return hasDocument && phone.length >= 10;
}

export function walletOnboardingComplete(wallet: WalletPeek): boolean {
  if (wallet.has_subaccount) return true;
  const kycStatus = wallet.kyc_case?.status ?? "";
  return kycStatus === "APPROVED" || kycStatus === "SUBMITTED";
}

export function canAccessPortalWithoutWallet(
  role: string,
  wallet: WalletPeek,
  profile: WalletProfile,
): boolean {
  if (WALLET_OPTIONAL_ROLES.has(role)) return true;
  if (walletOnboardingComplete(wallet)) return true;
  return profileHasWalletBasics(profile);
}