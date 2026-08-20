"use client";

import { Building2, Sparkles } from "lucide-react";
import { FormEvent, useState } from "react";

const API_URL = (process.env.NEXT_PUBLIC_API_URL?.trim() || "http://localhost:8000/api/v1").replace(/\s+/g, "");
const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type QuitConSim = {
  doc_version: string;
  saldo_devedor_bruto: string;
  meses_restantes: number;
  valor_presente_quitacao: string;
  elegibilidade: { elegivel: boolean; blockers: string[]; administradoras_whitelist: string[] };
  cedente: Record<string, string | number | boolean>;
  cessionario: Record<string, string | number | boolean>;
  compliance: Record<string, string | number>;
};

export default function QuitConPublicSimulatorPage() {
  const [result, setResult] = useState<QuitConSim | null>(null);
  const [error, setError] = useState("");

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    const f = new FormData(e.currentTarget);
    try {
      const res = await fetch(`${API_URL}/public/quitcon/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          outstanding_balance: f.get("outstanding_balance"),
          meses_restantes: Number(f.get("meses_restantes")),
          administrator_name: f.get("administrator_name"),
          operational_service: f.get("operational_service") === "on",
          contemplada: f.get("contemplada") === "on",
          bem_faturado: f.get("bem_faturado") === "on",
          parcelas_em_dia: f.get("parcelas_em_dia") === "on",
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail ?? "Falha na simulação");
      setResult(body);
    } catch (x) {
      setResult(null);
      setError(x instanceof Error ? x.message : "Falha na simulação");
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">SIMULADOR PÚBLICO</span>
          <h1>QuitCon — quitação inteligente de consórcio</h1>
          <p>Deflacionamento 1% a.m., taxas doc253 e elegibilidade por administradora whitelist.</p>
        </div>
        <div className="operational-icon"><Building2 /></div>
      </div>
      <section className="panel operational-panel">
        <form className="stack-form quitcon-public-form" onSubmit={(e) => void submit(e)}>
          <input name="outstanding_balance" type="number" min="1" step="0.01" placeholder="Saldo devedor bruto (R$)" required />
          <input name="meses_restantes" type="number" min="1" max="600" defaultValue={12} placeholder="Meses restantes" required />
          <select name="administrator_name" required defaultValue="Embracon">
            {["Embracon", "Ademicon", "HS", "Tradição", "Roma", "Reserva", "Groscon", "Recon", "Âncora"].map((x) => (
              <option key={x} value={x}>{x}</option>
            ))}
          </select>
          <label><input type="checkbox" name="contemplada" defaultChecked /> Cota contemplada e bem faturado</label>
          <label><input type="checkbox" name="bem_faturado" defaultChecked /> Bem faturado</label>
          <label><input type="checkbox" name="parcelas_em_dia" defaultChecked /> Parcelas em dia</label>
          <label><input type="checkbox" name="operational_service" /> Serviço operacional LETTER (+2%)</label>
          <button type="submit"><Sparkles /> Simular QuitCon</button>
        </form>
        {error && <div className="error">{error}</div>}
        {result && (
          <div className="sdc-quitcon-projection">
            <div className="sdc-quitcon-projection-head">
              <b>Quitação estimada: {brl.format(Number(result.valor_presente_quitacao))}</b>
              <small>Saldo bruto {brl.format(Number(result.saldo_devedor_bruto))} · {result.meses_restantes} meses</small>
              <small>Elegível: {result.elegibilidade.elegivel ? "Sim" : `Não (${result.elegibilidade.blockers.join(", ")})`}</small>
            </div>
            <div className="scenario-grid">
              <article><b>Cedente — intermediacao 3%</b><span>{brl.format(Number(result.cedente.taxa_intermediacao_3_porcento))}</span></article>
              <article><b>Cedente — líquido estimado</b><span>{brl.format(Number(result.cedente.valor_liquido_estimado_cedente))}</span></article>
              <article><b>Cessionário — capital de giro</b><span>{brl.format(Number(result.cessionario.capital_giro_liquido_estimado))}</span></article>
              <article><b>Taxa sucesso Escrow 10%</b><span>{brl.format(Number(result.cessionario.taxa_sucesso_escrow_10_porcento))}</span></article>
            </div>
            <small className="sdc-quitcon-compliance">Valores estimados. TAPAF R$ 1.500. SLA médio {result.compliance.sla_dias_estimados} dias.</small>
          </div>
        )}
      </section>
    </>
  );
}
