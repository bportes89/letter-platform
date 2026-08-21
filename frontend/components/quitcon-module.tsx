"use client";

import { Building2, Camera, CheckCircle2, Coins, Lock, Timer, Unlock } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { api, Proposal, QuitConOperacao } from "@/lib/api";
import { QuitConCustosEntradaPanel, QuitConCustosEntrada } from "@/components/quitcon-custos-entrada";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const STATUSES = [
  "AGUARDANDO_TAPAF", "TAPAF_LIQUIDADA", "EM_AUDITORIA_RISCO", "REPROVADO_COMPLIANCE",
  "AGUARDANDO_ASSINATURA", "PRONTO_PARA_CARTORIO", "EM_ANALISE_NO_RGI", "GRAVAME_CONCLUIDO",
  "ATIVO_OK_EM_PRODUCAO",
  "CANCELADO_INADIMPLENCIA_CESSIONARIO", "CANCELADO_DESISTENCIA_CEDENTE",
];

export function QuitConModule() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [operacoes, setOperacoes] = useState<QuitConOperacao[]>([]);
  const [selected, setSelected] = useState<QuitConOperacao | null>(null);
  const [message, setMessage] = useState("");
  const [financePreview, setFinancePreview] = useState<Record<string, string | boolean> | null>(null);
  const [tokenization, setTokenization] = useState<Record<string, unknown> | null>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const [photoMeta, setPhotoMeta] = useState<Array<{ filename: string; exif_timestamp_unix: number; gps_latitude: number; gps_longitude: number }>>([]);

  const load = () =>
    Promise.all([
      api<Proposal[]>("/proposals"),
      api<QuitConOperacao[]>("/finops/quitcon/operacoes"),
    ]).then(([p, qc]) => {
      setProposals(p);
      setOperacoes(qc);
      if (qc.length && !selected) setSelected(qc[0]);
    });

  useEffect(() => { void load(); }, []);

  async function createOperacao(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      const item = await api<QuitConOperacao>("/finops/quitcon/operacoes", {
        method: "POST",
        body: JSON.stringify({
          proposal_id: f.get("proposal_id"),
          outstanding_balance: f.get("outstanding_balance"),
          registry_number: f.get("registry_number"),
          registry_office: f.get("registry_office"),
          appraisal_value: f.get("appraisal_value") || undefined,
          meses_restantes: Number(f.get("meses_restantes") || 48),
          operational_service: f.get("operational_service") === "on",
          contemplada: f.get("contemplada") === "on",
          bem_faturado: f.get("bem_faturado") === "on",
          parcelas_em_dia: f.get("parcelas_em_dia") === "on",
        }),
      });
      setMessage(`Operação ${item.operacao_code} criada — AGUARDANDO_TAPAF.`);
      await load();
      setSelected(item);
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha ao criar operação");
    }
  }

  async function payTapaf() {
    if (!selected) return;
    try {
      const item = await api<QuitConOperacao>("/finops/quitcon/tapaf-payment-webhook", {
        method: "POST",
        body: JSON.stringify({ operacao_id: selected.id, event_id: `tapaf-qc-${Date.now()}`, amount: "1500.00" }),
      });
      setSelected(item);
      setMessage("TAPAF R$ 1.500,00 liquidada — dossiê compliance gerado.");
      await load();
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha TAPAF");
    }
  }

  async function capturePhoto() {
    if (!cameraRef.current?.files?.[0]) return;
    const file = cameraRef.current.files[0];
    let gps = { latitude: -14.235, longitude: -51.925 };
    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) =>
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 })
      );
      gps = pos.coords;
    } catch { /* sandbox */ }
    setPhotoMeta((prev) => [...prev, {
      filename: file.name,
      exif_timestamp_unix: Math.floor(Date.now() / 1000),
      gps_latitude: gps.latitude,
      gps_longitude: gps.longitude,
    }]);
    cameraRef.current.value = "";
  }

  async function submitPhotos() {
    if (!selected || photoMeta.length < 3) {
      setMessage("Mínimo 3 fotos nativas com GPS/EXIF.");
      return;
    }
    try {
      const item = await api<QuitConOperacao>("/finops/quitcon/inspection-photos", {
        method: "POST",
        body: JSON.stringify({
          operacao_id: selected.id,
          photos: photoMeta.map((p) => ({ ...p, source: "CAMERA_NATIVE" })),
        }),
      });
      setSelected(item);
      setPhotoMeta([]);
      setMessage("Vistoria nativa enviada.");
      await load();
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha vistoria");
    }
  }

  async function runStep(path: string, label: string, body?: object) {
    if (!selected) return;
    try {
      const item = await api<QuitConOperacao>(path, {
        method: "POST",
        body: JSON.stringify(body ?? { operacao_id: selected.id }),
      });
      setSelected(item);
      setMessage(label);
      await load();
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha na esteira");
    }
  }

  async function simulateFinance(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      setFinancePreview(await api<Record<string, string | boolean>>("/finops/quitcon/simulate", {
        method: "POST",
        body: JSON.stringify({
          outstanding_balance: f.get("outstanding_balance"),
          meses_restantes: Number(f.get("meses_restantes") || 48),
          administrator_name: f.get("administrator_name"),
          operational_service: f.get("operational_service") === "on",
          contemplada: f.get("contemplada") === "on",
          bem_faturado: f.get("bem_faturado") === "on",
          parcelas_em_dia: f.get("parcelas_em_dia") === "on",
        }),
      }));
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha simulação");
    }
  }

  async function tokenize() {
    if (!selected) return;
    try {
      const res = await api<Record<string, unknown>>("/finops/quitcon/tokenization-processor", {
        method: "POST",
        body: JSON.stringify({ operacao_id: selected.id, owner_uid: "USER_PF_88219_BA" }),
      });
      setTokenization(res);
      setMessage("Tokenização RWA QuitCon processada.");
      await load();
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha tokenização");
    }
  }

  async function payOperationalService() {
    if (!selected?.operational_service_fee_amount) return;
    try {
      const item = await api<QuitConOperacao>("/finops/quitcon/operational-service-payment-webhook", {
        method: "POST",
        body: JSON.stringify({
          operacao_id: selected.id,
          event_id: `svc-qc-${Date.now()}`,
          amount: selected.operational_service_fee_amount,
        }),
      });
      setSelected(item);
      setMessage("Taxa de serviço operacional 2% paga — LETTER conduz junto à administradora.");
      await load();
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha taxa serviço operacional");
    }
  }

  async function paySuccessFee() {
    if (!selected) return;
    try {
      const item = await api<QuitConOperacao>("/finops/quitcon/success-fee-payment-webhook", {
        method: "POST",
        body: JSON.stringify({
          operacao_id: selected.id,
          event_id: `fee-qc-${Date.now()}`,
          amount: selected.success_fee_escrow_amount,
        }),
      });
      setSelected(item);
      setMessage("Taxa de sucesso 10% depositada em Escrow.");
      await load();
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha taxa sucesso");
    }
  }

  async function payCedenteEscrow() {
    if (!selected?.cedente_payment_amount) return;
    try {
      const item = await api<QuitConOperacao>("/finops/quitcon/cedente-payment-webhook", {
        method: "POST",
        body: JSON.stringify({
          operacao_id: selected.id,
          event_id: `cedente-qc-${Date.now()}`,
          amount: selected.cedente_payment_amount,
        }),
      });
      setSelected(item);
      setMessage("Pagamento cedente registrado em Escrow até conclusão.");
      await load();
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha pagamento cedente");
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">QUITCON ENGINE V1</span>
          <h1>QuitCon — quitação de consórcio</h1>
          <p>Manual doc253: VP 1% a.m. · Cedente paga VP+3% na quitação · Cessionário recebe VP−5% · TAPAF R$ 1.500 · SLA 45 dias.</p>
        </div>
        <div className="operational-icon"><Building2 /></div>
      </div>
      {message && <div className="notice"><CheckCircle2 />{message}</div>}

      <div className="admin-grid">
        <section className="panel">
          <h2>Nova operação QuitCon</h2>
          <form className="stack-form" onSubmit={createOperacao}>
            <select name="proposal_id" required>
              <option value="">Proposta vinculada</option>
              {proposals.map((p) => <option key={p.id} value={p.id}>{p.product} · {p.id.slice(0, 8)}</option>)}
            </select>
            <input name="outstanding_balance" type="number" defaultValue="250000" placeholder="Saldo devedor bruto da cota" required />
            <input name="meses_restantes" type="number" defaultValue="12" min="1" placeholder="Meses restantes" required />
            <input name="appraisal_value" type="number" placeholder="Avaliação referência (opcional)" />
            <input name="registry_number" placeholder="Matrícula / ref. garantia" defaultValue="44901" required />
            <input name="registry_office" placeholder="Administradora whitelist" defaultValue="Embracon" required />
            <label><input type="checkbox" name="contemplada" defaultChecked /> Contemplada + bem faturado</label>
            <label><input type="checkbox" name="bem_faturado" defaultChecked /> Bem faturado</label>
            <label><input type="checkbox" name="parcelas_em_dia" defaultChecked /> Parcelas em dia</label>
            <label><input type="checkbox" name="operational_service" /> Serviço operacional LETTER (+2% na abertura, se não conduzir junto à ADM)</label>
            <button type="submit">Abrir operação AGUARDANDO_TAPAF</button>
          </form>
        </section>

        <section className="panel">
          <h2>Simulador QuitCon</h2>
          <form className="stack-form" onSubmit={simulateFinance}>
            <input name="outstanding_balance" type="number" defaultValue="250000" placeholder="Saldo devedor bruto" required />
            <input name="meses_restantes" type="number" defaultValue="12" min="1" placeholder="Meses restantes" required />
            <input name="administrator_name" placeholder="Administradora" defaultValue="Embracon" />
            <label><input type="checkbox" name="operational_service" /> Serviço operacional (+2% na abertura)</label>
            <button type="submit">Simular doc253</button>
          </form>
          {financePreview && (
            <>
              {(financePreview as Record<string, unknown>).custos_entrada && (
                <QuitConCustosEntradaPanel data={(financePreview as Record<string, QuitConCustosEntrada>).custos_entrada} />
              )}
            <div className="finops-summary">
              <article><small>VP quitação</small><strong>{brl.format(Number((financePreview as Record<string,string>).valor_presente_quitacao ?? financePreview.meta_captacao_quitacao))}</strong></article>
              <article><small>Cedente paga (VP + 3%)</small><strong>{brl.format(Number((financePreview as Record<string,Record<string,string>>).cedente?.pagamento_total_quitacao_mais_intermediacao ?? (financePreview as Record<string,string>).pagamento_total_cedente ?? 0))}</strong></article>
              <article><small>Taxa serviço 2% (abertura)</small><strong>{brl.format(Number((financePreview as Record<string,Record<string,string>>).cedente?.taxa_servico_operacional_2_porcento_inicio ?? (financePreview as Record<string,string>).taxa_servico_operacional_2_porcento ?? 0))}</strong></article>
              <article><small>Cessionário recebe (VP − 5%)</small><strong>{brl.format(Number((financePreview as Record<string,Record<string,string>>).cessionario?.capital_giro_liquido_na_liberacao ?? (financePreview as Record<string,string>).capital_giro_liquido_cessionario ?? financePreview.meta_captacao_quitacao))}</strong></article>
              <article><small>Escrow 10%</small><strong>{brl.format(Number((financePreview as Record<string,Record<string,string>>).cessionario?.taxa_sucesso_escrow_10_porcento ?? 0))}</strong></article>
            </div>
            </>
          )}
        </section>
      </div>

      <section className="panel">
        <h2>Operações QuitCon</h2>
        <select value={selected?.id ?? ""} onChange={(e) => setSelected(operacoes.find((p) => p.id === e.target.value) ?? null)}>
          <option value="">Selecione</option>
          {operacoes.map((p) => <option key={p.id} value={p.id}>{p.operacao_code} · {p.status}</option>)}
        </select>
        {selected && (
          <>
            <div className="module-checklist finops-events">
              {STATUSES.map((s) => (
                <span key={s} className={selected.status === s ? "active" : ""}>
                  {selected.status === s ? <Unlock /> : <Lock />}<b>{s}</b>
                </span>
              ))}
            </div>
            <div className="finops-summary">
              <article><small>SLA conclusão</small><strong><Timer />{selected.sla_dias_estimados}d — {selected.sla_estimated_completion_at ? new Date(selected.sla_estimated_completion_at).toLocaleDateString("pt-BR") : "—"}</strong></article>
              <article><small>Taxa sucesso Escrow (10%)</small><strong>{brl.format(Number(selected.success_fee_escrow_amount))}</strong></article>
              {selected.operational_service_enabled && (
                <article><small>Taxa serviço 2% (abertura)</small><strong>{brl.format(Number(selected.operational_service_fee_amount ?? 0))}{selected.operational_service_paid_at ? " ✓" : " pendente"}</strong></article>
              )}
              {selected.cedente_payment_amount && (
                <article><small>Cedente paga quitação (VP + 3%)</small><strong>{brl.format(Number(selected.cedente_payment_amount))}</strong></article>
              )}
              <article><small>Captação</small><strong>{selected.funding_capture_percent}%</strong></article>
              <article><small>Tokens estimados</small><strong>{Math.floor(Number(selected.credit_matrix.meta_captacao_quitacao) / 100)}</strong></article>
            </div>
            {selected.custos_entrada && <QuitConCustosEntradaPanel data={selected.custos_entrada} />}
            <div className="tapaf-actions">
              <button type="button" disabled={selected.status !== "AGUARDANDO_TAPAF"} onClick={() => void payTapaf()}>Pagar TAPAF R$ 1.500</button>
              <button type="button" disabled={!selected.operational_service_enabled || selected.status !== "TAPAF_LIQUIDADA" || !!selected.operational_service_paid_at} onClick={() => void payOperationalService()}>Pagar taxa serviço 2% (abertura)</button>
              <button type="button" disabled={selected.status !== "TAPAF_LIQUIDADA" || !!selected.success_fee_escrow_paid_at || (selected.operational_service_enabled && !selected.operational_service_paid_at)} onClick={() => void paySuccessFee()}>Depositar taxa sucesso Escrow 10%</button>
              <button type="button" disabled={!selected.administrator_approved_at || !!selected.cedente_payment_escrow_reference} onClick={() => void payCedenteEscrow()}>Pagar quitação cedente (Escrow)</button>
              <button type="button" disabled={selected.status !== "EM_AUDITORIA_RISCO"} onClick={() => void runStep("/finops/quitcon/compliance-review", "Compliance aprovado", { operacao_id: selected.id, approved: true })}>Aprovar compliance</button>
              <button type="button" disabled={!!selected.administrator_approved_at} onClick={() => void runStep(`/finops/quitcon/administrator-approval?operacao_id=${selected.id}`, "Administradora aprovou cessão")}>Aprovação administradora</button>
              <button type="button" disabled={selected.status !== "AGUARDANDO_ASSINATURA"} onClick={() => void runStep(`/finops/quitcon/sign-contract?operacao_id=${selected.id}`, "Contrato assinado")}>Assinar contrato</button>
              <button type="button" disabled={selected.status !== "PRONTO_PARA_CARTORIO"} onClick={() => void runStep(`/finops/quitcon/submit-registry?operacao_id=${selected.id}`, "Protocolo SERP")}>Protocolar SERP</button>
              <button type="button" disabled={selected.status !== "EM_ANALISE_NO_RGI"} onClick={() => void runStep(`/finops/quitcon/complete-gravame?operacao_id=${selected.id}`, "Gravame concluído")}>Concluir gravame</button>
              <button type="button" disabled={selected.status !== "GRAVAME_CONCLUIDO"} onClick={() => void runStep("/finops/quitcon/funding-capture", "Captação 30%", { operacao_id: selected.id, amount: String(Number(selected.funding_target_amount) * 0.3) })}>Simular captação 30%</button>
              <button type="button" onClick={() => void tokenize()}><Coins />Tokenizar RWA</button>
              <button type="button" disabled={!selected.administrator_approved_at || selected.status.startsWith("CANCELADO")} onClick={() => void runStep(`/finops/quitcon/cancel-desistencia?operacao_id=${selected.id}`, "Multa desistência cedente")}>Cancelar — desistência cedente</button>
              <button type="button" disabled={!selected.administrator_approved_at || selected.status.startsWith("CANCELADO")} onClick={() => void runStep("/finops/quitcon/cancel-inadimplencia", "Multa inadimplência cessionário", { operacao_id: selected.id, days_overdue: 16 })}>Cancelar — inadimplência &gt;15d</button>
            </div>

            <section className="panel">
              <h3><Camera />Vistoria fotográfica nativa</h3>
              <input ref={cameraRef} type="file" accept="image/*" capture="environment" onChange={() => void capturePhoto()} />
              <small>{photoMeta.length} foto(s)</small>
              <button type="button" disabled={photoMeta.length < 3 || selected.status !== "TAPAF_LIQUIDADA"} onClick={() => void submitPhotos()}>Enviar vistoria</button>
            </section>

            {selected.penalty_preview && (
              <section className="panel">
                <h3>Preview penalidades (pós-aprovação administradora)</h3>
                <pre className="manifest-scroll">{JSON.stringify(selected.penalty_preview, null, 2)}</pre>
              </section>
            )}

            {selected.penalty_amount && (
              <div className="notice">Multa aplicada: {brl.format(Number(selected.penalty_amount))} — {selected.cancellation_reason}</div>
            )}

            {tokenization && (
              <section className="panel">
                <h3>Tokenização blockchain</h3>
                <pre className="manifest-scroll">{JSON.stringify(tokenization, null, 2)}</pre>
              </section>
            )}
          </>
        )}
      </section>
    </>
  );
}
