export type ProductNavItem = {
  key: string;
  name: string;
};

/** Menu de produtos LETTER — ordem definida com o cliente. */
export const PRODUCT_NAV: ProductNavItem[] = [
  { key: "marketplace", name: "Cartas contempladas (Marketplace)" },
  { key: "sdc", name: "SDC" },
  { key: "flash-capital", name: "Flash Capital" },
  { key: "lease-equity", name: "Lease Equity" },
  { key: "flash-invest", name: "Flash Invest" },
  { key: "quitcon", name: "QuitCon" },
  { key: "lss", name: "SaaS LSS" },
  { key: "leilao", name: "Leilão" },
];

export const PRODUCT_KEYS = new Set(PRODUCT_NAV.map((item) => item.key));

/** Módulos operacionais que deixam de aparecer no menu antigo (viraram produto ou sub-rota). */
export const PLATFORM_HIDDEN_MODULE_KEYS = new Set([
  "inventory",
  "proposals",
  "finops",
  "funding",
  "auctions",
  "lss",
]);
