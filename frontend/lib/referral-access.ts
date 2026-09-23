const REFERRAL_LINK_ROLES = new Set([
  "MASTER_FRANCHISEE",
  "MANAGER",
  "PARTNER",
  "QUOTA_SELLER",
  "CLIENT",
  // Operação LETTER: link da matriz Letter Bank (API delega ao master raiz).
  "PLATFORM_ADMIN",
  "INTERNAL_STAFF",
]);

export function canUseReferralLink(role?: string | null): boolean {
  return Boolean(role && REFERRAL_LINK_ROLES.has(role));
}
