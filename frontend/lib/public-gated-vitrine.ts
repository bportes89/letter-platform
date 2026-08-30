export const TOKEN_NOMINAL_BRL = 100;

export type PublicFlashInvestItem = {
  id: string;
  ref: string;
  title: string;
  product: "FLASH_POOL" | "SDC_POOL";
  status: "ABERTO" | "CAPTANDO" | "ENCERRADO";
  target_amount: number;
  funded_amount: number;
  min_investment: number;
  rate_reference: string;
  sensitive: {
    borrower: string;
    collateral: string;
    registry: string;
    operation_id: string;
  };
};

export type PublicAuctionItem = {
  id: string;
  ref: string;
  title: string;
  status: "EM ANÁLISE" | "ABERTO" | "ENCERRADO";
  opening_price: number;
  avm: number;
  ltv_percent: number;
  ends_label: string;
  sensitive: {
    address: string;
    registry: string;
    owner: string;
  };
};

export const DEMO_FLASH_INVEST: PublicFlashInvestItem[] = [
  {
    id: "fi-001",
    ref: "POOL-042",
    title: "Flash Invest · Operação imobiliária corporativa",
    product: "FLASH_POOL",
    status: "CAPTANDO",
    target_amount: 1_200_000,
    funded_amount: 780_000,
    min_investment: TOKEN_NOMINAL_BRL,
    rate_reference: "1,6% a.m.",
    sensitive: {
      borrower: "Holdings Alpha Participações Ltda.",
      collateral: "Av. Paulista, 1000 — Bela Vista, São Paulo/SP",
      registry: "Matrícula nº 145.982 — 4º Ofício de Registro de Imóveis",
      operation_id: "OP-FLASH-2026-0099-A7",
    },
  },
  {
    id: "fi-002",
    ref: "POOL-038",
    title: "Flash Invest · Giro estruturado SDC",
    product: "SDC_POOL",
    status: "ABERTO",
    target_amount: 800_000,
    funded_amount: 215_000,
    min_investment: TOKEN_NOMINAL_BRL,
    rate_reference: "1,6% a.m.",
    sensitive: {
      borrower: "Comércio Beta Distribuição S/A",
      collateral: "Grupo 1847 · Cota 042 — Administradora homologada",
      registry: "Contrato de alienação fiduciária nº 2026/SDC-038",
      operation_id: "OP-SDC-2026-0038-B2",
    },
  },
];

export const DEMO_AUCTION_LOTS: PublicAuctionItem[] = [
  {
    id: "pauta-99",
    ref: "Pauta 099",
    title: "Ativo corporativo · São Paulo",
    status: "EM ANÁLISE",
    opening_price: 1_000_000,
    avm: 2_500_000,
    ltv_percent: 40,
    ends_label: "Publicação após habilitação",
    sensitive: {
      address: "Av. Paulista, Nº 1000 — Bela Vista, São Paulo/SP",
      registry: "Matrícula nº 145.982 — 4º Ofício RGI",
      owner: "Proprietário original — dados sob sigilo contratual",
    },
  },
  {
    id: "pauta-104",
    ref: "Pauta 104",
    title: "Imóvel comercial · Grande ABC",
    status: "ABERTO",
    opening_price: 620_000,
    avm: 1_550_000,
    ltv_percent: 40,
    ends_label: "Encerra em 12 dias · incremento R$ 5 mil",
    sensitive: {
      address: "Rua Industrial, 220 — Santo André/SP",
      registry: "Matrícula nº 88.441 — 2º Ofício RGI",
      owner: "Empresa recuperanda — identificação restrita",
    },
  },
];
