/** Agrupamento comercial (menu legado) → papéis técnicos do backend. */
export type GestaoPersonaKey =
  | "CLIENTE"
  | "INVESTIDOR"
  | "FUNDO"
  | "FORNECEDOR"
  | "PARCEIRO"
  | "FRANQUEADO"
  | "OPERACAO";

export const GESTAO_PERSONA_TABS: { key: GestaoPersonaKey | "ALL"; label: string }[] = [
  { key: "ALL", label: "Todos" },
  { key: "CLIENTE", label: "Cliente" },
  { key: "INVESTIDOR", label: "Investidor" },
  { key: "FUNDO", label: "Fundo" },
  { key: "FORNECEDOR", label: "Fornecedor" },
  { key: "PARCEIRO", label: "Parceiro" },
  { key: "FRANQUEADO", label: "Franqueado" },
  { key: "OPERACAO", label: "Operação LETTER" },
];

const ROLE_TO_PERSONA: Record<string, GestaoPersonaKey> = {
  CLIENT: "CLIENTE",
  RETAIL_INVESTOR: "INVESTIDOR",
  INSTITUTIONAL_FUND: "FUNDO",
  QUOTA_SELLER: "FORNECEDOR",
  PARTNER: "PARCEIRO",
  MASTER_FRANCHISEE: "FRANQUEADO",
  MANAGER: "FRANQUEADO",
  PLATFORM_ADMIN: "OPERACAO",
  INTERNAL_STAFF: "OPERACAO",
  AUDITOR: "OPERACAO",
};

export function gestaoPersonaForRole(role: string | undefined | null): GestaoPersonaKey | null {
  if (!role) return null;
  return ROLE_TO_PERSONA[role] ?? null;
}

export function gestaoPersonaLabelForRole(role: string | undefined | null): string {
  const persona = gestaoPersonaForRole(role);
  if (persona) {
    return GESTAO_PERSONA_TABS.find((t) => t.key === persona)?.label ?? persona;
  }
  return role || "—";
}

/** Convites / criação de conta — papéis agrupados como no admin antigo. */
export const GESTAO_INVITE_ROLE_GROUPS: { persona: GestaoPersonaKey; label: string; roles: string[] }[] = [
  { persona: "CLIENTE", label: "Cliente", roles: ["CLIENT"] },
  { persona: "INVESTIDOR", label: "Investidor", roles: ["RETAIL_INVESTOR"] },
  { persona: "FUNDO", label: "Fundo", roles: ["INSTITUTIONAL_FUND"] },
  { persona: "FORNECEDOR", label: "Fornecedor", roles: ["QUOTA_SELLER"] },
  { persona: "PARCEIRO", label: "Parceiro", roles: ["PARTNER"] },
  { persona: "FRANQUEADO", label: "Franqueado", roles: ["MASTER_FRANCHISEE", "MANAGER"] },
  {
    persona: "OPERACAO",
    label: "Operação LETTER",
    roles: ["PLATFORM_ADMIN", "INTERNAL_STAFF", "AUDITOR"],
  },
];

export function inviteRolesFlat(): string[] {
  return GESTAO_INVITE_ROLE_GROUPS.flatMap((g) => g.roles);
}
