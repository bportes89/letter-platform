import { isPortalHomePath, portalHomeForRole } from "@/lib/portal-routes";
import { isInternalProductRole } from "@/lib/product-nav";

/** Conta digital do usuário (BANK). */
export const BANK_ACCOUNT_KEYS = ["my-wallet"] as const;

/**
 * Produtos de investimento — ficam no BANK (hoje só Flash Invest).
 * `funding` é alias legado da mesma tela.
 */
export const BANK_INVESTMENT_KEYS = ["flash-invest", "funding"] as const;

/**
 * Controle interno / gestão do BANK — ações, escrow, ledger e cobrança.
 * Visível para perfis internos.
 */
export const BANK_CONTROL_KEYS = ["payments", "wallet", "collections"] as const;

/** Todas as chaves de rota/módulo que pertencem ao ambiente BANK. */
export const BANK_MODULE_KEYS = new Set<string>([
  ...BANK_ACCOUNT_KEYS,
  ...BANK_INVESTMENT_KEYS,
  ...BANK_CONTROL_KEYS,
  "bank-control",
]);

const BANK_CONTROL_LABELS: Record<string, string> = {
  "bank-control": "Painel de gestão",
  payments: "Pagamentos e escrow",
  wallet: "Ledger e saldos",
  collections: "Cobrança e inadimplência",
};

const PORTAL_HOME_PATHS = new Set([
  "/cliente",
  "/parceiro",
  "/investidor",
  "/fundo",
  "/operacao",
  "/dashboard",
]);

export function isBankModuleKey(key: string): boolean {
  return BANK_MODULE_KEYS.has(key);
}

export function isBankInvestmentKey(key: string): boolean {
  return (BANK_INVESTMENT_KEYS as readonly string[]).includes(key);
}

export function isBankControlKey(key: string): boolean {
  return key === "bank-control" || (BANK_CONTROL_KEYS as readonly string[]).includes(key);
}

export function bankControlLabel(key: string): string {
  return BANK_CONTROL_LABELS[key] ?? key;
}

export function canSeeBankControl(role: string | undefined): boolean {
  return isInternalProductRole(role) || role === "AUDITOR";
}

export function moduleKeyFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/modules\/([^/]+)/);
  return match?.[1] ?? null;
}

export function isBankPath(pathname: string): boolean {
  const key = moduleKeyFromPath(pathname);
  return key ? isBankModuleKey(key) : false;
}

export function isPlatformPath(pathname: string, role?: string): boolean {
  if (pathname === "/seguranca") return true;
  if (PORTAL_HOME_PATHS.has(pathname)) return true;
  if (role && isPortalHomePath(pathname, role)) return true;
  const key = moduleKeyFromPath(pathname);
  if (!key) return false;
  return !isBankModuleKey(key);
}

export function bankHomePath(_role?: string): string {
  return "/modules/my-wallet";
}

export function platformHomePath(role?: string): string {
  return portalHomeForRole(role);
}
