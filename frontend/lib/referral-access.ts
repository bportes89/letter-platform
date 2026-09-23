const REFERRAL_LINK_ROLES = new Set([
  "MASTER_FRANCHISEE",
  "MANAGER",
  "PARTNER",
  "QUOTA_SELLER",
  "CLIENT",
]);

export function canUseReferralLink(role?: string | null): boolean {
  return Boolean(role && REFERRAL_LINK_ROLES.has(role));
}
