import type { LetterRole } from "@/lib/role-nav";

export type PortalSlug = "cliente" | "parceiro" | "investidor" | "fundo" | "operacao";

export const PORTAL_PATHS: Record<PortalSlug, string> = {
  cliente: "/cliente",
  parceiro: "/parceiro",
  investidor: "/investidor",
  fundo: "/fundo",
  operacao: "/operacao",
};

export const PORTAL_LABELS: Record<PortalSlug, string> = {
  cliente: "Portal do Cliente",
  parceiro: "Portal do Parceiro",
  investidor: "Portal do Investidor",
  fundo: "Portal Institucional",
  operacao: "Operação LETTER",
};

const ROLE_TO_PORTAL: Record<LetterRole, PortalSlug> = {
  CLIENT: "cliente",
  PARTNER: "parceiro",
  QUOTA_SELLER: "parceiro",
  MASTER_FRANCHISEE: "parceiro",
  MANAGER: "parceiro",
  RETAIL_INVESTOR: "investidor",
  INSTITUTIONAL_FUND: "fundo",
  PLATFORM_ADMIN: "operacao",
  INTERNAL_STAFF: "operacao",
  AUDITOR: "operacao",
};

function normalizeRole(role: string | undefined): LetterRole | null {
  if (!role) return null;
  if (role in ROLE_TO_PORTAL) return role as LetterRole;
  return null;
}

export function portalSlugForRole(role: string | undefined): PortalSlug {
  const r = normalizeRole(role);
  return r ? ROLE_TO_PORTAL[r] : "cliente";
}

export function portalHomeForRole(role: string | undefined): string {
  return PORTAL_PATHS[portalSlugForRole(role)];
}

export function roleMatchesPortal(role: string | undefined, slug: PortalSlug): boolean {
  return portalSlugForRole(role) === slug;
}

export function isPortalHomePath(pathname: string, role: string | undefined): boolean {
  const home = portalHomeForRole(role);
  return pathname === home || pathname === "/dashboard";
}

export const ALL_PORTAL_SLUGS = Object.keys(PORTAL_PATHS) as PortalSlug[];
