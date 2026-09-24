"use client";

import { Building2, Camera, CheckCircle2, Coins, Lock, ScrollText, Timer, Unlock } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, Proposal, QuitConOperacao } from "@/lib/api";
import { QuitConCustosEntradaPanel, QuitConCustosEntrada } from "@/components/quitcon-custos-entrada";
import { CurrencyInput } from "@/components/currency-input";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const ADMINS = ["Embracon", "Ademicon", "Ancora", "HS", "Tradicao", "Recon", "Groscon", "Roma", "Reserva"];

type QuotaFormFields = {
  group_code: string;
  quota_code: string;
  credit_at_billing: string;
  installment_value: string;
  meses_restantes: string;
  registry_office: string;
  operational_service: boolean;
  contemplada: boolean;
  bem_faturado: boolean;
  parcelas_em_dia: boolean;
};

const emptyQuotaForm = (): QuotaFormFields => ({
  group_code: "",
  quota_code: "",
  credit_at_billing: "",
  installment_value: "",
  meses_restantes: "",
  registry_office: "",
  operational_service: false,
  contemplada: true,
  bem_faturado: true,
  parcelas_em_dia: true,
});

function parseMoney(value: string): number {
  const raw = String(value || "").trim();
  if (!raw) return 0;
  if (raw.includes(",")) return Number(raw.replace(/\./g, "").replace(",", ".")) || 0;
  return Number(raw) || 0;
}

function quotaSaldo(fields: QuotaFormFields): number {
  const parcela = parseMoney(fields.installment_value);
  const meses = Number(fields.meses_restantes);
  if (!parcela || !Number.isFinite(meses) || meses < 1) return 0;
  return parcela * meses;
}

function quotaVp(saldo: number, meses: number): number {
  if (!saldo || meses < 1) return 0;
  return saldo / (1 + 0.01 * meses);
}

function registryFromQuota(fields: QuotaFormFields): string {
  const g = fields.group_code.trim();
  const c = fields.quota_code.trim();
  if (!g || !c) return "";
  return `${g}/${c}`;
}

function validateQuotaFields(fields: QuotaFormFields): string | null {
  if (!fields.group_code.trim() || !fields.quota_code.trim()) return "Informe grupo e cota.";
  if (!fields.registry_office.trim()) return "Informe a administradora.";
  const meses = Number(fields.meses_restantes);
  if (!Number.isFinite(meses) || meses < 1 || meses > 240) return "Informe o prazo restante (1–240 meses).";
  if (parseMoney(fields.installment_value) <= 0) return "Informe o valor da parcela atual.";
  if (parseMoney(fields.credit_at_billing) <= 0) return "Informe o valor do crédito quando faturou o bem.";
  if (quotaSaldo(fields) <= 0) return "Não foi possível calcular o saldo devedor (parcela × prazo).";
  return null;
}

const STATUSES = [
  "AGUARDANDO_TAPAF", "TAPAF_CHECKOUT_ACCEPTED", "TAPAF_LIQUIDADA", "EM_AUDITORIA_RISCO", "REPROVADO_COMPLIANCE",
  "AGUARDANDO_ASSINATURA", "PRONTO_PARA_CARTORIO", "EM_ANALISE_NO_RGI", "GRAVAME_CONCLUIDO",
  "ATIVO_OK_EM_PRODUCAO",
  "CANCELADO_INADIMPLENCIA_CESSIONARIO", "CANCELADO_DESISTENCIA_CEDENTE",
];

type QuitConTapafCheckout = {
  valor_tapaf_brl: string;
  manifesto_html: string;
  checkbox_obrigatorio_01: string;
  checkbox_obrigatorio_02: string;
  gateway_baas_pix_qrcode: string;
  botao_habilitado?: boolean;
  texto_tooltip?: string;
};

export function QuitConModule() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [operacoes, setOperacoes] = useState<QuitConOperacao[]>([]);
  const [selected, setSelected] = useState<QuitConOperacao | null>(null);
  const [message, setMessage] = useState("");
  const [financePreview, setFinancePreview] = useState<Record<string, unknown> | null>(null);
  const [tokenization, setTokenization] = useState<Record<string, unknown> | null>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const [photoMeta, setPhotoMeta] = useState<Array<{ filename: string; exif_timestamp_unix: number; gps_latitude: number; gps_longitude: number }>>([]);
  const [tapafCheckout, setTapafCheckout] = useState<QuitConTapafCheckout | null>(null);
  const [scrollDone, setScrollDone] = useState(false);
  const [cb1, setCb1] = useState(false);
  const [cb2, setCb2] = useState(false);
  const manifestRef = useRef<HTMLDivElement>(null);
  const manifestEndRef = useRef<HTMLDivElement>(null);
  const [operacaoForm, setOperacaoForm] = useState({
    proposal_id: "",
    appraisal_value: "",
    ...emptyQuotaForm(),
  });
  const [simForm, setSimForm] = useState(emptyQuotaForm());

  const operacaoPreview = useMemo(() => {
    const saldo = quotaSaldo(operacaoForm);
    const meses = Number(operacaoForm.meses_restantes);
    return { saldo, vp: quotaVp(saldo, meses), economia: saldo - quotaVp(saldo, meses) };
  }, [operacaoForm]);

  const simPreview = useMemo(() => {
    const saldo = quotaSaldo(simForm);
    const meses = Number(simForm.meses_restantes);
    return { saldo, vp: quotaVp(saldo, meses), economia: saldo - quotaVp(saldo, meses) };
  }, [simForm]);

  const evaluateManifestScroll = useCallback(() => {
    const el = manifestRef.current;
    if (!el) return;
    const remaining = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (remaining <= 24 || el.scrollHeight <= el.clientHeight + 1) setScrollDone(true);
  }, []);

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

  useEffect(() => {
    if (!selected || !["AGUARDANDO_TAPAF", "TAPAF_CHECKOUT_ACCEPTED"].includes(selected.status)) {
      setTapafCheckout(null);
      return;
    }
    setScrollDone(Boolean(selected.tapaf_scroll_completed));
    setCb1(Boolean(selected.tapaf_checkbox_1));
    setCb2(Boolean(selected.tapaf_checkbox_2));
    api<QuitConTapafCheckout>(`/finops/quitcon/tapaf-checkout?operacao_id=${selected.id}`, { method: "POST", body: "{}" })
      .then((c) => setTapafCheckout(c))
      .catch(() => setTapafCheckout(null));
  }, [selected?.id, selected?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!tapafCheckout?.manifesto_html) return;
    const el = manifestRef.current;
    const end = manifestEndRef.current;
    if (!el) return;
    const raf = requestAnimationFrame(evaluateManifestScroll);
    let observer: IntersectionObserver | undefined;
    if (end) {
      observer = new IntersectionObserver(
        (entries) => {
          if (entries.some((entry) => entry.isIntersecting)) setScrollDone(true);
        },
        { root: el, threshold: 0.25 },
      );
      observer.observe(end);
    }
    return () => {
      cancelAnimationFrame(raf);
      observer?.disconnect();
    };
  }, [tapafCheckout, evaluateManifestScroll]);

  async function createOperacao(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const err = validateQuotaFields(operacaoForm);
    if (err) {
      setMessage(err);
      return;
    }
    if (!operacaoForm.proposal_id) {
      setMessage("Selecione a proposta vinculada.");
      return;
    }
    const meses = Number(operacaoForm.meses_restantes);
    const saldo = quotaSaldo(operacaoForm);
    try {
      const item = await api<QuitConOperacao>("/finops/quitcon/operacoes", {
        method: "POST",
        body: JSON.stringify({
          proposal_id: operacaoForm.proposal_id,
          outstanding_balance: String(saldo),
          registry_number: registryFromQuota(operacaoForm),
          registry_office: operacaoForm.registry_office.trim(),
          appraisal_value: parseMoney(operacaoForm.appraisal_value) || undefined,
          meses_restantes: meses,
          operational_service: operacaoForm.operational_service,
          contemplada: operacaoForm.contemplada,
          bem_faturado: operacaoForm.bem_faturado,
          parcelas_em_dia: operacaoForm.parcelas_em_dia,
        }),
      });
      setMessage(`Operação ${item.operacao_code} criada — AGUARDANDO_TAPAF.`);
      setOperacaoForm({ proposal_id: "", appraisal_value: "", ...emptyQuotaForm() });
      await load();
      setSelected(item);
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha ao criar operação");
    }
  }

  async function acceptTapaf() {
    if (!selected) return;
    try {
      const item = await api<QuitConOperacao>("/finops/quitcon/tapaf-checkout-accept", {
        method: "POST",
        body: JSON.stringify({
          operacao_id: selected.id,
          scroll_completed: scrollDone,
          checkbox_1: cb1,
          checkbox_2: cb2,
        }),
      });
      setSelected(item);
      setMessage("Aceite TAPAF registrado — pagamento liberado.");
      await load();
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha no aceite TAPAF");
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
    const err = validateQuotaFields(simForm);
    if (err) {
      setMessage(err);
      return;
    }
    const meses = Number(simForm.meses_restantes);
    const saldo = quotaSaldo(simForm);
    try {
      setFinancePreview(await api<Record<string, unknown>>("/finops/quitcon/simulate", {
        method: "POST",
        body: JSON.stringify({
          outstanding_balance: String(saldo),
          meses_restantes: meses,
          administrator_name: simForm.registry_office.trim(),
          operational_service: simForm.operational_service,
          contemplada: simForm.contemplada,
          bem_faturado: simForm.bem_faturado,
          parcelas_em_dia: simForm.parcelas_em_dia,
        }),
      }));
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha simulação");
    }
  }

  function quotaFieldsBlock(
    fields: QuotaFormFields,
    onChange: (next: QuotaFormFields) => void,
    preview: { saldo: number; vp: number; economia: number },
  ) {
    return (
      <>
        <p className="muted" style={{ fontSize: 12, margin: 0, lineHeight: 1.45 }}>
          Informe grupo, cota, crédito no faturamento, parcela atual e prazo. O saldo devedor é calculado como parcela × meses
          (deflação VP 1% a.m. no doc253).
        </p>
        <div style={{ display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr" }}>
          <input
            placeholder="Grupo"
            value={fields.group_code}
            onChange={(e) => onChange({ ...fields, group_code: e.target.value })}
          />
          <input
            placeholder="Cota"
            value={fields.quota_code}
            onChange={(e) => onChange({ ...fields, quota_code: e.target.value })}
          />
          <CurrencyInput
            placeholder="Crédito quando faturou o bem"
            value={fields.credit_at_billing}
            onChange={(v) => onChange({ ...fields, credit_at_billing: v })}
          />
          <CurrencyInput
            placeholder="Parcela atual"
            value={fields.installment_value}
            onChange={(v) => onChange({ ...fields, installment_value: v })}
          />
          <input
            type="number"
            min={1}
            max={240}
            placeholder="Prazo restante (meses)"
            value={fields.meses_restantes}
            onChange={(e) => onChange({ ...fields, meses_restantes: e.target.value })}
          />
          <select
            value={fields.registry_office}
            onChange={(e) => onChange({ ...fields, registry_office: e.target.value })}
          >
            <option value="">Administradora</option>
            {ADMINS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        {preview.saldo > 0 && (
          <div style={{ fontSize: 12, fontWeight: 700, padding: "8px 10px", background: "#eef8f3", borderRadius: 8 }}>
            Saldo devedor: {brl.format(preview.saldo)} · VP quitação: {brl.format(preview.vp)} · Economia:{" "}
            {brl.format(preview.economia)}
          </div>
        )}
        <label><input type="checkbox" checked={fields.contemplada} onChange={(e) => onChange({ ...fields, contemplada: e.target.checked })} /> Contemplada</label>
        <label><input type="checkbox" checked={fields.bem_faturado} onChange={(e) => onChange({ ...fields, bem_faturado: e.target.checked })} /> Bem faturado</label>
        <label><input type="checkbox" checked={fields.parcelas_em_dia} onChange={(e) => onChange({ ...fields, parcelas_em_dia: e.target.checked })} /> Parcelas em dia</label>
        <label>
          <input
            type="checkbox"
            checked={fields.operational_service}
            onChange={(e) => onChange({ ...fields, operational_service: e.target.checked })}
          />
          Serviço operacional LETTER (+2% na abertura)
        </label>
      </>
    );
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
            <select
              value={operacaoForm.proposal_id}
              required
              onChange={(e) => setOperacaoForm((prev) => ({ ...prev, proposal_id: e.target.value }))}
            >
              <option value="">Proposta vinculada</option>
              {proposals.map((p) => <option key={p.id} value={p.id}>{p.product} · {p.id.slice(0, 8)}</option>)}
            </select>
            {quotaFieldsBlock(operacaoForm, (next) => setOperacaoForm((prev) => ({ ...prev, ...next })), operacaoPreview)}
            <CurrencyInput
              placeholder="Avaliação referência (R$, opcional)"
              value={operacaoForm.appraisal_value}
              onChange={(v) => setOperacaoForm((prev) => ({ ...prev, appraisal_value: v }))}
            />
            <button type="submit">Abrir operação AGUARDANDO_TAPAF</button>
          </form>
        </section>

        <section className="panel">
          <h2>Simulador QuitCon</h2>
          <form className="stack-form" onSubmit={simulateFinance}>
            {quotaFieldsBlock(simForm, setSimForm, simPreview)}
            <button type="submit">Simular doc253</button>
          </form>
          {financePreview && (
            <>
              {financePreview.custos_entrada && (
                <QuitConCustosEntradaPanel data={financePreview.custos_entrada as QuitConCustosEntrada} />
              )}
            <div className="finops-summary">
              <article><small>VP quitação</small><strong>{brl.format(Number(financePreview.valor_presente_quitacao ?? financePreview.meta_captacao_quitacao ?? 0))}</strong></article>
              <article><small>Cedente paga (VP + 3%)</small><strong>{brl.format(Number((financePreview.cedente as Record<string, string> | undefined)?.pagamento_total_quitacao_mais_intermediacao ?? financePreview.pagamento_total_cedente ?? 0))}</strong></article>
              <article><small>Taxa serviço 2% (abertura)</small><strong>{brl.format(Number((financePreview.cedente as Record<string, string> | undefined)?.taxa_servico_operacional_2_porcento_inicio ?? financePreview.taxa_servico_operacional_2_porcento ?? 0))}</strong></article>
              <article><small>Cessionário recebe (VP − 5%)</small><strong>{brl.format(Number((financePreview.cessionario as Record<string, string> | undefined)?.capital_giro_liquido_na_liberacao ?? financePreview.capital_giro_liquido_cessionario ?? financePreview.meta_captacao_quitacao ?? 0))}</strong></article>
              <article><small>Escrow 10%</small><strong>{brl.format(Number((financePreview.cessionario as Record<string, string> | undefined)?.taxa_sucesso_escrow_10_porcento ?? 0))}</strong></article>
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
            {tapafCheckout && ["AGUARDANDO_TAPAF", "TAPAF_CHECKOUT_ACCEPTED"].includes(selected.status) && (
              <section className="panel">
                <h3 className="tapaf-section-title">Manifesto TAPAF QuitCon</h3>
                <div ref={manifestRef} className="manifest-scroll" onScroll={() => evaluateManifestScroll()}>
                  <ScrollText size={18} />
                  <div className="manifest-body" dangerouslySetInnerHTML={{ __html: tapafCheckout.manifesto_html }} />
                  <div ref={manifestEndRef} className="manifest-end-sentinel" aria-hidden="true" />
                </div>
                {!scrollDone && <small className="form-help">Role o manifesto até o final para habilitar as declarações.</small>}
                <div className="tapaf-acceptance">
                  <h4>Declarações obrigatórias</h4>
                  <label className="tapaf-check">
                    <input type="checkbox" checked={cb1} disabled={!scrollDone} onChange={(e) => setCb1(e.target.checked)} />
                    <span>{tapafCheckout.checkbox_obrigatorio_01}</span>
                  </label>
                  <label className="tapaf-check">
                    <input type="checkbox" checked={cb2} disabled={!scrollDone} onChange={(e) => setCb2(e.target.checked)} />
                    <span>{tapafCheckout.checkbox_obrigatorio_02}</span>
                  </label>
                </div>
              </section>
            )}
            <div className="tapaf-actions">
              <button
                type="button"
                disabled={selected.status !== "AGUARDANDO_TAPAF" || !(scrollDone && cb1 && cb2)}
                onClick={() => void acceptTapaf()}
              >
                Registrar aceite TAPAF
              </button>
              <button type="button" disabled={selected.status !== "TAPAF_CHECKOUT_ACCEPTED"} onClick={() => void payTapaf()}>
                Pagar TAPAF R$ 1.500
              </button>
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
