"use client";

import { FileSpreadsheet, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type Tab = "platform" | "supplier" | "partner";

type Summary = {
  scope: string;
  line_count: number;
  platform_fee_total: string;
  supplier_release_total: string;
  affiliate_total: string;
  platform_net_total: string;
  gross_total: string;
};

type ExtratoLine = {
  kind: string;
  released_at: string | null;
  proposal_id: string | null;
  lead_id: string | null;
  reference: string | null;
  beneficiary_label: string | null;
  credit: string | null;
  percent: string | null;
  amount: string | null;
  level: number | null;
  status: string | null;
};

type PlatformRow = {
  proposal_id: string;
  lead_id: string | null;
  released_at: string | null;
  reference: string | null;
  credit: string | null;
  platform_fee: string;
  supplier_release: string;
  affiliate_total: string;
  platform_net: string;
};

type SupplierLedgerRow = {
  id: string;
  kind: string;
  amount: string;
  reference: string;
  proposal_id: string | null;
  description: string;
  created_at: string | null;
  supplier_name: string | null;
  supplier_source_key: string | null;
};

const TAB_LABEL: Record<Tab, string> = {
  platform: "Plataforma",
  supplier: "Fornecedores",
  partner: "Parceiros / franquia",
};

const KIND_LABEL: Record<string, string> = {
  platform_fee: "Taxa plataforma",
  supplier_release: "Repasse fornecedor",
  affiliate: "Comissão rede",
};

export function MarketplaceExtratoModule() {
  const [tab, setTab] = useState<Tab>("platform");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [lines, setLines] = useState<ExtratoLine[]>([]);
  const [platformRows, setPlatformRows] = useState<PlatformRow[]>([]);
  const [supplierLedger, setSupplierLedger] = useState<SupplierLedgerRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const scope = tab === "partner" ? "partner" : tab === "supplier" ? "supplier" : "platform";
      const [sum, extratoLines] = await Promise.all([
        api<Summary>(`/marketplace/extrato/summary?scope=${scope}`),
        api<ExtratoLine[]>(`/marketplace/extrato?scope=${scope}&limit=200`),
      ]);
      setSummary(sum);
      setLines(extratoLines);
      if (tab === "platform") {
        setPlatformRows(await api<PlatformRow[]>("/marketplace/extrato/platform-by-proposal?limit=120"));
      } else {
        setPlatformRows([]);
      }
      if (tab === "supplier") {
        setSupplierLedger(await api<SupplierLedgerRow[]>("/marketplace/extrato/supplier-ledger?limit=200"));
      } else {
        setSupplierLedger([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar extrato.");
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="module-page">
      <header className="module-header">
        <FileSpreadsheet />
        <div>
          <h1>Extratos — marketplace</h1>
          <p className="muted">Espelho dos menus legado: plataforma (líquido), fornecedor e parceiro.</p>
        </div>
        <button type="button" onClick={() => void load()} disabled={loading}>
          <RefreshCw /> Atualizar
        </button>
      </header>

      <div className="toolbar" style={{ marginBottom: "1rem", gap: "0.5rem" }}>
        {(Object.keys(TAB_LABEL) as Tab[]).map((key) => (
          <button
            key={key}
            type="button"
            className={tab === key ? "primary" : "table-action"}
            onClick={() => setTab(key)}
          >
            {TAB_LABEL[key]}
          </button>
        ))}
      </div>

      {error && <div className="error">{error}</div>}

      {summary && (
        <div className="stat-grid">
          {tab === "platform" && (
            <>
              <div className="stat-card">
                <small>Taxa plataforma (bruto)</small>
                <strong>{brl.format(Number(summary.platform_fee_total))}</strong>
              </div>
              <div className="stat-card">
                <small>Comissão rede (dedução)</small>
                <strong>{brl.format(Number(summary.affiliate_total))}</strong>
              </div>
              <div className="stat-card">
                <small>Líquido plataforma (B8)</small>
                <strong>{brl.format(Number(summary.platform_net_total))}</strong>
              </div>
            </>
          )}
          {tab === "supplier" && (
            <>
              <div className="stat-card">
                <small>Repasses fornecedor</small>
                <strong>{brl.format(Number(summary.supplier_release_total))}</strong>
              </div>
              <div className="stat-card">
                <small>Lançamentos extrato</small>
                <strong>{summary.line_count}</strong>
              </div>
            </>
          )}
          {tab === "partner" && (
            <>
              <div className="stat-card">
                <small>Comissões rede</small>
                <strong>{brl.format(Number(summary.affiliate_total))}</strong>
              </div>
              <div className="stat-card">
                <small>Linhas no extrato</small>
                <strong>{summary.line_count}</strong>
              </div>
            </>
          )}
        </div>
      )}

      {tab === "platform" && platformRows.length > 0 && (
        <section className="panel" style={{ marginBottom: "1rem" }}>
          <h2 className="subheading">Por venda (líquido plataforma)</h2>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Lead</th>
                  <th>Crédito</th>
                  <th>Taxa plat.</th>
                  <th>Repasse forn.</th>
                  <th>Rede</th>
                  <th>Líquido</th>
                </tr>
              </thead>
              <tbody>
                {platformRows.map((row) => (
                  <tr key={row.proposal_id}>
                    <td>{row.released_at ? new Date(row.released_at).toLocaleString("pt-BR") : "—"}</td>
                    <td>
                      <code>{row.lead_id?.slice(0, 8) ?? "—"}</code>
                    </td>
                    <td>{row.credit ? brl.format(Number(row.credit)) : "—"}</td>
                    <td>{brl.format(Number(row.platform_fee))}</td>
                    <td>{brl.format(Number(row.supplier_release))}</td>
                    <td>{brl.format(Number(row.affiliate_total))}</td>
                    <td><b>{brl.format(Number(row.platform_net))}</b></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "supplier" && supplierLedger.length > 0 && (
        <section className="panel" style={{ marginBottom: "1rem" }}>
          <h2 className="subheading">Extrato carteira fornecedor (ledger)</h2>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Fornecedor</th>
                  <th>Tipo</th>
                  <th>Valor</th>
                  <th>Descrição</th>
                </tr>
              </thead>
              <tbody>
                {supplierLedger.map((row) => (
                  <tr key={row.id}>
                    <td>{row.created_at ? new Date(row.created_at).toLocaleString("pt-BR") : "—"}</td>
                    <td>
                      <b>{row.supplier_name ?? "—"}</b>
                      <small>{row.supplier_source_key}</small>
                    </td>
                    <td>{row.kind}</td>
                    <td>{brl.format(Number(row.amount))}</td>
                    <td>{row.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="panel">
        <h2 className="subheading">Linhas — {TAB_LABEL[tab]}</h2>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Data</th>
                <th>Tipo</th>
                <th>Beneficiário</th>
                <th>Crédito</th>
                <th>%</th>
                <th>Valor</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {lines.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <small className="muted">Nenhum lançamento liberado ainda.</small>
                  </td>
                </tr>
              ) : (
                lines.map((row, idx) => (
                  <tr key={`${row.reference}-${row.kind}-${idx}`}>
                    <td>{row.released_at ? new Date(row.released_at).toLocaleString("pt-BR") : "—"}</td>
                    <td>{KIND_LABEL[row.kind] ?? row.kind}</td>
                    <td>{row.beneficiary_label ?? "—"}</td>
                    <td>{row.credit ? brl.format(Number(row.credit)) : "—"}</td>
                    <td>{row.percent ?? (row.level != null ? `N${row.level}` : "—")}</td>
                    <td>{row.amount ? brl.format(Number(row.amount)) : "—"}</td>
                    <td>{row.status ?? "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
