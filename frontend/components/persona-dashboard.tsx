"use client";

import {
  ArrowUpRight,
  BrainCircuit,
  CircleDollarSign,
  FileCheck2,
  ShieldAlert,
  Users,
  WalletCards,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, logout, Summary, User } from "@/lib/api";
import { BANK_INVESTMENT_KEYS } from "@/lib/main-nav";
import { quickAccessTargets } from "@/lib/product-nav";
import { canAccessModuleRouteForUser, filterProductNavForUser } from "@/lib/permission-nav";
import { personaLabel } from "@/lib/role-nav";
import { getDashboardLayout } from "@/lib/role-dashboard";

const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const METRIC_ICONS = {
  leads: Users,
  available_quotas: WalletCards,
  active_proposals: FileCheck2,
  active_operations: CircleDollarSign,
} as const;

export function PersonaDashboard() {
  const [data, setData] = useState<Summary | null>(null);
  const [user, setUser] = useState<User | null>(null);
  useEffect(() => {
    Promise.all([api<Summary>("/dashboard"), api<User>("/auth/me")])
      .then(([summary, me]) => {
        setData(summary);
        setUser(me);
      })
      .catch(() => logout());
  }, []);

  if (!data || !user) {
    return <div className="loading">Carregando visão geral...</div>;
  }

  const layout = getDashboardLayout(user.role);
  const products = filterProductNavForUser(user);
  const bankInvestments = products.filter((p) => (BANK_INVESTMENT_KEYS as readonly string[]).includes(p.key));
  const platformProducts = products.filter((p) => !(BANK_INVESTMENT_KEYS as readonly string[]).includes(p.key));
  const quickAccessProducts = quickAccessTargets([...platformProducts, ...bankInvestments]).filter((target) =>
    canAccessModuleRouteForUser(user, target.routeKey),
  );
  const persona = personaLabel(user.role);

  return (
    <div className="dashboard-page">
      <div className="page-heading">
        <div>
          <div className="page-heading-meta">
            <span className="status-pill">
              <span className="status-dot" />
              {persona}
            </span>
            <span className="eyebrow dark">{layout.eyebrow}</span>
          </div>
          <h1>{layout.title}</h1>
          <p>{layout.subtitle}</p>
        </div>
        {layout.exportLabel && <button className="outline-button">{layout.exportLabel}</button>}
      </div>

      {!data.financial_transactions_enabled && (
        <div className="warning-banner">
          <ShieldAlert />
          <div>
            <strong>Modo seguro de implantação</strong>
            <p>Transações financeiras permanecem bloqueadas até a homologação do BaaS e da conta escrow.</p>
          </div>
        </div>
      )}

      <div className="metric-grid">
        {layout.metrics.map((metric, index) => {
          const Icon = METRIC_ICONS[metric.key];
          return (
            <Metric
              key={metric.key}
              icon={<Icon />}
              label={metric.label}
              value={data[metric.key]}
              trend={metric.trend}
              delay={index + 1}
            />
          );
        })}
      </div>

      <div className="dashboard-grid">
        {layout.panels.includes("pipeline") && <PipelinePanel />}
        {layout.panels.includes("quick-access") && quickAccessProducts.length > 0 && (
          <QuickAccessPanel products={quickAccessProducts} />
        )}
        {layout.panels.includes("nina") && <NinaPanel />}
        {layout.panels.includes("risk") && <RiskPanel persona={persona} />}
        {layout.panels.includes("financial") && <FinancialPanel />}
      </div>
    </div>
  );
}

function PipelinePanel() {
  return (
    <section className="panel large panel-float">
      <div className="panel-title">
        <div>
          <span className="eyebrow dark">PIPELINE</span>
          <h2>Esteiras de negócio</h2>
        </div>
        <button>
          Ver detalhes <ArrowUpRight />
        </button>
      </div>
      <div className="pipeline">
        {[
          ["Análise inicial", 8, 72],
          ["Documentação", 5, 49],
          ["Funding", 3, 34],
          ["Contratação", 2, 22],
          ["Liquidação", 1, 12],
        ].map(([name, count, pct]) => (
          <div className="pipeline-row" key={name as string}>
            <span>{name}</span>
            <div>
              <i style={{ width: `${pct}%` }} />
            </div>
            <b>{count}</b>
          </div>
        ))}
      </div>
    </section>
  );
}

function QuickAccessPanel({ products }: { products: { id: string; name: string; routeKey: string; badge: string }[] }) {
  return (
    <section className="panel panel-float quick-access-panel">
      <div className="panel-title">
        <div>
          <span className="eyebrow dark">ACESSO RÁPIDO</span>
          <h2>Seus produtos LETTER</h2>
        </div>
      </div>
      <div className="backlog-grid">
        {products.map((product) => (
          <Link className="backlog-item quick-access-item" href={`/modules/${product.routeKey}`} key={product.id}>
            <span>{product.badge}</span>
            <div>
              <strong>{product.name}</strong>
              <p>Abrir módulo liberado para o seu perfil</p>
            </div>
            <ArrowUpRight aria-hidden />
          </Link>
        ))}
      </div>
    </section>
  );
}

function NinaPanel() {
  return (
    <section className="panel nina-card panel-float">
      <div className="nina-orb">
        <BrainCircuit />
      </div>
      <span className="eyebrow">NINA ENGINE</span>
      <h2>Inteligência operacional</h2>
      <p>
        A camada de regras e automações está pronta para receber os adaptadores de bureaus, WhatsApp e
        análise.
      </p>
      <div className="nina-stats">
        <span>
          <b>18</b> módulos
        </span>
        <span>
          <b>100%</b> auditável
        </span>
      </div>
      <button>
        Abrir central NINA <ArrowUpRight />
      </button>
    </section>
  );
}

function RiskPanel({ persona }: { persona: string }) {
  return (
    <section className="panel panel-float">
      <div className="panel-title">
        <div>
          <span className="eyebrow dark">RISCO</span>
          <h2>Alertas operacionais</h2>
        </div>
      </div>
      <div className="empty-state">
        <ShieldAlert />
        <strong>Nenhum alerta crítico</strong>
        <p>
          O monitoramento de {persona.toLowerCase()} exibirá divergências, bloqueios e exceções relevantes.
        </p>
      </div>
    </section>
  );
}

type StructuredVolume = {
  marketplace: string;
  sdc: string;
  flash_capital: string;
  total: string;
  counts?: { marketplace: number; sdc: number; flash_capital: number };
  note?: string;
};

function FinancialPanel() {
  const [volume, setVolume] = useState<StructuredVolume | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    api<{ structured_volume: StructuredVolume }>("/bi/summary")
      .then((res) => setVolume(res.structured_volume))
      .catch(() => setLoadError(true));
  }, []);

  const marketplace = volume ? Number(volume.marketplace) : 0;
  const sdc = volume ? Number(volume.sdc) : 0;
  const flash = volume ? Number(volume.flash_capital) : 0;
  const total = volume ? Number(volume.total) : 0;
  const denom = total > 0 ? total : 1;
  const segments = [
    { key: "marketplace", label: "Marketplace", value: marketplace, pct: (marketplace / denom) * 100 },
    { key: "sdc", label: "SDC", value: sdc, pct: (sdc / denom) * 100 },
    { key: "flash", label: "Flash Capital", value: flash, pct: (flash / denom) * 100 },
  ];

  return (
    <section className="panel panel-float">
      <div className="panel-title">
        <div>
          <span className="eyebrow dark">FINANCEIRO</span>
          <h2>Volume estruturado</h2>
        </div>
      </div>
      {!volume && !loadError && <p className="muted" style={{ marginTop: 10 }}>Carregando volume por esteira…</p>}
      {loadError && (
        <p className="muted" style={{ marginTop: 10 }}>Não foi possível carregar o volume estruturado.</p>
      )}
      {volume && (
        <>
          <div className="big-number">{money.format(total)}</div>
          <p className="muted" style={{ lineHeight: 1.45 }}>
            {volume.note ||
              "Soma das propostas Marketplace e solicitações ativas nas mesas SDC e Flash Capital."}
          </p>
          <div
            style={{
              display: "flex",
              height: 10,
              borderRadius: 6,
              overflow: "hidden",
              background: "#e4ebe7",
              marginTop: 14,
            }}
            aria-hidden
          >
            {segments.map((seg) =>
              seg.pct > 0 ? (
                <div
                  key={seg.key}
                  style={{
                    width: `${seg.pct}%`,
                    background: seg.key === "marketplace" ? "var(--green)" : seg.key === "sdc" ? "#00b872" : "#067647",
                  }}
                />
              ) : null,
            )}
            {total <= 0 && <div style={{ width: "100%", background: "#dfe8e3" }} />}
          </div>
          <div className="legend">
            {segments.map((seg) => {
              const n =
                seg.key === "flash"
                  ? volume.counts?.flash_capital
                  : seg.key === "sdc"
                    ? volume.counts?.sdc
                    : volume.counts?.marketplace;
              return (
                <span key={seg.key}>
                  {seg.label}
                  {volume.counts ? ` (${n ?? 0})` : ""}: {money.format(seg.value)}
                </span>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}

function Metric({
  icon,
  label,
  value,
  trend,
  delay,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  trend: string;
  delay?: number;
}) {
  return (
    <div className={`metric-card metric-card-float${delay ? ` metric-delay-${delay}` : ""}`}>
      <div className="metric-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{trend}</small>
      </div>
    </div>
  );
}
