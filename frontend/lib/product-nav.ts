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
};

/** Menu de produtos LETTER — ordem definida com o cliente. */
export const PRODUCT_NAV: ProductNavItem[] = [
  {
    key: "marketplace-group",
    name: "Cartas contempladas",
    commercial: true,
    children: [
      { key: "marketplace", name: "Marketplace (esteiras)" },
      { key: "inventory", name: "Inventário (admin)", internalOnly: true },
    ],
  },
  {
    key: "proposals",
    name: "Propostas e simulações",
    commercial: true,
  },
  { key: "sdc", name: "SDC — estrutura interna", internalOnly: true },
  { key: "flash-capital", name: "Flash Capital" },
  { key: "lease-equity", name: "Lease Equity" },
  { key: "flash-invest", name: "Flash Invest" },
  { key: "quitcon", name: "QuitCon" },
  { key: "lss", name: "SaaS LSS" },
  { key: "leilao", name: "Leilão" },
];

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
