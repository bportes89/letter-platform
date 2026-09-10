export type ProductNavChild = {
  key: string;
  name: string;
  /** Visível apenas para perfis internos (admin / staff / franqueadora). */
  internalOnly?: boolean;
};

export type ProductNavItem = {
  key: string;
  name: string;
  /** Agrupa itens operados por parceiros no menu COMERCIAL. */
  commercial?: boolean;
  children?: ProductNavChild[];
  /** Produto de estrutura interna — oculto para parceiros comerciais. */
  internalOnly?: boolean;
  /** Produto do ambiente BANK (investimentos), não da PLATAFORMA. */
  bank?: boolean;
  /** Em stand-by: oculto do menu e travado na rota. */
  standby?: boolean;
};

/**
 * Prioridade operacional (cliente LETTER):
 * 1) Marketplace, SDC, Flash Capital
 * 2) QuitCon, Flash Invest, SaaS (LSS) + ajustes TAPAF
 * Lease Equity: stand-by até nova ordem.
 * Flash Invest: captação por token + mútuo conversível (mútuo primeiro; tokenização depois).
 */
export const PRODUCT_NAV: ProductNavItem[] = [
  {
    key: "marketplace-group",
    name: "Cartas contempladas",
    commercial: true,
    children: [
      { key: "marketplace", name: "Marketplace (esteiras)" },
      { key: "venda-direta-robo", name: "Venda Direta Robô", internalOnly: true },
      { key: "venda-direta-manual", name: "Venda Direta Manual", internalOnly: true },
      { key: "fornecedores", name: "Fornecedores", internalOnly: true },
      { key: "inventory", name: "Inventário (admin)", internalOnly: true },
      { key: "vender-cota", name: "Vender minha cota (admin)", internalOnly: true },
    ],
  },
  {
    key: "proposals",
    name: "Propostas e simulações",
    commercial: true,
  },
  { key: "sdc", name: "SDC — Capital de Giro", commercial: true },
  { key: "flash-capital", name: "Flash Capital", commercial: true },
  { key: "quitcon", name: "QuitCon", commercial: true },
  { key: "flash-invest", name: "Flash Invest", bank: true },
  { key: "lss", name: "SaaS LSS" },
  { key: "leilao", name: "Leilão" },
  { key: "lease-equity", name: "Lease Equity", standby: true },
];

/** Produtos travados / stand-by (não aparecem no menu). */
export const STANDBY_PRODUCT_KEYS = new Set(
  PRODUCT_NAV.filter((item) => item.standby).map((item) => item.key),
);

const NAV_ROUTE_KEYS = new Set<string>();
for (const item of PRODUCT_NAV) {
  if (item.children?.length) {
    for (const child of item.children) NAV_ROUTE_KEYS.add(child.key);
  } else {
    NAV_ROUTE_KEYS.add(item.key);
  }
}

export const PRODUCT_KEYS = NAV_ROUTE_KEYS;

/** Módulos operacionais que deixam de aparecer no menu antigo (viraram produto ou sub-rota). */
export const PLATFORM_HIDDEN_MODULE_KEYS = new Set([
  "inventory",
  "proposals",
  "finops",
  "funding",
  "auctions",
  "lss",
]);

export function isInternalProductRole(role: string | undefined): boolean {
  return role === "PLATFORM_ADMIN" || role === "INTERNAL_STAFF" || role === "MASTER_FRANCHISEE";
}

export function filterProductNavItem(
  item: ProductNavItem,
  allowedKeys: readonly string[] | "*",
  role: string | undefined,
): ProductNavItem | null {
  const internal = isInternalProductRole(role);

  if (item.standby) return null;
  if (item.internalOnly && !internal) return null;

  if (item.children?.length) {
    const children = item.children.filter((child) => {
      if (child.internalOnly && !internal) return false;
      return allowedKeys === "*" || allowedKeys.includes(child.key);
    });
    if (!children.length) return null;
    return { ...item, children };
  }

  if (allowedKeys !== "*" && !allowedKeys.includes(item.key)) return null;
  return item;
}
