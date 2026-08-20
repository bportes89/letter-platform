"use client";

import { ArrowRight, CircleHelp, Loader2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { api, SdcQuitConIntegration, SdcStartQuitConResponse } from "@/lib/api";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export type SdcQuitConContext = {
  proposalId?: string;
  contractId?: string;
  calculationMemoryId?: string;
  mesesRestantes?: number;
};

function SdcQuitConAdvancePanel({
  data,
  context,
  onStarted,
}: {
  data: SdcQuitConIntegration;
  context: SdcQuitConContext;
  onStarted?: (result: SdcStartQuitConResponse) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [result, setResult] = useState<SdcStartQuitConResponse | null>(null);
  const [error, setError] = useState("");

  async function advance() {
    if (!confirmed || loading) return;
    if (!context.proposalId && !context.contractId) {
      setError("Vincule a proposta ou contrato SDC antes de avançar.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {
        confirmation: true,
        meses_restantes: context.mesesRestantes ?? data.card.meses_restantes_referencia,
      };
      if (context.proposalId) payload.proposal_id = context.proposalId;
      if (context.contractId) payload.contract_id = context.contractId;
      if (context.calculationMemoryId) payload.calculation_memory_id = context.calculationMemoryId;

      const res = await api<SdcStartQuitConResponse>("/finops/sdc/start-quitcon", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setResult(res);
      onStarted?.(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao abrir operação QuitCon");
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    return (
      <div className="sdc-quitcon-advance success">
        <b>{result.message}</b>
        <small>
          Operação <code>{result.operacao_code}</code> · {result.status.replaceAll("_", " ")}
        </small>
        <small>Próximo passo: TAPAF {brl.format(Number(result.tapaf_checkout.valor_tapaf_brl))}</small>
        <Link href={result.finops_route} className="sdc-quitcon-advance-link">
          Ir para FinOps QuitCon <ArrowRight />
        </Link>
      </div>
    );
  }

  return (
    <div className="sdc-quitcon-advance">
      <label className="sdc-quitcon-check">
        <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
        <span>
          Quero avançar com a quitação QuitCon no valor estimado de{" "}
          <strong>{brl.format(Number(data.card.quitacao_vista_quitcon_vp))}</strong> e iniciar a operação
          (TAPAF R$ 1.500,00).
        </span>
      </label>
      {error && <small className="sdc-quitcon-error">{error}</small>}
      <button type="button" className="sdc-quitcon-advance-btn" disabled={!confirmed || loading} onClick={() => void advance()}>
        {loading ? <Loader2 className="spin" /> : <ArrowRight />}
        Quero avançar com QuitCon
      </button>
    </div>
  );
}

export function SdcQuitConCard({
  data,
  context,
  onStarted,
}: {
  data: SdcQuitConIntegration;
  context?: SdcQuitConContext;
  onStarted?: (result: SdcStartQuitConResponse) => void;
}) {
  const [open, setOpen] = useState(false);
  const { card } = data;
  const paragraphs = card.modal.corpo.split("\n\n").filter(Boolean);

  return (
    <>
      <div className="sdc-quitcon-card">
        <div className="sdc-quitcon-card-head">
          <Sparkles />
          <span>Quitação Inteligente QuitCon</span>
        </div>
        <div className="sdc-quitcon-card-row">
          <small>Saldo Devedor Atual</small>
          <strong>{brl.format(Number(card.saldo_devedor_atual))}</strong>
        </div>
        <div className="sdc-quitcon-card-row highlight">
          <small>
            Quitação à Vista QuitCon
            <button type="button" className="sdc-quitcon-help" aria-label="Como funciona" onClick={() => setOpen(true)}>
              <CircleHelp />
            </button>
          </small>
          <strong>{brl.format(Number(card.quitacao_vista_quitcon_vp))}</strong>
        </div>
        <small className="sdc-quitcon-meta">
          Desconto de {card.taxa_desconto_mensal_percent}% a.m. · referência {card.meses_restantes_referencia} meses
        </small>
        {context && <SdcQuitConAdvancePanel data={data} context={context} onStarted={onStarted} />}
      </div>
      {open && (
        <div className="sdc-quitcon-modal-backdrop" onClick={() => setOpen(false)}>
          <div className="sdc-quitcon-modal" onClick={(e) => e.stopPropagation()}>
            <h4>{card.modal.titulo}</h4>
            {paragraphs.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
            <button type="button" onClick={() => setOpen(false)}>Entendi</button>
          </div>
        </div>
      )}
    </>
  );
}

export function SdcQuitConProjectionTable({
  data,
  context,
  onStarted,
}: {
  data: SdcQuitConIntegration;
  context?: SdcQuitConContext;
  onStarted?: (result: SdcStartQuitConResponse) => void;
}) {
  const { projecao_temporal: proj } = data;
  return (
    <div className="sdc-quitcon-projection">
      <div className="sdc-quitcon-projection-head">
        <span className="eyebrow dark">PROJEÇÃO QUITCON · DOC256</span>
        <b>Quitação acelerada — deflacionamento 1% a.m.</b>
        <small>Referência: {brl.format(Number(proj.saldo_devedor_referencia))} · {proj.formula}</small>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Prazo estimado</th>
              <th>Meses (n)</th>
              <th>Valor projetado QuitCon</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {proj.linhas.map((row) => (
              <tr key={row.prazo_meses}>
                <td><b>Quitação em {row.prazo_meses} meses</b></td>
                <td>{row.prazo_meses}</td>
                <td>{brl.format(Number(row.valor_quitcon_estimado_vp))}</td>
                <td>{row.status_operacao}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <small className="sdc-quitcon-compliance">{proj.nota_compliance_rodape}</small>
      {context && <SdcQuitConAdvancePanel data={data} context={context} onStarted={onStarted} />}
    </div>
  );
}
