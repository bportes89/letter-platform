"use client";

import { ArrowRight, CheckCircle2, Clock3, Construction, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, logout, Module, User } from "@/lib/api";
import { InventoryModule, LeadsModule, MarketplaceModule, ProposalsModule } from "@/components/operational-modules";
import { ContractsModule, PaymentsModule, WalletModule } from "@/components/financial-modules";
import { ComplianceModule, IdentityModule, SecurityModule } from "@/components/identity-modules";
import { FundingModule, NetworkModule } from "@/components/network-funding-modules";
import { CollectionsModule } from "@/components/collections-module";
import { AuctionsModule } from "@/components/auctions-module";
import { CommunicationsModule, TaxTechModule } from "@/components/tax-communications-modules";
import { BIModule, NinaModule } from "@/components/nina-bi-modules";
import { OperationsModule } from "@/components/operations-module";
import { StructuredPropertiesModule } from "@/components/structured-properties-module";
import { LSSModule } from "@/components/lss-module";
import { FinOpsModule } from "@/components/finops-module";
import { PreAnalysisModule } from "@/components/pre-analysis-module";
import { LeaseEquityModule } from "@/components/lease-equity-module";
import { QuitConModule } from "@/components/quitcon-module";
import { canAccessModuleRoute, personaLabel } from "@/lib/role-nav";
import { portalHomeForRole } from "@/lib/portal-routes";

export default function ModulePage() {
  const { key } = useParams<{ key: string }>();
  const routeKey = key ?? "";
  const [module, setModule] = useState<Module | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api<Module[]>("/modules"), api<User>("/auth/me")])
      .then(([items, u]) => {
        setUser(u);
        setModule(items.find((i) => i.key === routeKey) ?? null);
      })
      .catch(() => logout())
      .finally(() => setLoading(false));
  }, [routeKey]);

  if (loading) return <div className="loading">Carregando módulo...</div>;
  if (!user) return null;

  if (!canAccessModuleRoute(user.role, routeKey)) {
    return (
      <div className="module-hero">
        <div>
          <ShieldCheck />
          <h2>Acesso restrito</h2>
          <p>
            Seu perfil ({personaLabel(user.role)}) não tem permissão para acessar este módulo.
            Use o menu lateral para ir aos produtos e ferramentas liberados para você.
          </p>
          <Link className="primary-button" href={portalHomeForRole(user.role)}>
            Voltar à visão geral <ArrowRight />
          </Link>
        </div>
      </div>
    );
  }

  if (routeKey === "marketplace") return <MarketplaceModule />;
  if (routeKey === "inventory") return <InventoryModule />;
  if (routeKey === "proposals") return <ProposalsModule />;
  if (routeKey === "sdc") return <PreAnalysisModule />;
  if (routeKey === "flash-capital" || routeKey === "finops") return <FinOpsModule />;
  if (routeKey === "lease-equity") return <><LeaseEquityModule /><PreAnalysisModule /></>;
  if (routeKey === "flash-invest" || routeKey === "funding") return <FundingModule />;
  if (routeKey === "quitcon") return <QuitConModule />;
  if (routeKey === "leilao" || routeKey === "auctions") return <AuctionsModule />;
  if (routeKey === "crm") return <LeadsModule />;
  if (routeKey === "contracts") return <ContractsModule />;
  if (routeKey === "wallet") return <WalletModule />;
  if (routeKey === "payments") return <PaymentsModule />;
  if (routeKey === "identity") return <IdentityModule />;
  if (routeKey === "rbac") return <SecurityModule />;
  if (routeKey === "admin") return <ComplianceModule />;
  if (routeKey === "mmn") return <NetworkModule />;
  if (routeKey === "collections") return <CollectionsModule />;
  if (routeKey === "taxtech") return <TaxTechModule />;
  if (routeKey === "communications") return <CommunicationsModule />;
  if (routeKey === "nina") return <NinaModule />;
  if (routeKey === "structured-properties") return <StructuredPropertiesModule />;
  if (routeKey === "reports") return <BIModule />;
  if (routeKey === "operations") return <OperationsModule />;
  if (routeKey === "lss") return <LSSModule />;

  if (!module) {
    return (
      <div className="error">
        Módulo &quot;{routeKey}&quot; não encontrado ou indisponível neste ambiente.
      </div>
    );
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">MÓDULO LETTER</span>
          <h1>{module.name}</h1>
          <p>{module.description}</p>
        </div>
        <Status status={module.status} />
      </div>
      <div className="module-hero">
        <div>
          <Construction />
          <h2>Fundação do módulo criada</h2>
          <p>
            Este módulo já está integrado à navegação, identidade, organização, RBAC e auditoria da
            plataforma. As jornadas específicas serão ativadas conforme o roadmap.
          </p>
          <button className="primary-button">
            Consultar roadmap <ArrowRight />
          </button>
        </div>
        <div className="module-checklist">
          <h3>Controles herdados</h3>
          {[
            "Isolamento por organização",
            "Permissões por escopo",
            "Trilha de auditoria",
            "Integrações por adaptadores",
            "Testes e observabilidade",
          ].map((x) => (
            <span key={x}>
              <CheckCircle2 />
              {x}
            </span>
          ))}
        </div>
      </div>
      <section className="panel">
        <div className="panel-title">
          <div>
            <span className="eyebrow dark">PRÓXIMAS ENTREGAS</span>
            <h2>Backlog do módulo</h2>
          </div>
        </div>
        <div className="backlog-grid">
          {[
            "Modelo de dados e regras canônicas",
            "Endpoints e políticas de acesso",
            "Jornadas e telas operacionais",
            "Testes de integração e homologação",
          ].map((x, i) => (
            <div className="backlog-item" key={x}>
              <span>0{i + 1}</span>
              <div>
                <strong>{x}</strong>
                <p>{i === 0 ? "Em preparação para a próxima evolução" : "Planejado no roadmap da plataforma"}</p>
              </div>
              <Clock3 />
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function Status({ status }: { status: string }) {
  const label: Record<string, string> = {
    ACTIVE: "Ativo",
    FOUNDATION: "Fundação pronta",
    ADAPTER_REQUIRED: "Aguardando fornecedor",
    COMPLIANCE_REQUIRED: "Aguardando compliance",
  };
  return (
    <span className={`status ${status.toLowerCase()}`}>
      <ShieldCheck />
      {label[status] ?? status}
    </span>
  );
}
