"use client";

import { AlertCircle, CheckCircle2, FileSearch, HelpCircle, ScrollText } from "lucide-react";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api, Proposal } from "@/lib/api";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type TapafCheckout = {
  valor_nominal_taxa: string;
  gateway_baas_pix_qrcode: string;
  texto_explicativo_tooltip_interrogacao: string;
  checkbox_obrigatorio_01: string;
  checkbox_obrigatorio_02: string;
  manifesto_html: string;
  botao_habilitado: boolean;
  botao_label: string;
};

type TapafSettlement = {
  total_brl: string;
  lote_a_api_reserve_brl: string;
  lote_b_franchise_spread_brl: string;
  inventory: { providers: Array<{ code: string; name?: string; status: string; mode: string }> };
};

type Pauta = {
  id: string;
  proposal_id: string;
  pauta_code: string;
  status: string;
  documents: { submitted?: unknown[]; errors?: { code: string; label: string; reason: string }[] };
  tapaf_scroll_completed: boolean;
  tapaf_checkbox_1: boolean;
  tapaf_checkbox_2: boolean;
  tapaf_payment_reference: string | null;
  client_result: Record<string, unknown> | null;
  valid_stamp_hash: string | null;
};

const DOC_CODES = [
  { code: "EXTRATO_BANCARIO_6M", label: "Extratos bancários (6 meses)" },
  { code: "PGDAS_DRE", label: "PGDAS / DRE / Balanço" },
  { code: "DECORE_CRC", label: "DECORE eletrônica CRC" },
  { code: "MATRICULA_OU_CRLV", label: "Matrícula ou CRLV" },
  { code: "LAUDO_AVM", label: "Laudo AVM" },
];

const TAPAF_UI_STATUSES = new Set(["DOCUMENTS_OK", "TAPAF_CHECKOUT_ACCEPTED", "TAPAF_PAID"]);

export function PreAnalysisModule({ variant = "sdc" }: { variant?: "sdc" | "flash" }) {
  const productFilter = variant === "flash" ? "FLASH_CREDIT" : "SDC";
  const heading = variant === "flash"
    ? {
        eyebrow: "FLASH CAPITAL — COMPLIANCE",
        title: "Flash Capital — TAPAF, LTV e Valid-Stamp",
        subtitle: "TAPAF R$ 1.500,00 é obrigatória para emissão do Valid-Stamp. Após simular a proposta, valide documentos → TAPAF → selo.",
      }
    : {
        eyebrow: "SDC — ESTRUTURA INTERNA",
        title: "SDC — TAPAF, LTV e Valid-Stamp",
        subtitle: "Puxa automaticamente a proposta SDC: valida lastro (LTV), cobra TAPAF R$ 1.500,00 e emite selo Valid-Stamp após auditoria de renda.",
      };
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [proposalId, setProposalId] = useState("");
  const [pauta, setPauta] = useState<Pauta | null>(null);
  const [checkout, setCheckout] = useState<TapafCheckout | null>(null);
  const [message, setMessage] = useState("");
  const [scrollDone, setScrollDone] = useState(false);
  const [cb1, setCb1] = useState(false);
  const [cb2, setCb2] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const manifestRef = useRef<HTMLDivElement>(null);
  const manifestEndRef = useRef<HTMLDivElement>(null);

  const [apiReady, setApiReady] = useState<boolean | null>(null);
  const [settlement, setSettlement] = useState<TapafSettlement | null>(null);

  const evaluateManifestScroll = useCallback(() => {
    const el = manifestRef.current;
    if (!el) return;
    const remaining = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (remaining <= 24 || el.scrollHeight <= el.clientHeight + 1) setScrollDone(true);
  }, []);

  useEffect(() => {
    if (!checkout) return;
    setScrollDone(Boolean(pauta?.tapaf_scroll_completed));
    if (pauta?.tapaf_scroll_completed) {
      setCb1(Boolean(pauta.tapaf_checkbox_1));
      setCb2(Boolean(pauta.tapaf_checkbox_2));
    }

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
  }, [checkout, pauta?.tapaf_scroll_completed, pauta?.tapaf_checkbox_1, pauta?.tapaf_checkbox_2, evaluateManifestScroll]);

  const loadProposals = useCallback(
    () => api<Proposal[]>("/proposals").then((rows) => setProposals(rows.filter((p) => p.product === productFilter))),
    [productFilter],
  );
  useEffect(() => { void loadProposals(); }, [loadProposals]);

  useEffect(() => {
    api<{ features: { finops_pre_analysis_v6?: boolean } }>("/platform/capabilities")
      .then((caps) => setApiReady(Boolean(caps.features?.finops_pre_analysis_v6)))
      .catch(() => setApiReady(false));
  }, []);

  async function loadSettlement(pautaId: string) {
    try {
      setSettlement(await api<TapafSettlement>(
        `/finops/tapaf/settlements/lookup?entity_type=pre_analysis_pauta&entity_id=${encodeURIComponent(pautaId)}`,
      ));
    } catch {
      setSettlement(null);
    }
  }

  async function loadPauta(id: string) {
    if (!id) { setPauta(null); setSettlement(null); return; }
    try {
      const row = await api<Pauta>(`/finops/pre-analysis/${id}`);
      setPauta(row);
      if (row.status === "TAPAF_PAID") await loadSettlement(row.id);
      else setSettlement(null);
    } catch {
      setPauta(null);
      setSettlement(null);
    }
  }

  useEffect(() => { void loadPauta(proposalId); }, [proposalId]);

  const onManifestScroll = () => evaluateManifestScroll();

  async function validateDocs(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const documents = DOC_CODES.map(({ code }) => ({
      code,
      filename: String(f.get(`${code}_file`) || `${code}.pdf`),
      dpi: Number(f.get(`${code}_dpi`) || 300),
      present: f.get(`${code}_present`) === "on",
      illegible: f.get(`${code}_illegible`) === "on",
      rasurado: f.get(`${code}_rasurado`) === "on",
    }));
    try {
      const result = await api<Pauta>("/finops/pre-analysis/validate-documents", {
        method: "POST",
        body: JSON.stringify({ proposal_id: proposalId, documents }),
      });
      setPauta(result);
      setMessage(result.status === "DOCUMENTS_OK" ? "Fase 1 concluída — documentação validada." : "PENDING_DOCUMENTS — corrija os itens indicados.");
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha na validação OCR");
    }
  }

  async function loadTapafCheckout(preserveAcceptance = false) {
    try {
      const res = await api<{ interface_checkout_tapaf: TapafCheckout }>("/finops/pre-analysis/generate-tapaf", {
        method: "POST",
        body: JSON.stringify({ proposal_id: proposalId }),
      });
      setCheckout(res.interface_checkout_tapaf);
      if (!preserveAcceptance) {
        setScrollDone(false);
        setCb1(false);
        setCb2(false);
      }
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha ao carregar checkout TAPAF");
    }
  }

  async function openTapaf() {
    await loadTapafCheckout(false);
    setMessage("Checkout TAPAF carregado. Role o manifesto e marque as duas declarações.");
  }

  useEffect(() => {
    if (!proposalId || !pauta || !TAPAF_UI_STATUSES.has(pauta.status) || checkout) return;
    setScrollDone(Boolean(pauta.tapaf_scroll_completed));
    setCb1(Boolean(pauta.tapaf_checkbox_1));
    setCb2(Boolean(pauta.tapaf_checkbox_2));
    void loadTapafCheckout(true);
  }, [proposalId, pauta?.status, pauta?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function acceptCheckout() {
    try {
      const result = await api<Pauta>("/finops/pre-analysis/tapaf-checkout-accept", {
        method: "POST",
        body: JSON.stringify({ proposal_id: proposalId, scroll_completed: scrollDone, checkbox_1: cb1, checkbox_2: cb2 }),
      });
      setPauta(result);
      setMessage("Aceite registrado — botão de pagamento habilitado.");
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha no aceite TAPAF");
    }
  }

  async function payTapaf() {
    try {
      const result = await api<Pauta>("/finops/pre-analysis/tapaf-payment-webhook", {
        method: "POST",
        body: JSON.stringify({ proposal_id: proposalId, event_id: `tapaf-${Date.now()}`, amount: "1500.00" }),
      });
      setPauta(result);
      await loadSettlement(result.id);
      setMessage("TAPAF confirmada D+0 — split contábil 300/1200 e inventário sandbox executados.");
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha no pagamento TAPAF");
    }
  }

  async function runEngine() {
    const sampleExtratos: Record<string, { valor: number; tipo_credito: string; mesmo_titular_TED_bool: boolean }[]> = {};
    for (let m = 1; m <= 6; m++) {
      sampleExtratos[`2026-${String(m).padStart(2, "0")}`] = [
        { valor: 50000, tipo_credito: "PIX_RECEBIDO", mesmo_titular_TED_bool: false },
      ];
    }
    const proposal = proposals.find((p) => p.id === proposalId);
    const body = variant === "flash"
      ? {
          proposal_id: proposalId,
          asset_type: "REAL_ESTATE",
          extratos_6_meses_data: sampleExtratos,
          parcela_simulada: proposal ? String(Number(proposal.requested_amount) / 36) : "8000",
          valor_avaliacao_bem: proposal ? String(Number(proposal.requested_amount) / 0.35) : "1000000",
        }
      : {
          proposal_id: proposalId,
          adm_nome: "ANCORA",
          extratos_6_meses_data: sampleExtratos,
          parcela_simulada: "8000",
          valor_avaliacao_bem: "200000",
          saldo_devedor_cotas: "150000",
          ano_fabricacao_bem: 2020,
        };
    try {
      const res = await api<{ result: Record<string, unknown>; status: string }>("/finops/pre-analysis/run-engine", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setMessage(variant === "flash"
        ? `Flash Capital: ${String(res.result.status_core)}${res.result.Selo_LETTER_Valid_Stamp ? " — Valid-Stamp emitido" : ""}`
        : `Motor V6: ${String(res.result.status_core)}`);
      await loadPauta(proposalId);
    } catch (x) {
      setMessage(x instanceof Error ? x.message : "Falha no motor de pré-análise");
    }
  }

  const showTapafPhase = Boolean(pauta && TAPAF_UI_STATUSES.has(pauta.status));
  const canPay = pauta?.status === "TAPAF_CHECKOUT_ACCEPTED";
  const tapafPaid = pauta?.status === "TAPAF_PAID";
  const gateOpen = scrollDone && cb1 && cb2;
  const canRunEngine = tapafPaid;

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">{heading.eyebrow}</span>
          <h1>{heading.title}</h1>
          <p>{heading.subtitle}</p>
        </div>
        <div className="operational-icon"><FileSearch /></div>
      </div>
      {message && <div className="notice"><CheckCircle2 />{message}</div>}
      {apiReady === false && (
        <div className="notice warning"><AlertCircle />
          A API no Render ainda não foi atualizada com a pré-análise V6. No painel Render, abra o serviço <b>letter-api</b> → <b>Manual Deploy</b> → <b>Deploy latest commit</b> e aguarde 3–5 minutos.
        </div>
      )}

      <section className="panel">
        <h2>Fase 1 — Upload e triagem OCR</h2>
        <select value={proposalId} onChange={(e) => setProposalId(e.target.value)} required>
          <option value="">Selecione a proposta</option>
          {proposals.map((p) => <option key={p.id} value={p.id}>{p.product} · {brl.format(Number(p.requested_amount))}</option>)}
        </select>
        {pauta && (
          <p className="form-help">Pauta <b>{pauta.pauta_code}</b> · status <span className="pill">{pauta.status}</span></p>
        )}
        <form className="stack-form doc-check-grid" onSubmit={validateDocs}>
          {DOC_CODES.map(({ code, label }) => (
            <fieldset key={code} className="doc-check-card">
              <legend>{label}</legend>
              <div className="doc-check-row">
                <label><input type="checkbox" name={`${code}_present`} defaultChecked /> Documento presente</label>
                <label>DPI <input name={`${code}_dpi`} type="number" min="72" defaultValue="300" /></label>
                <label><input type="checkbox" name={`${code}_illegible`} /> Ilegível</label>
                <label><input type="checkbox" name={`${code}_rasurado`} /> Rasurado</label>
              </div>
            </fieldset>
          ))}
          <button disabled={!proposalId}>Validar documentação (OCR sandbox)</button>
        </form>
        {pauta?.documents?.errors && pauta.documents.errors.length > 0 && (
          <div className="notice warning"><AlertCircle />
            {pauta.documents.errors.map((err) => <div key={err.code}>{err.label}: {err.reason}</div>)}
          </div>
        )}
      </section>

      {showTapafPhase && (
        <section className="panel">
          <h2>Fase 2 — Checkout TAPAF</h2>
          {!checkout ? (
            <button type="button" onClick={() => void openTapaf()}>Abrir painel TAPAF</button>
          ) : (
            <div className="tapaf-checkout">
              {canPay && (
                <div className="notice"><CheckCircle2 />Aceite registrado. Clique em <b>{checkout.botao_label}</b> abaixo para confirmar o pagamento sandbox.</div>
              )}
              {tapafPaid && (
                <div className="notice"><CheckCircle2 />TAPAF paga — prossiga para a Fase 3 abaixo.</div>
              )}
              <div className="finops-summary tapaf-price">
                <article>
                  <small>Taxa nominal</small>
                  <strong>{brl.format(Number(checkout.valor_nominal_taxa))}</strong>
                  <button type="button" className="help-icon" title="Ajuda TAPAF" onMouseEnter={() => setShowTooltip(true)} onMouseLeave={() => setShowTooltip(false)} onClick={() => setShowTooltip((v) => !v)}>
                    <HelpCircle size={16} /> [?]
                  </button>
                  {showTooltip && <div className="tooltip-pop">{checkout.texto_explicativo_tooltip_interrogacao}</div>}
                </article>
              </div>

              <div>
                <h3 className="tapaf-section-title">Manifesto regulatório</h3>
                <div ref={manifestRef} className="manifest-scroll" onScroll={onManifestScroll}>
                  <ScrollText size={18} />
                  <div className="manifest-body" dangerouslySetInnerHTML={{ __html: checkout.manifesto_html }} />
                  <div ref={manifestEndRef} className="manifest-end-sentinel" aria-hidden="true" />
                </div>
                {!scrollDone && <small className="form-help">Role o manifesto até o final para habilitar as declarações abaixo.</small>}
                {scrollDone && <small className="form-help">Manifesto lido — marque as duas declarações abaixo.</small>}
              </div>

              <div className="tapaf-acceptance">
                <h4>Declarações obrigatórias</h4>
                <label className="tapaf-check">
                  <input type="checkbox" checked={cb1} disabled={!scrollDone} onChange={(e) => setCb1(e.target.checked)} />
                  <span>{checkout.checkbox_obrigatorio_01}</span>
                </label>
                <label className="tapaf-check">
                  <input type="checkbox" checked={cb2} disabled={!scrollDone} onChange={(e) => setCb2(e.target.checked)} />
                  <span>{checkout.checkbox_obrigatorio_02}</span>
                </label>
              </div>

              <div className="tapaf-actions">
                {!canPay && !tapafPaid && (
                  <button type="button" className="tapaf-btn-secondary" disabled={!gateOpen} onClick={() => void acceptCheckout()}>
                    Registrar aceite do manifesto
                  </button>
                )}
                <button type="button" className="tapaf-btn-primary" disabled={!canPay} onClick={() => void payTapaf()}>
                  {checkout.botao_label}
                </button>
              </div>
              {canPay && <small className="form-help">Pix sandbox: {checkout.gateway_baas_pix_qrcode.slice(0, 48)}…</small>}
            </div>
          )}
        </section>
      )}

      {settlement && (
        <section className="panel">
          <h2>Split TAPAF e inventário (NINA v4.0)</h2>
          <div className="finops-summary">
            <article><small>Total recebido</small><strong>{brl.format(Number(settlement.total_brl))}</strong></article>
            <article><small>Lote A — APIs</small><strong>{brl.format(Number(settlement.lote_a_api_reserve_brl))}</strong></article>
            <article><small>Lote B — spread</small><strong>{brl.format(Number(settlement.lote_b_franchise_spread_brl))}</strong></article>
            <article><small>Consultas disparadas</small><strong>{settlement.inventory.providers.length}</strong></article>
          </div>
          <ul className="form-help">
            {settlement.inventory.providers.map((p) => (
              <li key={p.code}>{p.code} · {p.status} · {p.mode}</li>
            ))}
          </ul>
        </section>
      )}

      {canRunEngine && (
        <section className="panel">
          <h2>Fase 3 — {variant === "flash" ? "Valid-Stamp Flash Capital (pós-TAPAF)" : "Motor Nina (pós-TAPAF)"}</h2>
          <button type="button" onClick={() => void runEngine()}>{variant === "flash" ? "Validar LTV e emitir Valid-Stamp" : "Executar MotorPreAnaliseFiduciariaV6"}</button>
        </section>
      )}

      {pauta?.client_result && (
        <section className="panel">
          <h2>Resultado para o cliente</h2>
          <pre className="code-block">{JSON.stringify(pauta.client_result, null, 2)}</pre>
          {pauta.valid_stamp_hash && <p className="form-help">Valid-Stamp: {pauta.valid_stamp_hash}</p>}
        </section>
      )}
    </>
  );
}
