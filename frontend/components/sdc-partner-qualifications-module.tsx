"use client";

import { Award, Calculator, CheckCircle2, RefreshCw } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type Tier = {
  id: string;
  legacy_id: number | null;
  active: boolean;
  name: string;
  price_init: string;
  price_final: string;
  price_bonus: string;
  sort_order: number;
};

type FranchiseRow = {
  user_id: string;
  name: string;
  email: string;
  appraisal_amount: string;
  appraisal_tier_name: string | null;
  current_tier_id: string | null;
};

type HistoryRow = {
  id: string;
  date_init: string;
  date_final: string;
  created_at: string;
};

export function SdcPartnerQualificationsModule() {
  const [tab, setTab] = useState<"tiers" | "appraisal">("tiers");
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [franchises, setFranchises] = useState<FranchiseRow[]>([]);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [dateInit, setDateInit] = useState("");
  const [dateFinal, setDateFinal] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const loadTiers = useCallback(async () => {
    setTiers(await api<Tier[]>("/sdc/partner-qualification-tiers"));
  }, []);

  const loadFranchises = useCallback(async () => {
    setFranchises(await api<FranchiseRow[]>("/sdc/partner-qualifications/appraisal/franchises"));
  }, []);

  const loadHistory = useCallback(async () => {
    setHistory(await api<HistoryRow[]>("/sdc/partner-qualifications/appraisal/history"));
  }, []);

  useEffect(() => {
    loadTiers().catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar faixas"));
    loadHistory().catch(() => undefined);
  }, [loadTiers, loadHistory]);

  useEffect(() => {
    if (tab !== "appraisal") return;
    if (dateInit || dateFinal) return;
    void api("/sdc/partner-qualifications/appraisal/clear-preview", { method: "POST" })
      .then(() => loadFranchises())
      .catch(() => undefined);
  }, [tab, dateInit, dateFinal, loadFranchises]);

  async function importLegacy() {
    setError("");
    setNotice("");
    try {
      const r = await api<{ created: number; updated: number; total_legacy: number }>(
        "/sdc/partner-qualification-tiers/import-legacy",
        { method: "POST" },
      );
      setNotice(`Importação: ${r.created} criadas, ${r.updated} atualizadas (${r.total_legacy} no SQL).`);
      await loadTiers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Importação falhou");
    }
  }

  async function submitTier(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setError("");
    try {
      await api("/sdc/partner-qualification-tiers", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          price_init: fd.get("price_init"),
          price_final: fd.get("price_final"),
          price_bonus: fd.get("price_bonus"),
          sort_order: Number(fd.get("sort_order") || 999),
        }),
      });
      e.currentTarget.reset();
      setNotice("Faixa criada.");
      await loadTiers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar faixa");
    }
  }

  async function runPreview() {
    if (!dateInit || !dateFinal) {
      setError("Informe data inicial e final.");
      return;
    }
    setError("");
    setNotice("");
    try {
      const rows = await api<FranchiseRow[]>("/sdc/partner-qualifications/appraisal/preview", {
        method: "POST",
        body: JSON.stringify({ date_init: dateInit, date_final: dateFinal }),
      });
      setFranchises(rows);
      setNotice("Apuração calculada (preview). Revise e clique em Aplicar qualificações.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Apuração falhou");
    }
  }

  async function applyAppraisal() {
    if (!dateInit || !dateFinal) {
      setError("Informe data inicial e final.");
      return;
    }
    setError("");
    try {
      const r = await api<{ franchises_updated: number }>("/sdc/partner-qualifications/appraisal/apply", {
        method: "POST",
        body: JSON.stringify({ date_init: dateInit, date_final: dateFinal }),
      });
      setNotice(`Qualificações aplicadas em ${r.franchises_updated} franquias.`);
      await loadFranchises();
      await loadHistory();
      await loadTiers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Aplicação falhou");
    }
  }

  async function clearPreview() {
    setError("");
    await api("/sdc/partner-qualifications/appraisal/clear-preview", { method: "POST" });
    await loadFranchises();
    setNotice("Preview de apuração limpo.");
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">SDC</span>
          <h1>Qualificação de parceiros</h1>
          <p>Faixas por faturamento SDC e bônus somado à % da franquia em vendas Capital de Giro.</p>
        </div>
        <div className="operational-icon"><Award /></div>
      </div>

      {notice && <div className="notice"><CheckCircle2 />{notice}</div>}
      {error && <div className="error">{error}</div>}

      <div className="marketplace-subtabs">
        <button type="button" className={tab === "tiers" ? "active" : ""} onClick={() => setTab("tiers")}>Faixas</button>
        <button type="button" className={tab === "appraisal" ? "active" : ""} onClick={() => setTab("appraisal")}>Apuração SDC</button>
        {tab === "tiers" && (
          <button type="button" className="table-action" onClick={() => void importLegacy()}>
            <RefreshCw /> Importar SQL legado
          </button>
        )}
      </div>

      {tab === "tiers" && (
        <>
          <section className="panel identity-table">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Faturamento (de — até)</th>
                  <th>Bônus %</th>
                  <th>Ativo</th>
                </tr>
              </thead>
              <tbody>
                {tiers.map((row) => (
                  <tr key={row.id}>
                    <td><b>{row.name}</b></td>
                    <td>{row.price_init} — {row.price_final}</td>
                    <td>{row.price_bonus}%</td>
                    <td>{row.active ? "Sim" : "Não"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section className="panel">
            <h2>Nova faixa</h2>
            <form className="stack-form grid-2" onSubmit={submitTier}>
              <input name="name" placeholder="Nome da faixa" required />
              <input name="price_init" type="number" step="0.01" min={0} placeholder="Valor inicial" required />
              <input name="price_final" type="number" step="0.01" min={0} placeholder="Valor final" required />
              <input name="price_bonus" type="number" step="0.01" min={0} max={100} placeholder="Bônus %" required />
              <input name="sort_order" type="number" defaultValue={999} />
              <button type="submit">Criar faixa</button>
            </form>
          </section>
        </>
      )}

      {tab === "appraisal" && (
        <>
          <section className="panel">
            <h2><Calculator /> Período da apuração</h2>
            <p className="muted">Soma vendas SDC aprovadas (crédito estimado) por franquia no período.</p>
            <div className="stack-form grid-2">
              <label>
                Data inicial
                <input type="date" value={dateInit} onChange={(e) => setDateInit(e.target.value)} />
              </label>
              <label>
                Data final
                <input type="date" value={dateFinal} onChange={(e) => setDateFinal(e.target.value)} />
              </label>
            </div>
            <div className="marketplace-subtabs" style={{ marginTop: 12 }}>
              <button type="button" className="table-action" onClick={() => void runPreview()}>Calcular apuração</button>
              <button type="button" className="table-action" onClick={() => void applyAppraisal()}>Aplicar qualificações</button>
              <button type="button" className="table-action" onClick={() => void clearPreview()}>Limpar preview</button>
            </div>
          </section>

          {history[0] && (
            <section className="panel">
              <small className="muted">
                Última apuração aplicada: {history[0].date_init} a {history[0].date_final}
              </small>
            </section>
          )}

          <section className="panel identity-table">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Franquia</th>
                  <th>E-mail</th>
                  <th>Valor apurado</th>
                  <th>Faixa (preview)</th>
                </tr>
              </thead>
              <tbody>
                {franchises.map((row) => (
                  <tr key={row.user_id}>
                    <td><b>{row.name}</b></td>
                    <td><small>{row.email}</small></td>
                    <td>{row.appraisal_amount}</td>
                    <td>{row.appraisal_tier_name || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </>
  );
}
