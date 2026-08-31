import type { Summary } from "@/lib/api";
import type { LetterRole } from "@/lib/role-nav";

export type DashboardMetricDef = {
  key: keyof Pick<Summary, "leads" | "available_quotas" | "active_proposals" | "active_operations">;
  label: string;
  trend: string;
};

export type DashboardPanel = "pipeline" | "nina" | "risk" | "financial" | "quick-access";

export type DashboardLayout = {
  eyebrow: string;
  title: string;
  subtitle: string;
  metrics: DashboardMetricDef[];
  panels: DashboardPanel[];
  exportLabel: string | null;
};

const LAYOUTS: Record<LetterRole, DashboardLayout> = {
  PLATFORM_ADMIN: {
    eyebrow: "VISÃO EXECUTIVA",
    title: "Centro de operações",
    subtitle: "Ecossistema LETTER — capital estruturado, consórcio e recuperação com trilha auditável.",
    metrics: [
      { key: "leads", label: "Leads no funil", trend: "Base inicial" },
      { key: "available_quotas", label: "Cotas disponíveis", trend: "Inventário ativo" },
      { key: "active_proposals", label: "Propostas ativas", trend: "Em acompanhamento" },
      { key: "active_operations", label: "Operações ativas", trend: "Ledger protegido" },
    ],
    panels: ["pipeline", "nina", "risk", "financial"],
    exportLabel: "Exportar relatório",
  },
  INTERNAL_STAFF: {
    eyebrow: "OPERAÇÃO LETTER",
    title: "Central operacional",
    subtitle: "Monitoramento de esteiras, exceções e volume estruturado da matriz.",
    metrics: [
      { key: "leads", label: "Leads no funil", trend: "Entrada comercial" },
      { key: "active_proposals", label: "Propostas ativas", trend: "Em análise" },
      { key: "active_operations", label: "Operações ativas", trend: "Em execução" },
      { key: "available_quotas", label: "Cotas disponíveis", trend: "Inventário" },
    ],
    panels: ["pipeline", "risk", "nina", "financial"],
    exportLabel: "Exportar relatório",
  },
  MASTER_FRANCHISEE: {
    eyebrow: "FRANQUEADORA",
    title: "Painel da rede",
    subtitle: "Originação, produtos LETTER e performance da franqueadora.",
    metrics: [
      { key: "leads", label: "Leads na rede", trend: "Funil comercial" },
      { key: "active_proposals", label: "Propostas ativas", trend: "Em curso" },
      { key: "active_operations", label: "Operações ativas", trend: "Carteira" },
      { key: "available_quotas", label: "Cotas disponíveis", trend: "Marketplace" },
    ],
    panels: ["pipeline", "quick-access", "financial"],
    exportLabel: "Relatório da rede",
  },
  MANAGER: {
    eyebrow: "GESTÃO REGIONAL",
    title: "Painel regional",
    subtitle: "Acompanhe originação e propostas da sua unidade.",
    metrics: [
      { key: "leads", label: "Leads regionais", trend: "Funil local" },
      { key: "active_proposals", label: "Propostas ativas", trend: "Em acompanhamento" },
      { key: "active_operations", label: "Operações ativas", trend: "Carteira" },
    ],
    panels: ["pipeline", "quick-access", "risk"],
    exportLabel: null,
  },
  PARTNER: {
    eyebrow: "PARCEIRO COMERCIAL",
    title: "Central comercial",
    subtitle: "Originação, simulações, propostas e acompanhamento das suas operações LETTER.",
    metrics: [
      { key: "leads", label: "Leads no funil", trend: "Sua originação" },
      { key: "available_quotas", label: "Cotas disponíveis", trend: "Marketplace" },
      { key: "active_proposals", label: "Propostas ativas", trend: "Em negociação" },
      { key: "active_operations", label: "Operações ativas", trend: "Fechadas por você" },
    ],
    panels: ["pipeline", "quick-access", "financial"],
    exportLabel: "Exportar pipeline",
  },
  CLIENT: {
    eyebrow: "ÁREA DO CLIENTE",
    title: "Minha jornada LETTER",
    subtitle: "Acompanhe propostas, contratos e pagamentos das suas operações de crédito estruturado.",
    metrics: [
      { key: "active_proposals", label: "Propostas em andamento", trend: "Suas solicitações" },
      { key: "active_operations", label: "Operações ativas", trend: "Contratos vigentes" },
    ],
    panels: ["quick-access", "risk"],
    exportLabel: null,
  },
  QUOTA_SELLER: {
    eyebrow: "VENDAS DE COTAS",
    title: "Central de vendas",
    subtitle: "Marketplace, leads e propostas de cotas contempladas.",
    metrics: [
      { key: "available_quotas", label: "Cotas disponíveis", trend: "Inventário" },
      { key: "leads", label: "Leads qualificados", trend: "Funil" },
      { key: "active_proposals", label: "Propostas ativas", trend: "Em curso" },
    ],
    panels: ["quick-access", "pipeline"],
    exportLabel: null,
  },
  RETAIL_INVESTOR: {
    eyebrow: "CENTRAL DO INVESTIDOR",
    title: "Flash Invest & oportunidades",
    subtitle: "Reservas, posições e leilões disponíveis para o seu perfil de investidor.",
    metrics: [
      { key: "active_operations", label: "Posições ativas", trend: "Carteira" },
      { key: "active_proposals", label: "Oportunidades abertas", trend: "Pools e leilões" },
    ],
    panels: ["quick-access", "financial"],
    exportLabel: "Extrato do investidor",
  },
  INSTITUTIONAL_FUND: {
    eyebrow: "VISÃO INSTITUCIONAL",
    title: "Painel do fundo",
    subtitle: "Posições, relatórios e comunicações para gestão institucional de capital.",
    metrics: [
      { key: "active_operations", label: "Posições alocadas", trend: "Carteira SPE" },
      { key: "active_proposals", label: "Oportunidades em análise", trend: "Comitê" },
    ],
    panels: ["financial", "quick-access"],
    exportLabel: "Relatório institucional",
  },
  AUDITOR: {
    eyebrow: "AUDITORIA",
    title: "Painel de conformidade",
    subtitle: "Monitoramento de operações, trilhas e exceções para revisão independente.",
    metrics: [
      { key: "active_operations", label: "Operações monitoradas", trend: "Universo auditável" },
      { key: "active_proposals", label: "Propostas em trilha", trend: "Rastreabilidade" },
    ],
    panels: ["risk", "nina"],
    exportLabel: "Exportar trilha",
  },
};

function normalizeRole(role: string | undefined): LetterRole | null {
  if (!role) return null;
  if (role in LAYOUTS) return role as LetterRole;
  return null;
}

export function getDashboardLayout(role: string | undefined): DashboardLayout {
  const r = normalizeRole(role);
  return r ? LAYOUTS[r] : LAYOUTS.CLIENT;
}
