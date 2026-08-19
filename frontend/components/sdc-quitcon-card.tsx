"use client";

import { CircleHelp, Sparkles } from "lucide-react";
import { useState } from "react";
import { SdcQuitConIntegration } from "@/lib/api";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export function SdcQuitConCard({ data }: { data: SdcQuitConIntegration }) {
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

export function SdcQuitConProjectionTable({ data }: { data: SdcQuitConIntegration }) {
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
    </div>
  );
}
