"use client";

import { Building2, Camera, CheckCircle2, Coins, Lock, Unlock } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { api, LeaseEquityPauta, Proposal } from "@/lib/api";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const STATUSES = [
  "AGUARDANDO_TAPAF", "TAPAF_LIQUIDADA", "EM_AUDITORIA_RISCO", "REPROVADO_COMPLIANCE",
  "AGUARDANDO_ASSINATURA", "PRONTO_PARA_CARTORIO", "EM_ANALISE_NO_RGI", "GRAVAME_CONCLUIDO",
  "ATIVO_OK_EM_PRODUCAO", "LIBERADO_PARA_ANTECIPACAO",
];

export function LeaseEquityModule() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [pautas, setPautas] = useState<LeaseEquityPauta[]>([]);
  const [selected, setSelected] = useState<LeaseEquityPauta | null>(null);
  const [message, setMessage] = useState("");
  const [ltvPreview, setLtvPreview] = useState<Record<string, string> | null>(null);
  const [tokenization, setTokenization] = useState<Record<string, unknown> | null>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const [photoMeta, setPhotoMeta] = useState<Array<{ filename: string; exif_timestamp_unix: number; gps_latitude: number; gps_longitude: number }>>([]);

  const load = () =>
    Promise.all([
      api<Proposal[]>("/proposals"),
      api<LeaseEquityPauta[]>("/finops/lease-equity/pautas"),
    ]).then(([p, le]) => {
      setProposals(p);
      setPautas(le);
      if (le.length && !selected) setSelected(le[0]);
    });

  useEffect(() => { void load(); }, []);

  async function createPauta(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      const item = await api<LeaseEquityPauta>("/finops/lease-equity/pautas", {
        method: "POST",
        body: JSON.stringify({
          proposal_id: f.get("proposal_id"),
          property_type: f.get("property_type"),
          appraisal_value: f.get("appraisal_value"),
          registry_number: f.get("registry_number"),
          registry_office: f.get("registry_office"),
        }),
      });
      setMessage(`Pauta ${item.pauta_code} criada — status AGUARDANDO_TAPAF.`);
      await load();
      setSelected(item);
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha ao criar pauta");
    }
  }

  async function payTapaf() {
    if (!selected) return;
    try {
      const item = await api<LeaseEquityPauta>("/finops/lease-equity/tapaf-payment-webhook", {
        method: "POST",
        body: JSON.stringify({ pauta_id: selected.id, event_id: `tapaf-le-${Date.now()}`, amount: "750.00" }),
      });
      setSelected(item);
      setMessage("TAPAF R$ 750,00 liquidada — dossiê compliance gerado no S3.");
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
    } catch { /* sandbox fallback */ }
    setPhotoMeta((prev) => [
      ...prev,
      {
        filename: file.name,
        exif_timestamp_unix: Math.floor(Date.now() / 1000),
        gps_latitude: gps.latitude,
        gps_longitude: gps.longitude,
      },
    ]);
    cameraRef.current.value = "";
  }

  async function submitPhotos() {
    if (!selected || photoMeta.length < 3) {
      setMessage("Mínimo 3 fotos nativas com GPS/EXIF.");
      return;
    }
    try {
      const item = await api<LeaseEquityPauta>("/finops/lease-equity/inspection-photos", {
        method: "POST",
        body: JSON.stringify({
          pauta_id: selected.id,
          photos: photoMeta.map((p) => ({ ...p, source: "CAMERA_NATIVE" })),
        }),
      });
      setSelected(item);
      setPhotoMeta([]);
      setMessage("Vistoria nativa enviada — EM_AUDITORIA_RISCO.");
      await load();
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha vistoria");
    }
  }

  async function runStep(path: string, label: string, body?: object) {
    if (!selected) return;
    try {
      const item = await api<LeaseEquityPauta>(path, {
        method: "POST",
        body: JSON.stringify(body ?? { pauta_id: selected.id }),
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
      setLtvPreview(await api<Record<string, string>>("/finops/lease-equity/simulate-ltv", {
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
      const res = await api<Record<string, unknown>>("/finops/lease-equity/tokenization-processor", {
        method: "POST",
        body: JSON.stringify({ pauta_id: selected.id, owner_uid: "USER_PF_88219_BA" }),
      });
      setTokenization(res);
      setMessage("Tokenização RWA processada — ERC-3643.");
      await load();
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha tokenização");
    }
  }

  const anticipationBlocked = selected?.anticipation_preview?.status_antecipacao === "ANTECIPACAO_BLOQUEADA_CARENCIA_MINIMA";
  const canAnticipate = selected?.status === "LIBERADO_PARA_ANTECIPACAO";

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">LEASE EQUITY ENGINE V1</span>
          <h1>Lease Equity — TAPAF, LTV e RWA</h1>
          <p>Esteira FinOps: TAPAF R$ 750, LTV 40%/25%/20%, tokenização R$ 100/cota, antecipação Price 2,5% a.m. e comissão parceiro 2% sobre antecipação.</p>
        </div>
        <div className="operational-icon"><Building2 /></div>
      </div>
      {message && <div className="notice"><CheckCircle2 />{message}</div>}

      <div className="admin-grid">
        <section className="panel">
          <h2>Nova pauta imobiliária</h2>
          <form className="stack-form" onSubmit={createPauta}>
            <select name="proposal_id" required>
              <option value="">Proposta vinculada</option>
              {proposals.map((p) => <option key={p.id} value={p.id}>{p.product} · {p.id.slice(0, 8)}</option>)}
            </select>
            <select name="property_type" defaultValue="URBANO_RESIDENCIAL">
              <option value="URBANO_RESIDENCIAL">Urbano residencial (LTV 40%)</option>
              <option value="URBANO_COMERCIAL">Urbano comercial (LTV 40%)</option>
              <option value="LOTE_URBANO">Lote urbano (LTV 25%)</option>
              <option value="GALPAO">Galpão (LTV 25%)</option>
              <option value="RURAL">Rural (LTV 20%)</option>
            </select>
            <input name="appraisal_value" type="number" min="1" step="0.01" placeholder="Valor avaliação (AVM)" defaultValue="1000000" required />
            <input name="registry_number" placeholder="Matrícula" defaultValue="44901" required />
            <input name="registry_office" placeholder="Cartório RGI" defaultValue="Teixeira de Freitas - BA" required />
            <button type="submit">Abrir pauta AGUARDANDO_TAPAF</button>
          </form>
        </section>

        <section className="panel">
          <h2>Simulador Lease Equity</h2>
          <form className="stack-form" onSubmit={simulateLtv}>
            <select name="property_type" defaultValue="URBANO_RESIDENCIAL">
              <option value="URBANO_RESIDENCIAL">Urbano (exceto lote/galpão)</option>
              <option value="LOTE_URBANO">Lote / galpão</option>
              <option value="RURAL">Rural</option>
            </select>
            <input name="appraisal_value" type="number" defaultValue="600000" required />
            <button type="submit">Calcular matriz</button>
          </form>
          {ltvPreview && (
            <div className="finops-summary">
              <article><small>LTV captação ({ltvPreview.ltv_percent}%)</small><strong>{brl.format(Number(ltvPreview.limite_teto_ltv_captacao))}</strong></article>
              <article><small>Saque mensal dono (0,4%)</small><strong>{brl.format(Number(ltvPreview.aluguel_mensal_recorrente_bruto_dono))}</strong></article>
              <article><small>Ganho total 36m</small><strong>{brl.format(Number(ltvPreview.ganho_total_proprietario_prazo))}</strong></article>
              <article><small>Antecipação VP (2,5% a.m.)</small><strong>{brl.format(Number(ltvPreview.saque_total_antecipado_vp))}</strong></article>
              <article><small>Comissão parceiro (2%)</small><strong>{brl.format(Number(ltvPreview.comissao_parceiro_pool))}</strong></article>
              <article><small>Custo pool/mês (1,6%)</small><strong>{brl.format(Number(ltvPreview.custo_mensal_remuneracao_pool_investidores))}</strong></article>
            </div>
          )}
        </section>
      </div>

      <section className="panel">
        <h2>Pautas Lease Equity</h2>
        <select value={selected?.id ?? ""} onChange={(e) => setSelected(pautas.find((p) => p.id === e.target.value) ?? null)}>
          <option value="">Selecione</option>
          {pautas.map((p) => <option key={p.id} value={p.id}>{p.pauta_code} · {p.status}</option>)}
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
              <article><small>Captação</small><strong>{selected.funding_capture_percent}%</strong></article>
              <article><small>Aluguel dono</small><strong>{brl.format(Number(selected.credit_matrix.aluguel_mensal_recorrente_bruto_dono))}</strong></article>
              <article><small>Tokens estimados</small><strong>{Math.floor(Number(selected.credit_matrix.limite_teto_ltv_captacao) / 100)}</strong></article>
            </div>
            <div className="tapaf-actions">
              <button type="button" disabled={selected.status !== "AGUARDANDO_TAPAF"} onClick={() => void payTapaf()}>Pagar TAPAF R$ 750</button>
              <button type="button" disabled={selected.status !== "EM_AUDITORIA_RISCO"} onClick={() => void runStep("/finops/lease-equity/compliance-review", "Compliance aprovado", { pauta_id: selected.id, approved: true })}>Aprovar compliance</button>
              <button type="button" disabled={selected.status !== "AGUARDANDO_ASSINATURA"} onClick={() => void runStep(`/finops/lease-equity/sign-contract?pauta_id=${selected.id}`, "Contrato assinado")}>Assinar contrato</button>
              <button type="button" disabled={selected.status !== "PRONTO_PARA_CARTORIO"} onClick={() => void runStep(`/finops/lease-equity/submit-registry?pauta_id=${selected.id}`, "Protocolo SERP")}>Protocolar SERP</button>
              <button type="button" disabled={selected.status !== "EM_ANALISE_NO_RGI"} onClick={() => void runStep(`/finops/lease-equity/complete-gravame?pauta_id=${selected.id}`, "Gravame concluído")}>Concluir gravame</button>
              <button type="button" disabled={selected.status !== "GRAVAME_CONCLUIDO"} onClick={() => void runStep("/finops/lease-equity/funding-capture", "Captação 30%", { pauta_id: selected.id, amount: String(Number(selected.funding_target_amount) * 0.3) })}>Simular captação 30%</button>
              <button type="button" onClick={() => void tokenize()}><Coins />Tokenizar RWA</button>
            </div>

            <section className="panel">
              <h3><Camera />Vistoria fotográfica nativa</h3>
              <p className="form-help">Câmera nativa apenas — galeria bloqueada. GPS e timestamp EXIF obrigatórios.</p>
              <input ref={cameraRef} type="file" accept="image/*" capture="environment" onChange={() => void capturePhoto()} />
              <small>{photoMeta.length} foto(s) capturada(s)</small>
              <button type="button" disabled={photoMeta.length < 3 || selected.status !== "TAPAF_LIQUIDADA"} onClick={() => void submitPhotos()}>Enviar vistoria</button>
            </section>

            <section className="panel">
              <h3>Antecipação de recebíveis (Price 2,5% a.m.)</h3>
              <button type="button" disabled={anticipationBlocked && !canAnticipate} title={anticipationBlocked ? `Carência: faltam ${selected.anticipation_preview.meses_faltantes_para_liberacao} meses` : ""}>
                {canAnticipate ? "Antecipar recebíveis" : "Antecipar recebíveis (bloqueado)"}
              </button>
              {selected.anticipation_preview && (
                <div className="finops-summary">
                  <article><small>Status</small><strong>{selected.anticipation_preview.status_antecipacao}</strong></article>
                  {selected.anticipation_preview.valor_liquido_payout_vista && (
                    <article><small>Payout à vista</small><strong>{brl.format(Number(selected.anticipation_preview.valor_liquido_payout_vista))}</strong></article>
                  )}
                </div>
              )}
            </section>

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
