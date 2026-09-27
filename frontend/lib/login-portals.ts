import type { LetterRole } from "@/lib/role-nav";
import { personaLabel } from "@/lib/role-nav";
import type { PortalSlug } from "@/lib/portal-routes";
import { PORTAL_LABELS, portalHomeForRole, portalSlugForRole, roleMatchesPortal } from "@/lib/portal-routes";

/** Perfis exibidos no login (simplificado para o usuário). */
export type LoginPortalKey =
  | "cliente"
  | "fornecedor"
  | "parceiro"
  | "investidor"
  | "fundo"
  | "operacao";

export type LoginPortalOption = {
  key: LoginPortalKey;
  label: string;
  description: string;
  portalSlug: PortalSlug | null;
  roles: readonly LetterRole[];
  /** Fornecedor usa portal dedicado, não o login LETTER principal. */
  externalHref?: string;
};

export const LOGIN_PORTAL_OPTIONS: LoginPortalOption[] = [
  {
    key: "cliente",
    label: "Cliente",
    description: "Compras, contratos e conta LETTER",
    portalSlug: "cliente",
    roles: ["CLIENT"],
  },
  {
    key: "fornecedor",
    label: "Fornecedor",
    description: "Portal do fornecedor de cotas",
    portalSlug: null,
    roles: [],
    externalHref: "/portal-fornecedor",
  },
  {
    key: "parceiro",
    label: "Parceiro / Franqueado",
    description: "Rede, originação e produtos LETTER",
    portalSlug: "parceiro",
    roles: ["PARTNER", "QUOTA_SELLER", "MASTER_FRANCHISEE", "MANAGER"],
  },
  {
    key: "investidor",
    label: "Investidor",
    description: "Flash Invest e posições",
    portalSlug: "investidor",
    roles: ["RETAIL_INVESTOR"],
  },
  {
    key: "fundo",
    label: "Fundo institucional",
    description: "Portal institucional e captação",
    portalSlug: "fundo",
    roles: ["INSTITUTIONAL_FUND"],
  },
  {
    key: "operacao",
    label: "Operação LETTER (admin)",
    description: "Equipe interna, auditoria e configurações",
    portalSlug: "operacao",
    roles: ["PLATFORM_ADMIN", "INTERNAL_STAFF", "AUDITOR"],
  },
];

const KEY_SET = new Set(LOGIN_PORTAL_OPTIONS.map((o) => o.key));

/** Compatibilidade com URLs antigas ?portal=franqueado */
const LEGACY_PORTAL_ALIASES: Record<string, LoginPortalKey> = {
  franqueado: "parceiro",
};

export function parseLoginPortalKey(raw: string | null | undefined): LoginPortalKey {
  const key = (raw || "").trim().toLowerCase();
  if (KEY_SET.has(key as LoginPortalKey)) return key as LoginPortalKey;
  if (key in LEGACY_PORTAL_ALIASES) return LEGACY_PORTAL_ALIASES[key];
  return "cliente";
}

export function loginPortalOption(key: LoginPortalKey): LoginPortalOption {
  return LOGIN_PORTAL_OPTIONS.find((o) => o.key === key) ?? LOGIN_PORTAL_OPTIONS[0];
}

export function roleMatchesLoginPortal(role: string | undefined, portalKey: LoginPortalKey): boolean {
  const option = loginPortalOption(portalKey);
  if (option.externalHref) return false;
  if (!role) return false;
  return (option.roles as readonly string[]).includes(role);
}

export function loginPortalMismatchMessage(role: string | undefined, portalKey: LoginPortalKey): string {
  const selected = loginPortalOption(portalKey).label;
  const actual = personaLabel(role);
  const home = portalHomeForRole(role);
  return `Área «${selected}» não confere com este e-mail (cadastro: «${actual}»). Escolha a área correta ou acesse ${home}.`;
}

/** Opções do seletor na tela pública (sem operação — link dedicado). */
export const LOGIN_PORTAL_PUBLIC_OPTIONS = LOGIN_PORTAL_OPTIONS.filter((o) => o.key !== "operacao");

export function portalKeyForRole(role: string | undefined): LoginPortalKey {
  const slug = portalSlugForRole(role);
  if (slug === "operacao") return "operacao";
  if (slug === "investidor") return "investidor";
  if (slug === "fundo") return "fundo";
  if (role === "PARTNER" || role === "QUOTA_SELLER" || role === "MASTER_FRANCHISEE" || role === "MANAGER") {
    return "parceiro";
  }
  return "cliente";
}

export function loginHeadingForPortal(key: LoginPortalKey): { title: string; subtitle: string } {
  if (key === "operacao") {
    return {
      title: "Operação LETTER",
      subtitle: "Acesso da equipe interna e administração.",
    };
  }
  const option = loginPortalOption(key);
  if (option.externalHref) {
    return { title: "Fornecedor", subtitle: option.description };
  }
  return {
    title: "Acesso LETTER",
    subtitle: option.description,
  };
}

export { roleMatchesPortal };
