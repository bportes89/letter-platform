/** Persistência do código de indicação do parceiro (?ref=) no site público. */

const STORAGE_KEY = "letter_referral_code";

export function rememberReferralCode(code: string | null | undefined): string | null {
  const cleaned = (code || "").trim().toUpperCase();
  if (typeof window === "undefined") return cleaned || null;
  if (!cleaned) return getStoredReferralCode();
  try {
    localStorage.setItem(STORAGE_KEY, cleaned);
  } catch {
    /* ignore */
  }
  return cleaned;
}

export function getStoredReferralCode(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const value = localStorage.getItem(STORAGE_KEY)?.trim().toUpperCase() || "";
    return value || null;
  } catch {
    return null;
  }
}

export function resolveReferralCode(urlCode?: string | null): string | null {
  return rememberReferralCode(urlCode) || getStoredReferralCode();
}

export function venderCotaHref(path = "/vender-minha-cota"): string {
  const ref = getStoredReferralCode();
  if (!ref) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}ref=${encodeURIComponent(ref)}`;
}

export function isVenderCotaLink(link: string): boolean {
  const path = link.split("?")[0].replace(/\/$/, "");
  return path === "/vender_minha_cota" || path === "/vender-minha-cota";
}
