"use client";

import {
  computeDeskPipelineSummary,
  type DeskPipelineStatusOption,
} from "@/lib/desk-pipeline-summary";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type DeskRow = { status: string; amount: number };

type PartnerOption = { id: string; name: string };

export function DeskPipelineSummaryBar({
  title,
  items,
  statusOptions,
  statusFilter,
  onStatusFilterChange,
  partnerFilter,
  onPartnerFilterChange,
  partnerOptions,
  showPartnerFilter,
  networkHint,
}: {
  title: string;
  items: DeskRow[];
  statusOptions: readonly DeskPipelineStatusOption[];
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  partnerFilter: string;
  onPartnerFilterChange: (value: string) => void;
  partnerOptions: PartnerOption[];
  showPartnerFilter: boolean;
  networkHint?: string;
}) {
  const { buckets, totalCount, totalAmount } = computeDeskPipelineSummary(items, statusOptions);

  return (
    <div style={{ padding: "14px 18px 0", borderBottom: "1px solid var(--line)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 10, marginBottom: 10 }}>
        <div>
          <span className="eyebrow dark">RESUMO DA ESTEIRA</span>
          <h2 style={{ fontSize: 15, margin: "4px 0 0" }}>{title}</h2>
          {networkHint && (
            <p className="muted" style={{ fontSize: 11, margin: "6px 0 0", maxWidth: 640, lineHeight: 1.45 }}>
              {networkHint}
            </p>
          )}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, fontWeight: 700, color: "#52605a" }}>
            Status
            <select
              value={statusFilter}
              onChange={(e) => onStatusFilterChange(e.target.value)}
              style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid var(--line)", fontWeight: 500 }}
            >
              <option value="ALL">Todos</option>
              {statusOptions.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </label>
          {showPartnerFilter && (
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, fontWeight: 700, color: "#52605a" }}>
              Parceiro
              <select
                value={partnerFilter}
                onChange={(e) => onPartnerFilterChange(e.target.value)}
                style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid var(--line)", fontWeight: 500, maxWidth: 220 }}
              >
                <option value="ALL">Todos da rede</option>
                {partnerOptions.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </label>
          )}
          {statusFilter !== "ALL" && (
            <button type="button" className="table-action" onClick={() => onStatusFilterChange("ALL")}>
              Limpar filtro
            </button>
          )}
        </div>
      </div>
      <div
        className="network-metrics"
        style={{
          gridTemplateColumns: "repeat(auto-fit, minmax(132px, 1fr))",
          marginBottom: 14,
        }}
      >
        {statusOptions.map((s) => {
          const b = buckets[s.value];
          const active = statusFilter === s.value;
          return (
            <article
              key={s.value}
              role="button"
              tabIndex={0}
              onClick={() => onStatusFilterChange(active ? "ALL" : s.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onStatusFilterChange(active ? "ALL" : s.value);
                }
              }}
              style={{
                cursor: "pointer",
                outline: active ? "2px solid var(--green)" : undefined,
                background: active ? "#f2faf6" : undefined,
              }}
              title={`Filtrar: ${s.label}`}
            >
              <small>{s.label}</small>
              <strong>{b?.count ?? 0}</strong>
              <span style={{ display: "block", fontSize: 10, color: "var(--muted)", marginTop: 4 }}>
                {brl.format(b?.total ?? 0)}
              </span>
            </article>
          );
        })}
        <article
          role="button"
          tabIndex={0}
          onClick={() => onStatusFilterChange("ALL")}
          style={{ cursor: "pointer", background: statusFilter === "ALL" ? "#f2faf6" : undefined }}
          title="Ver toda a esteira"
        >
          <small>Total da esteira</small>
          <strong>{totalCount}</strong>
          <span style={{ display: "block", fontSize: 10, color: "var(--muted)", marginTop: 4 }}>
            {brl.format(totalAmount)}
          </span>
        </article>
      </div>
    </div>
  );
}
