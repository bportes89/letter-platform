import {
  PRODUCT_NAV,
  filterProductNavItem,
  type ProductNavItem,
} from "@/lib/product-nav";
import type { Module, User } from "@/lib/api";

/** Papéis alinhados ao enum Role do backend. */
export type LetterRole =
  | "PLATFORM_ADMIN"
  | "INTERNAL_STAFF"
  | "MASTER_FRANCHISEE"
  | "MANAGER"
  | "PARTNER"
  | "CLIENT"
  | "QUOTA_SELLER"
  | "RETAIL_INVESTOR"
  | "INSTITUTIONAL_FUND"
  | "AUDITOR";

type AccessList = readonly string[] | "*";

const ROLE_PERSONA_LABEL: Record<LetterRole, string> = {
  PLATFORM_ADMIN: "Operação LETTER",
  INTERNAL_STAFF: "Operação LETTER",
  MASTER_FRANCHISEE: "Franqueadora",
  MANAGER: "Gestão regional",
  PARTNER: "Parceiro comercial",
  CLIENT: "Cliente",
  QUOTA_SELLER: "Vendedor de cotas",
  RETAIL_INVESTOR: "Investidor",
  INSTITUTIONAL_FUND: "Fundo institucional",
  AUDITOR: "Auditoria",
};

/** Produtos visíveis por perfil (chaves de /modules/[key]). */
const ROLE_PRODUCT_KEYS: Record<LetterRole, AccessList> = {
  PLATFORM_ADMIN: "*",
  INTERNAL_STAFF: "*",
  MASTER_FRANCHISEE: [
    "marketplace", "inventory", "proposals", "sdc",
    "flash-capital", "lease-equity", "flash-invest", "quitcon", "lss", "leilao",
  ],
  MANAGER: ["marketplace", "inventory", "proposals", "flash-capital", "lease-equity", "quitcon", "lss"],
  PARTNER: ["marketplace", "proposals", "flash-capital", "lease-equity", "quitcon", "lss", "leilao"],
  CLIENT: ["proposals", "flash-capital", "lease-equity", "quitcon", "lss"],
  QUOTA_SELLER: ["marketplace", "proposals", "quitcon"],
  RETAIL_INVESTOR: ["flash-invest", "leilao"],
  INSTITUTIONAL_FUND: ["flash-invest"],
  AUDITOR: [],
};

/** Módulos de plataforma (API /modules) visíveis por perfil. */
const ROLE_PLATFORM_MODULE_KEYS: Record<LetterRole, AccessList> = {
  PLATFORM_ADMIN: "*",
  INTERNAL_STAFF: [
    "identity", "rbac", "crm", "administrators", "nina", "structured-properties",
    "contracts", "payments", "wallet", "collections", "mmn", "taxtech",
    "communications", "reports", "operations", "admin",
  ],
  MASTER_FRANCHISEE: ["crm", "mmn", "reports", "contracts", "my-wallet", "wallet", "communications"],
  MANAGER: ["crm", "reports", "contracts", "my-wallet", "wallet", "communications"],
  PARTNER: ["crm", "contracts", "my-wallet", "wallet", "mmn", "structured-properties", "communications"],
  CLIENT: ["contracts", "my-wallet", "payments", "communications"],
  QUOTA_SELLER: ["crm", "contracts", "my-wallet", "wallet", "communications"],
  RETAIL_INVESTOR: ["wallet", "reports", "communications"],
  INSTITUTIONAL_FUND: ["reports", "communications"],
  AUDITOR: ["reports", "operations", "rbac"],
};

function normalizeRole(role: string | undefined): LetterRole | null {
  if (!role) return null;
  if (role in ROLE_PERSONA_LABEL) return role as LetterRole;
  return null;
}

function allowed(list: AccessList, key: string): boolean {
  return list === "*" || list.includes(key);
}

export function personaLabel(role: string | undefined): string {
  const r = normalizeRole(role);
  return r ? ROLE_PERSONA_LABEL[r] : "Acesso restrito";
}

export function canAccessProduct(role: string | undefined, productKey: string): boolean {
  const r = normalizeRole(role);
  if (!r) return false;
  return allowed(ROLE_PRODUCT_KEYS[r], productKey);
}

export function canAccessPlatformModule(role: string | undefined, moduleKey: string): boolean {
  const r = normalizeRole(role);
  if (!r) return false;
  return allowed(ROLE_PLATFORM_MODULE_KEYS[r], moduleKey);
}

/** Rotas de produto incluem aliases legados usados em /modules/[key]. */
const PRODUCT_ROUTE_ALIASES: Record<string, string> = {
  marketplace: "marketplace",
  inventory: "marketplace",
  proposals: "proposals",
  sdc: "sdc",
  "flash-capital": "flash-capital",
  finops: "flash-capital",
  "lease-equity": "lease-equity",
  "flash-invest": "flash-invest",
  funding: "flash-invest",
  quitcon: "quitcon",
  lss: "lss",
  leilao: "leilao",
  auctions: "leilao",
};

export function canAccessModuleRoute(role: string | undefined, routeKey: string): boolean {
  if (routeKey === "legal-manuals") return normalizeRole(role) !== null;
  const product = PRODUCT_ROUTE_ALIASES[routeKey];
  if (product) return canAccessProduct(role, product);
  return canAccessPlatformModule(role, routeKey);
}

export function filterProductNav(role: string | undefined): ProductNavItem[] {
  const r = normalizeRole(role);
  if (!r) return [];
  const list = ROLE_PRODUCT_KEYS[r];
  return PRODUCT_NAV.map((item) => filterProductNavItem(item, list, role))
    .filter((item): item is ProductNavItem => item !== null);
}

export function filterPlatformModules(role: string | undefined, modules: Module[]): Module[] {
  const r = normalizeRole(role);
  if (!r) return [];
  const list = ROLE_PLATFORM_MODULE_KEYS[r];
  if (list === "*") return modules;
  return modules.filter((m) => list.includes(m.key));
}

export function showDashboard(_role: string | undefined): boolean {
  return true;
}

export function navSummary(user: User | null): { products: number; platform: number; persona: string } {
  if (!user) return { products: 0, platform: 0, persona: "—" };
  return {
    persona: personaLabel(user.role),
    products: filterProductNav(user.role).length,
    platform: 0,
  };
}
