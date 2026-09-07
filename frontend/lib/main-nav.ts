import { isPortalHomePath, portalHomeForRole } from "@/lib/portal-routes";

/** Módulos que pertencem ao ambiente BANK (conta digital, escrow, pagamentos). */
export const BANK_MODULE_KEYS = new Set(["my-wallet", "wallet", "payments"]);

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

export function bankHomePath(role?: string): string {
  return "/modules/my-wallet";
}

export function platformHomePath(role?: string): string {
  return portalHomeForRole(role);
}
