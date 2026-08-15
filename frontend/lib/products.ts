export const PRODUCT_LABELS: Record<string, string> = {
  MARKETPLACE: "Marketplace",
  SDC: "SDC",
  FLASH_CREDIT: "Flash Capital",
};

export function productLabel(code: string): string {
  return PRODUCT_LABELS[code] ?? code.replaceAll("_", " ");
}

export const SDC_CAPITAL_SOURCES = [
  { value: "POOL", label: "Pool — 2,5% investidores + 2% plataforma" },
  { value: "FUND", label: "Fundo — 4,5% integral ao fundo" },
] as const;

export const FLASH_CAPITAL_SOURCES = [
  { value: "RETAIL", label: "Pool — 2,5% a.m. (1,6% pool + 0,9% plataforma)" },
  { value: "INSTITUTIONAL", label: "Fundo — 14% a.a. + IPCA (reajuste anual)" },
] as const;

export const VALID_STAMP_DOCUMENTS = {
  REAL_ESTATE: [
    { code: "MATRICULA_ENOTARIADO", label: "Matrícula atualizada (e-notariado)" },
    { code: "LAUDO_AVALIACAO", label: "Laudo de avaliação" },
    { code: "SERASA", label: "Consulta Serasa" },
    { code: "BACEN", label: "Consulta Bacen" },
  ],
  VEHICLE: [
    { code: "FIPE_MOLICAR", label: "Tabela FIPE ou Molicar" },
    { code: "LAUDO_AVALIACAO", label: "Laudo de avaliação" },
    { code: "SERASA", label: "Consulta Serasa" },
    { code: "BACEN", label: "Consulta Bacen" },
  ],
} as const;
