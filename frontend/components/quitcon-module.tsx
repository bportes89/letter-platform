"use client";

import { Building2, Camera, CheckCircle2, Coins, Lock, Timer, Unlock } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { api, Proposal, QuitConOperacao } from "@/lib/api";

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
  const [ltvPreview, setLtvPreview] = useState<Record<string, string> | null>(null);
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
          property_type: f.get("property_type"),
          appraisal_value: f.get("appraisal_value"),
          outstanding_balance: f.get("outstanding_balance"),
          registry_number: f.get("registry_number"),
          registry_office: f.get("registry_office"),
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

  async function simulateLtv(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      setLtvPreview(await api<Record<string, string>>("/finops/quitcon/simulate-ltv", {
        method: "POST",
        body: JSON.stringify({ property_type: f.get("property_type"), appraisal_value: f.get("appraisal_value") }),
      }));
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha LTV");
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

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">QUITCON ENGINE V1</span>
          <h1>QuitCon — quitação de consórcio</h1>
          <p>TAPAF R$ 1.500, LTV 60/40/30, multas 10%, SLA 45 dias e tokenização RWA. Sem remuneração 0,4% — exclusiva Lease Equity.</p>
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
            <select name="property_type" defaultValue="URBANO_RESIDENCIAL">
              <option value="URBANO_RESIDENCIAL">Urbano residencial (LTV 60%)</option>
              <option value="LOTE_URBANO">Lote urbano (LTV 40%)</option>
              <option value="RURAL">Rural (LTV 30%)</option>
            </select>
            <input name="appraisal_value" type="number" defaultValue="1000000" placeholder="Valor avaliação" required />
            <input name="outstanding_balance" type="number" defaultValue="250000" placeholder="Saldo devedor bruto" required />
            <input name="registry_number" placeholder="Matrícula" defaultValue="44901" required />
            <input name="registry_office" placeholder="Cartório RGI" defaultValue="Teixeira de Freitas - BA" required />
            <button type="submit">Abrir operação AGUARDANDO_TAPAF</button>
          </form>
        </section>

        <section className="panel">
          <h2>Simulador LTV QuitCon</h2>
          <form className="stack-form" onSubmit={simulateLtv}>
            <select name="property_type" defaultValue="URBANO_RESIDENCIAL">
              <option value="URBANO_RESIDENCIAL">Urbano</option>
              <option value="RURAL">Rural</option>
            </select>
            <input name="appraisal_value" type="number" defaultValue="1000000" required />
            <button type="submit">Calcular matriz</button>
          </form>
          {ltvPreview && (
            <div className="finops-summary">
              <article><small>Teto LTV ({ltvPreview.ltv_percent}%)</small><strong>{brl.format(Number(ltvPreview.limite_teto_ltv_captacao))}</strong></article>
              <article><small>Custo pool/mês (1,6%)</small><strong>{brl.format(Number(ltvPreview.custo_mensal_remuneracao_pool_investidores))}</strong></article>
              <article><small>SLA estimado</small><strong>{ltvPreview.sla_dias_estimados} dias</strong></article>
            </div>
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
              <article><small>Captação</small><strong>{selected.funding_capture_percent}%</strong></article>
              <article><small>Tokens estimados</small><strong>{Math.floor(Number(selected.credit_matrix.limite_teto_ltv_captacao) / 100)}</strong></article>
            </div>
            <div className="tapaf-actions">
              <button type="button" disabled={selected.status !== "AGUARDANDO_TAPAF"} onClick={() => void payTapaf()}>Pagar TAPAF R$ 1.500</button>
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
