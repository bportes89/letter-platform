"use client";

import { CheckCircle2, FileUp, HelpCircle, Plus, RefreshCw, ShoppingCart, ClipboardList, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AdminDocumentPanel } from "@/components/admin-document-panel";
import { api, apiForm, deleteApi, downloadApi, User } from "@/lib/api";
import { isInternalProductRole } from "@/lib/product-nav";
import { PreAnalysisModule } from "@/components/pre-analysis-module";
import { DeskSourceMetaRow } from "@/lib/desk-source-meta";
import { PartnerSociosFields, SocioPartner, sociosPayload } from "@/components/partner-socios-fields";
import { CurrencyInput } from "@/components/currency-input";

type RequiredDoc = { code: string; label: string; uploaded?: boolean };

type SdcSolicitation = {
  id: string;
  status: string;
  status_label: string;
  status_notes: string | null;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  document: string | null;
  person_type: string;
  address: string | null;
  occupation: string | null;
  income_value: string;
  asset_type: string;
  asset_type_label: string;
  asset_value: string;
  asset_year: number | null;
  credit_estimated: string;
  installment_estimated: string;
  term_months: number;
  interest_rate_monthly: string;
  proposal_id: string | null;
  source_channel: string | null;
  source_channel_label: string | null;
  lead_id: string | null;
  documents: Array<{ id: string; doc_type: string; document_id?: string | null; filename?: string | null; status?: string | null; created_at: string | null }>;
  required_docs?: RequiredDoc[];
  docs_checklist_complete?: boolean;
  can_submit_documents?: boolean;
  can_create_sale: boolean;
};

type EvalSimRow = {
  credito: string;
  parcela_estimada: string;
  prazo_meses: number;
  taxa_juros_mensal: string;
};

type EvalResult = {
  viable: boolean;
  motivos: string[];
  credito_estimado: string;
  limite_maximo_credito?: string;
  credito_solicitado?: string | null;
  requested_exceeds_limit?: boolean;
  excesso_sobre_limite?: string | null;
  simulacao_limite?: EvalSimRow;
  simulacao_solicitada?: EvalSimRow | null;
  show_choice?: boolean;
  parcela_estimada: string;
  prazo_meses: number;
  taxa_juros_mensal: string;
  message: string;
  required_docs?: RequiredDoc[];
};

type TapafCheckoutUi = {
  valor_nominal_taxa: string;
  texto_explicativo_tooltip_interrogacao: string;
  checkbox_obrigatorio_01: string;
  checkbox_obrigatorio_02: string;
  manifesto_html: string;
  botao_habilitado?: boolean;
  botao_label?: string;
  checkout_url?: string | null;
  checkout_mode?: string;
  pix_copy_paste?: string;
};

type StoreResponse = SdcSolicitation & {
  tapaf_checkout?: TapafCheckoutUi;
  tapaf_proposal_id?: string;
};

type QuotaRow = {
  id: string;
  group_code: string;
  quota_code: string;
  category: string;
  credit_value: string;
  status: string;
};

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const ASSET_TYPES = [
  { value: "imovel", label: "Imóvel" },
  { value: "veiculo_leve", label: "Veículo leve" },
  { value: "veiculo_pesado", label: "Veículo pesado" },
  { value: "maquina", label: "Máquina" },
] as const;

const STATUS_OPTIONS = [
  { value: "AWAITING_DOCS", label: "Aguardando Documentação" },
  { value: "UNDER_REVIEW", label: "Em Análise" },
  { value: "PENDING", label: "Pendente" },
  { value: "APPROVED", label: "Aprovado" },
  { value: "REJECTED", label: "Reprovado" },
  { value: "CANCELLED", label: "Cancelado" },
] as const;

const emptyForm = {
  contact_name: "",
  contact_email: "",
  contact_phone: "",
  document: "",
  person_type: "PF",
  address: "",
  occupation: "",
  income_value: "",
  asset_type: "imovel",
  asset_value: "",
  asset_year: "",
  asset_paid_off: true,
  asset_has_lien: false,
  docs_complete: true,
  requested_leverage_amount: "",
  property_registry: "",
  vehicle_plate: "",
  vehicle_renavam: "",
  asset_street: "",
  asset_number: "",
  asset_city: "",
  asset_state: "",
  asset_zip: "",
};

function moneyPayload(value: string) {
  const raw = String(value || "").trim();
  if (!raw) return "0";
  if (raw.includes(",")) return raw.replace(/\./g, "").replace(",", ".");
  return raw;
}

type VehicleRow = { plate: string; renavam: string };

function composePropertyAddress(form: typeof emptyForm): string {
  const parts = [
    [form.asset_street.trim(), form.asset_number.trim()].filter(Boolean).join(", "),
    form.asset_city.trim(),
    form.asset_state.trim(),
    form.asset_zip.trim() ? `CEP ${form.asset_zip.trim()}` : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

function chosenCreditFromEval(result: EvalResult, choice: "limite" | "solicitada" | null): string {
  if (result.requested_exceeds_limit) {
    return result.simulacao_limite?.credito || result.limite_maximo_credito || result.credito_estimado;
  }
  if (result.show_choice && choice === "solicitada" && result.simulacao_solicitada) {
    return result.simulacao_solicitada.credito;
  }
  return result.simulacao_limite?.credito || result.limite_maximo_credito || result.credito_estimado;
}

export function SdcDeskModule() {
  const [tab, setTab] = useState<"nova" | "lista" | "venda">("nova");
  const [user, setUser] = useState<User | null>(null);
  const [items, setItems] = useState<SdcSolicitation[]>([]);
  const [quotas, setQuotas] = useState<QuotaRow[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [evalResult, setEvalResult] = useState<EvalResult | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saleQuotaId, setSaleQuotaId] = useState("");
  const [docType, setDocType] = useState("RG_CPF");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [socios, setSocios] = useState<SocioPartner[]>([]);
  const [matriculas, setMatriculas] = useState<string[]>([""]);
  const [vehicles, setVehicles] = useState<VehicleRow[]>([{ plate: "", renavam: "" }]);
  const [creditChoice, setCreditChoice] = useState<"limite" | "solicitada" | null>(null);
  const [tapafCheckout, setTapafCheckout] = useState<TapafCheckoutUi | null>(null);
  const [tapafProposalId, setTapafProposalId] = useState("");
  const [tapafScroll, setTapafScroll] = useState(false);
  const [tapafCb1, setTapafCb1] = useState(false);
  const [tapafCb2, setTapafCb2] = useState(false);
  const [showTapafTip, setShowTapafTip] = useState(false);

  const isInternal = isInternalProductRole(user?.role);
  const needsYear = ["veiculo_leve", "veiculo_pesado", "maquina"].includes(form.asset_type);
  const isImovel = form.asset_type === "imovel";
  const isVeiculo = form.asset_type === "veiculo_leve" || form.asset_type === "veiculo_pesado";
  const isMaquina = form.asset_type === "maquina";

  const load = useCallback(async () => {
    const [me, list, qs] = await Promise.all([
      api<User>("/auth/me"),
      api<SdcSolicitation[]>("/sdc/desk/solicitations"),
      api<QuotaRow[]>("/quotas"),
    ]);
    setUser(me);
    setItems(list);
    setQuotas(qs.filter((q) => q.status === "AVAILABLE"));
  }, []);

  useEffect(() => {
    setLoading(true);
    load()
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar mesa SDC"))
      .finally(() => setLoading(false));
  }, [load]);

  const filtered = useMemo(
    () => (statusFilter === "ALL" ? items : items.filter((i) => i.status === statusFilter)),
    [items, statusFilter],
  );
  const selected = useMemo(() => items.find((i) => i.id === selectedId) ?? null, [items, selectedId]);
  const approvedForSale = useMemo(() => items.filter((i) => i.can_create_sale), [items]);
  const sdcDocTypeOptions = useMemo(
    () =>
      (selected?.required_docs?.length
        ? selected.required_docs
        : [
            { code: "RG_CPF", label: "RG e CPF (ou CNH)" },
            { code: "COMPROVANTE_RENDA", label: "Comprovante de renda" },
            { code: "MATRICULA_ENOTARIADO", label: "Matrícula (e-notariado)" },
            { code: "LAUDO_AVALIACAO", label: "Laudo de avaliação" },
            { code: "SERASA", label: "Consulta Serasa" },
            { code: "BACEN", label: "Consulta Bacen" },
          ]
      ).map((d) => ({ value: d.code, label: d.label })),
    [selected],
  );

  useEffect(() => {
    if (!selected?.required_docs?.length) return;
    const firstMissing = selected.required_docs.find((d) => !d.uploaded)?.code;
    if (firstMissing) setDocType(firstMissing);
    else if (selected.required_docs[0]) setDocType(selected.required_docs[0].code);
  }, [selected?.id, selected?.required_docs]);

  function patchForm<K extends keyof typeof emptyForm>(key: K, value: (typeof emptyForm)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setEvalResult(null);
    setCreditChoice(null);
    setTapafCheckout(null);
    setTapafProposalId("");
  }

  function evaluatePayload() {
    const requested = form.requested_leverage_amount ? moneyPayload(form.requested_leverage_amount) : null;
    return {
      asset_type: form.asset_type,
      asset_value: moneyPayload(form.asset_value),
      asset_year: needsYear && form.asset_year ? Number(form.asset_year) : null,
      asset_paid_off: form.asset_paid_off,
      asset_has_lien: form.asset_has_lien,
      docs_complete: form.docs_complete,
      ...(requested && Number(requested) > 0 ? { requested_leverage_amount: requested } : {}),
    };
  }

  async function calculate() {
    setError("");
    setBusy(true);
    setTapafCheckout(null);
    setCreditChoice(null);
    try {
      const res = await api<{ result: EvalResult }>("/sdc/desk/evaluate", {
        method: "POST",
        body: JSON.stringify(evaluatePayload()),
      });
      setEvalResult(res.result);
      if (res.result.requested_exceeds_limit || !res.result.show_choice) {
        setCreditChoice("limite");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no cálculo");
    } finally {
      setBusy(false);
    }
  }

  function validateBeforeStore(): string | null {
    if (!form.contact_name.trim()) return "Informe o nome do cliente.";
    if (!form.contact_email.trim()) return "Informe o e-mail.";
    if (!form.contact_phone.trim()) return "Informe o telefone.";
    if (!form.document.trim()) return "Informe CPF/CNPJ.";
    if (!parseMoney(form.asset_value)) return "Informe o valor do bem.";
    if (!evalResult?.viable) return "Calcule a viabilidade antes de avançar.";
    if (evalResult.show_choice && !creditChoice) {
      return "No resultado da análise, escolha o limite máximo ou o valor solicitado.";
    }
    if (isImovel && !form.asset_street.trim()) return "Informe o logradouro do imóvel.";
    if (isImovel && !form.asset_city.trim()) return "Informe a cidade do imóvel.";
    return null;
  }

  function parseMoney(value: string): number {
    const n = Number(moneyPayload(value));
    return Number.isFinite(n) && n > 0 ? n : 0;
  }

  async function store() {
    const validation = validateBeforeStore();
    if (validation) {
      setError(validation);
      return;
    }
    if (!evalResult) return;
    const chosen = chosenCreditFromEval(evalResult, creditChoice);
    setError("");
    setBusy(true);
    try {
      const vehicleRows = vehicles
        .map((v) => ({ plate: v.plate.trim(), renavam: v.renavam.trim() }))
        .filter((v) => v.plate || v.renavam);
      const registryLines = matriculas.map((m) => m.trim()).filter(Boolean);
      const created = await api<StoreResponse>("/sdc/desk/solicitations", {
        method: "POST",
        body: JSON.stringify({
          ...evaluatePayload(),
          chosen_credit_amount: chosen,
          contact_name: form.contact_name.trim(),
          contact_email: form.contact_email.trim(),
          contact_phone: form.contact_phone.trim(),
          document: form.document.trim() || null,
          person_type: form.person_type,
          address: form.address.trim() || null,
          occupation: form.occupation.trim() || null,
          income_value: moneyPayload(form.income_value),
          requested_leverage_amount: form.requested_leverage_amount ? moneyPayload(form.requested_leverage_amount) : null,
          property_registry: isImovel && registryLines.length ? registryLines.join("\n") : null,
          vehicle_plate: isVeiculo && vehicleRows[0]?.plate ? vehicleRows[0].plate : null,
          vehicle_renavam: isVeiculo && vehicleRows[0]?.renavam ? vehicleRows[0].renavam : null,
          vehicles_json: isVeiculo ? vehicleRows : [],
          asset_full_address: isImovel ? composePropertyAddress(form) || null : null,
          partners_json: form.person_type === "PJ" ? sociosPayload(socios) : [],
        }),
      });
      setNotice(`SDC gravado: ${created.contact_name} — ${created.status_label}. Conclua o TAPAF no painel ao lado.`);
      if (created.tapaf_checkout) {
        setTapafCheckout(created.tapaf_checkout);
        setTapafProposalId(created.tapaf_proposal_id || "");
        setTapafScroll(false);
        setTapafCb1(false);
        setTapafCb2(false);
      }
      setSelectedId(created.id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao gravar solicitação");
    } finally {
      setBusy(false);
    }
  }

  async function acceptTapaf() {
    if (!tapafProposalId) return;
    setError("");
    setBusy(true);
    try {
      await api("/finops/pre-analysis/tapaf-checkout-accept", {
        method: "POST",
        body: JSON.stringify({
          proposal_id: tapafProposalId,
          scroll_completed: tapafScroll,
          checkbox_1: tapafCb1,
          checkbox_2: tapafCb2,
          asset_type: isVeiculo ? "VEHICLE" : "REAL_ESTATE",
        }),
      });
      const res = await api<{ interface_checkout_tapaf: TapafCheckoutUi }>("/finops/pre-analysis/generate-tapaf", {
        method: "POST",
        body: JSON.stringify({ proposal_id: tapafProposalId }),
      });
      setTapafCheckout(res.interface_checkout_tapaf);
      setNotice("Aceite TAPAF registrado. Clique em confirmar pagamento para gerar boleto/Pix.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no aceite TAPAF");
    } finally {
      setBusy(false);
    }
  }

  async function payTapaf() {
    if (!tapafProposalId) return;
    setError("");
    setBusy(true);
    try {
      if (tapafCheckout?.checkout_url && tapafCheckout.checkout_mode === "ASAAS") {
        window.open(tapafCheckout.checkout_url, "_blank", "noopener,noreferrer");
        setNotice("Cobrança aberta — aguarde confirmação do pagamento.");
        return;
      }
      await api("/finops/pre-analysis/tapaf-payment-webhook", {
        method: "POST",
        body: JSON.stringify({
          proposal_id: tapafProposalId,
          event_id: `sdc-desk-tapaf-${Date.now()}`,
          amount: tapafCheckout?.valor_nominal_taxa || "1500.00",
        }),
      });
      setNotice("TAPAF confirmada. Acompanhe o status na aba Acompanhamento.");
      setForm(emptyForm);
      setSocios([]);
      setMatriculas([""]);
      setVehicles([{ plate: "", renavam: "" }]);
      setEvalResult(null);
      setTapafCheckout(null);
      setTab("lista");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao gerar pagamento TAPAF");
    } finally {
      setBusy(false);
    }
  }

  async function updateStatus(item: SdcSolicitation, status: string) {
    setError("");
    setBusy(true);
    try {
      const updated = await api<SdcSolicitation>(`/sdc/desk/solicitations/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setNotice(`${updated.contact_name}: ${updated.status_label}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao atualizar status");
    } finally {
      setBusy(false);
    }
  }

  async function uploadDoc(item: SdcSolicitation, file: File, type = docType) {
    setError("");
    setBusy(true);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("doc_type", type);
      await apiForm(`/sdc/desk/solicitations/${item.id}/documents`, body);
      setNotice(`Documento anexado em ${item.contact_name}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no upload");
    } finally {
      setBusy(false);
    }
  }

  async function submitDocuments(item: SdcSolicitation) {
    setError("");
    setBusy(true);
    try {
      const updated = await api<SdcSolicitation>(`/sdc/desk/solicitations/${item.id}/submit-documents`, { method: "POST" });
      setNotice(`Documentação transmitida — ${updated.contact_name} em análise LETTER.`);
      setSelectedId(updated.id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Checklist incompleto ou transmissão indisponível.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteDoc(item: SdcSolicitation, docId: string) {
    setError("");
    setBusy(true);
    try {
      await deleteApi(`/sdc/desk/solicitations/${item.id}/documents/${docId}`);
      setNotice("Documento excluído.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao excluir documento");
    } finally {
      setBusy(false);
    }
  }

  async function createSale() {
    if (!selectedId || !saleQuotaId) return;
    setError("");
    setBusy(true);
    try {
      const res = await api<{ message: string; proposal_id: string }>(
        `/sdc/desk/solicitations/${selectedId}/sale`,
        { method: "POST", body: JSON.stringify({ quota_id: saleQuotaId }) },
      );
      setNotice(`${res.message} (proposta ${res.proposal_id})`);
      setSaleQuotaId("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao criar venda");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="loading">Carregando mesa SDC…</div>;

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">COMERCIAL</span>
          <h1>SDC — Capital de Giro</h1>
          <p>
            Solicitação com viabilidade → documentos/status → venda Cap Giro (somente Aprovado).
            Parceiro anexa docs; operação LETTER altera status.
          </p>
        </div>
        <div className="operational-icon"><ClipboardList /></div>
      </div>

      <section className="panel operational-panel">
        <div className="marketplace-tabs" style={{ gridTemplateColumns: "1fr 1fr 1fr" }}>
          <button type="button" className={`marketplace-tab${tab === "nova" ? " active" : ""}`} onClick={() => setTab("nova")}>
            1. Nova solicitação
          </button>
          <button type="button" className={`marketplace-tab${tab === "lista" ? " active" : ""}`} onClick={() => setTab("lista")}>
            2. Acompanhamento
          </button>
          <button type="button" className={`marketplace-tab${tab === "venda" ? " active" : ""}`} onClick={() => setTab("venda")}>
            3. Venda Cap Giro
          </button>
        </div>

        <div style={{ padding: "14px 18px", display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <button type="button" className="table-action" onClick={() => void load().catch((e) => setError(e.message))}>
            <RefreshCw />Atualizar
          </button>
          {tab === "lista" && (
            <>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, fontWeight: 700, color: "#52605a" }}>
                Status
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid var(--line)" }}>
                  <option value="ALL">Todos</option>
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, fontWeight: 700, color: "#52605a" }}>
                Tipo doc
                <select value={docType} onChange={(e) => setDocType(e.target.value)} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid var(--line)" }}>
                  {sdcDocTypeOptions.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                  <option value="SDC_SUPPORT">Apoio (opcional)</option>
                </select>
              </label>
            </>
          )}
        </div>

        {notice && <div className="notice" style={{ margin: "0 18px 12px" }}><CheckCircle2 />{notice}</div>}
        {error && <div className="error" style={{ margin: "0 18px 12px" }}>{error}</div>}

        {tab === "nova" && (
          <div style={{ padding: "0 18px 18px", display: "grid", gap: 16, gridTemplateColumns: "minmax(0,1.2fr) minmax(0,0.8fr)" }}>
            <div className="stack-form">
              <div style={{ display: "grid", gap: 9, gridTemplateColumns: "1fr 1fr" }}>
                <input placeholder="Nome" value={form.contact_name} onChange={(e) => patchForm("contact_name", e.target.value)} />
                <input placeholder="E-mail" value={form.contact_email} onChange={(e) => patchForm("contact_email", e.target.value)} />
                <input placeholder="Telefone" value={form.contact_phone} onChange={(e) => patchForm("contact_phone", e.target.value)} />
                <input placeholder="CPF/CNPJ" value={form.document} onChange={(e) => patchForm("document", e.target.value)} />
                <select
                  value={form.person_type}
                  onChange={(e) => {
                    const pt = e.target.value;
                    patchForm("person_type", pt);
                    if (pt === "PF") setSocios([]);
                  }}
                >
                  <option value="PF">PF</option>
                  <option value="PJ">PJ</option>
                </select>
                <input placeholder="Profissão / ramo" value={form.occupation} onChange={(e) => patchForm("occupation", e.target.value)} />
                <label>
                  Renda / faturamento (R$)
                  <CurrencyInput value={form.income_value} onChange={(v) => patchForm("income_value", v)} placeholder="R$ 0,00" />
                </label>
                <select value={form.asset_type} onChange={(e) => patchForm("asset_type", e.target.value)}>
                  {ASSET_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                <label>
                  Valor do bem (R$)
                  <CurrencyInput value={form.asset_value} onChange={(v) => patchForm("asset_value", v)} placeholder="R$ 0,00" />
                </label>
                {needsYear && (
                  <input type="number" placeholder="Ano fabricação" value={form.asset_year} onChange={(e) => patchForm("asset_year", e.target.value)} />
                )}
                <input style={{ gridColumn: "1 / -1" }} placeholder="Endereço resumido do cliente" value={form.address} onChange={(e) => patchForm("address", e.target.value)} />
                <label style={{ gridColumn: "1 / -1" }}>
                  Valor alavancagem solicitado (R$)
                  <CurrencyInput value={form.requested_leverage_amount} onChange={(v) => patchForm("requested_leverage_amount", v)} placeholder="R$ 0,00" />
                </label>
                {isImovel && (
                  <>
                    <label>
                      Logradouro
                      <input value={form.asset_street} onChange={(e) => patchForm("asset_street", e.target.value)} placeholder="Rua / avenida" />
                    </label>
                    <label>
                      Número
                      <input value={form.asset_number} onChange={(e) => patchForm("asset_number", e.target.value)} placeholder="Nº" />
                    </label>
                    <label>
                      CEP
                      <input value={form.asset_zip} onChange={(e) => patchForm("asset_zip", e.target.value)} placeholder="00000-000" inputMode="numeric" />
                    </label>
                    <label>
                      Cidade
                      <input value={form.asset_city} onChange={(e) => patchForm("asset_city", e.target.value)} placeholder="Cidade" />
                    </label>
                    <label>
                      UF
                      <input value={form.asset_state} onChange={(e) => patchForm("asset_state", e.target.value)} placeholder="MG" maxLength={2} />
                    </label>
                    <div className="desk-repeat-block">
                      <b>Matrícula(s) do imóvel</b>
                      <small className="muted">Informe uma matrícula por linha. Use + para incluir outra.</small>
                      {matriculas.map((line, idx) => (
                        <div key={idx} className="desk-repeat-row single-col">
                          <input
                            placeholder={`Matrícula ${idx + 1}`}
                            value={line}
                            onChange={(e) => {
                              const next = [...matriculas];
                              next[idx] = e.target.value;
                              setMatriculas(next);
                            }}
                          />
                          {matriculas.length > 1 && (
                            <button type="button" className="table-action" onClick={() => setMatriculas(matriculas.filter((_, i) => i !== idx))} aria-label="Remover matrícula">
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      ))}
                      <button type="button" className="table-action" onClick={() => setMatriculas([...matriculas, ""])}>
                        <Plus size={14} />
                        Adicionar matrícula
                      </button>
                    </div>
                  </>
                )}
                {isVeiculo && (
                  <div className="desk-repeat-block">
                    <b>Veículo(s)</b>
                    <small className="muted">Placa e RENAVAM de cada veículo. Use + para outro veículo.</small>
                    {vehicles.map((row, idx) => (
                      <div key={idx} className="desk-repeat-row">
                        <label>
                          Placa
                          <input
                            placeholder="ABC1D23"
                            value={row.plate}
                            onChange={(e) => {
                              const next = [...vehicles];
                              next[idx] = { ...next[idx], plate: e.target.value };
                              setVehicles(next);
                            }}
                          />
                        </label>
                        <label>
                          RENAVAM
                          <input
                            placeholder="RENAVAM"
                            value={row.renavam}
                            onChange={(e) => {
                              const next = [...vehicles];
                              next[idx] = { ...next[idx], renavam: e.target.value };
                              setVehicles(next);
                            }}
                          />
                        </label>
                        {vehicles.length > 1 && (
                          <button type="button" className="table-action" onClick={() => setVehicles(vehicles.filter((_, i) => i !== idx))} aria-label="Remover veículo">
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    ))}
                    <button type="button" className="table-action" onClick={() => setVehicles([...vehicles, { plate: "", renavam: "" }])}>
                      <Plus size={14} />
                      Adicionar veículo
                    </button>
                  </div>
                )}
                {isMaquina && (
                  <p className="muted" style={{ gridColumn: "1 / -1", fontSize: 11, margin: 0 }}>
                    Máquina/equipamento: use ano de fabricação e valor do bem. Não exige matrícula de imóvel nem placa.
                  </p>
                )}
              </div>
              {form.person_type === "PJ" && <PartnerSociosFields value={socios} onChange={setSocios} />}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 14, fontSize: 12, fontWeight: 700 }}>
                <label><input type="checkbox" checked={form.asset_paid_off} onChange={(e) => patchForm("asset_paid_off", e.target.checked)} /> Bem quitado</label>
                <label><input type="checkbox" checked={form.asset_has_lien} onChange={(e) => patchForm("asset_has_lien", e.target.checked)} /> Bem com pendência</label>
                <label><input type="checkbox" checked={form.docs_complete} onChange={(e) => patchForm("docs_complete", e.target.checked)} /> Documentação completa</label>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="admin-button" disabled={busy} onClick={() => void calculate()}>Calcular viabilidade</button>
              </div>
            </div>
            <div style={{ border: "1px solid var(--line)", borderRadius: 12, padding: 16, background: "#f7fbf9" }}>
              <b>Resultado da análise</b>
              {!evalResult && !tapafCheckout && <p className="muted" style={{ marginTop: 10 }}>Preencha e clique em Calcular viabilidade.</p>}
              {evalResult?.required_docs?.length && !tapafCheckout && (
                <p className="muted" style={{ fontSize: 10, marginTop: 8 }}>
                  Após gravar, na aba Acompanhamento você anexará {evalResult.required_docs.length} documentos do checklist ({form.asset_type === "imovel" ? "imóvel" : "bem"}).
                </p>
              )}
              {evalResult?.viable && !tapafCheckout && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
                  {evalResult.simulacao_limite && (
                    <div
                      style={{
                        border: creditChoice === "limite" || !evalResult.show_choice ? "2px solid var(--green-dark)" : "1px solid var(--line)",
                        borderRadius: 10,
                        padding: 12,
                        background: "#fff",
                      }}
                    >
                      <b style={{ fontSize: 11 }}>Limite máximo com o bem</b>
                      <div style={{ display: "grid", gap: 8, marginTop: 8, gridTemplateColumns: "1fr 1fr" }}>
                        <div><small>Valor alavancável</small><div><b>{brl.format(Number(evalResult.simulacao_limite.credito))}</b></div></div>
                        <div><small>Parcela estimada</small><div><b>{brl.format(Number(evalResult.simulacao_limite.parcela_estimada))}</b></div></div>
                        <div><small>Prazo estimado</small><div><b>{evalResult.simulacao_limite.prazo_meses} meses</b></div></div>
                        <div><small>Taxa estimada</small><div><b>{evalResult.simulacao_limite.taxa_juros_mensal}% a.m.</b></div></div>
                      </div>
                      {evalResult.show_choice && (
                        <button type="button" className="table-action" style={{ marginTop: 10 }} onClick={() => setCreditChoice("limite")}>
                          Escolher limite máximo
                        </button>
                      )}
                      {!evalResult.show_choice && (
                        <button type="button" className="admin-button" style={{ marginTop: 10, width: "100%" }} disabled={busy} onClick={() => void store()}>
                          Avançar com este valor
                        </button>
                      )}
                    </div>
                  )}
                  {evalResult.simulacao_solicitada && (
                    <div
                      style={{
                        border: creditChoice === "solicitada" ? "2px solid var(--green-dark)" : "1px solid var(--line)",
                        borderRadius: 10,
                        padding: 12,
                        background: "#fff",
                      }}
                    >
                      <b style={{ fontSize: 11 }}>Valor solicitado na simulação</b>
                      <div style={{ display: "grid", gap: 8, marginTop: 8, gridTemplateColumns: "1fr 1fr" }}>
                        <div><small>Valor desejado</small><div><b>{brl.format(Number(evalResult.simulacao_solicitada.credito))}</b></div></div>
                        <div><small>Parcela estimada</small><div><b>{brl.format(Number(evalResult.simulacao_solicitada.parcela_estimada))}</b></div></div>
                        <div><small>Prazo estimado</small><div><b>{evalResult.simulacao_solicitada.prazo_meses} meses</b></div></div>
                        <div><small>Taxa estimada</small><div><b>{evalResult.simulacao_solicitada.taxa_juros_mensal}% a.m.</b></div></div>
                      </div>
                      <button type="button" className="table-action" style={{ marginTop: 10 }} onClick={() => setCreditChoice("solicitada")}>
                        Escolher valor solicitado
                      </button>
                    </div>
                  )}
                  {evalResult.requested_exceeds_limit && (
                    <p style={{ color: "#b45309", fontSize: 11, lineHeight: 1.45, margin: 0 }}>{evalResult.message}</p>
                  )}
                  {!evalResult.requested_exceeds_limit && evalResult.message && (
                    <p style={{ color: "#067647", fontWeight: 700, fontSize: 11, margin: 0 }}>{evalResult.message}</p>
                  )}
                  {evalResult.show_choice && creditChoice && (
                    <button type="button" className="admin-button" disabled={busy} onClick={() => void store()}>
                      Avançar com {creditChoice === "solicitada" ? "valor solicitado" : "limite máximo"}
                    </button>
                  )}
                </div>
              )}
              {evalResult && !evalResult.viable && (
                <div style={{ marginTop: 12 }}>
                  <p style={{ color: "#b42318", fontWeight: 700 }}>{evalResult.message}</p>
                  <ul>{evalResult.motivos.map((m) => <li key={m}>{m}</li>)}</ul>
                </div>
              )}
              {tapafCheckout && (
                <div className="tapaf-checkout" style={{ marginTop: 14 }}>
                  <b>TAPAF — taxa de abertura</b>
                  <div className="finops-summary tapaf-price" style={{ marginTop: 10 }}>
                    <article>
                      <small>Taxa nominal</small>
                      <strong>{brl.format(Number(tapafCheckout.valor_nominal_taxa))}</strong>
                      <button type="button" className="help-icon" onClick={() => setShowTapafTip((v) => !v)} aria-label="O que é TAPAF">
                        <HelpCircle size={16} /> ?
                      </button>
                      {showTapafTip && (
                        <div className="tooltip-pop">{tapafCheckout.texto_explicativo_tooltip_interrogacao}</div>
                      )}
                    </article>
                  </div>
                  <div className="manifest-scroll" style={{ maxHeight: 120 }} dangerouslySetInnerHTML={{ __html: tapafCheckout.manifesto_html }} />
                  <label className="tapaf-check">
                    <input type="checkbox" checked={tapafScroll} onChange={(e) => setTapafScroll(e.target.checked)} />
                    <span>Li o manifesto TAPAF até o final.</span>
                  </label>
                  <label className="tapaf-check">
                    <input type="checkbox" checked={tapafCb1} onChange={(e) => setTapafCb1(e.target.checked)} />
                    <span>{tapafCheckout.checkbox_obrigatorio_01}</span>
                  </label>
                  <label className="tapaf-check">
                    <input type="checkbox" checked={tapafCb2} onChange={(e) => setTapafCb2(e.target.checked)} />
                    <span>{tapafCheckout.checkbox_obrigatorio_02}</span>
                  </label>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <button type="button" className="admin-button" disabled={busy || !tapafScroll || !tapafCb1 || !tapafCb2} onClick={() => void acceptTapaf()}>
                      Aceitar TAPAF e gerar boleto/Pix
                    </button>
                    {(tapafCheckout.botao_habilitado || tapafCheckout.checkout_url) && (
                      <button type="button" className="admin-button" disabled={busy} onClick={() => void payTapaf()}>
                        {tapafCheckout.botao_label || "Gerar boleto / Pix TAPAF"}
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "lista" && (
          <div style={{ padding: "0 18px 18px", overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cliente</th>
                  <th>Bem</th>
                  <th>Crédito est.</th>
                  <th>Status</th>
                  <th>Docs</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id} style={selectedId === item.id ? { background: "#f2faf6" } : undefined}>
                    <td>
                      <button type="button" className="table-action" style={{ padding: 0, background: "none", color: "var(--green-dark)" }} onClick={() => setSelectedId(item.id)}>
                        {item.contact_name}
                      </button>
                      <div className="muted" style={{ fontSize: 11 }}>{item.contact_email}</div>
                      <DeskSourceMetaRow
                        channel={item.source_channel}
                        label={item.source_channel_label}
                        leadId={item.lead_id}
                      />
                    </td>
                    <td>
                      {item.asset_type_label}
                      <div className="muted" style={{ fontSize: 11 }}>{brl.format(Number(item.asset_value))}</div>
                    </td>
                    <td>{brl.format(Number(item.credit_estimated))}</td>
                    <td>{item.status_label}</td>
                    <td>
                      {(item.required_docs?.filter((d) => d.uploaded).length ?? item.documents.length)}
                      /{item.required_docs?.length ?? "—"}
                    </td>
                    <td style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                      {isInternal && (
                        <select
                          value={item.status}
                          disabled={busy}
                          onChange={(e) => void updateStatus(item, e.target.value)}
                          style={{ padding: "6px 8px", borderRadius: 8, border: "1px solid var(--line)", fontSize: 11 }}
                        >
                          {STATUS_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                        </select>
                      )}
                      <label className="table-action" style={{ cursor: "pointer" }}>
                        <FileUp />
                        <input
                          type="file"
                          hidden
                          onChange={(e) => {
                            const f = e.target.files?.[0];
                            if (f) void uploadDoc(item, f, docType);
                            e.target.value = "";
                          }}
                        />
                      </label>
                      {item.can_create_sale && (
                        <button
                          type="button"
                          className="table-action"
                          onClick={() => {
                            setSelectedId(item.id);
                            setTab("venda");
                          }}
                        >
                          <ShoppingCart />Venda
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {selected && (
              <div className="notice" style={{ marginTop: 14 }}>
                <b>Detalhe — {selected.contact_name}</b>
                <div>
                  {selected.asset_type_label} · crédito {brl.format(Number(selected.credit_estimated))} · parcela{" "}
                  {brl.format(Number(selected.installment_estimated))} · {selected.term_months}m @ {selected.interest_rate_monthly}%
                </div>
                {selected.proposal_id && <div>Proposta: {selected.proposal_id}</div>}
                <DeskSourceMetaRow
                  channel={selected.source_channel}
                  label={selected.source_channel_label}
                  leadId={selected.lead_id}
                />
                <div style={{ marginTop: 12 }}>
                  <b style={{ fontSize: 12 }}>Checklist documental ({selected.asset_type_label}{selected.person_type === "PJ" ? " · PJ" : ""})</b>
                  <p className="muted" style={{ fontSize: 11, margin: "6px 0 8px" }}>
                    Anexe cada item do checklist. O botão <em>Transmitir documentação</em> só libera quando todos estiverem marcados.
                  </p>
                  <ul style={{ margin: "0 0 12px", paddingLeft: 18, fontSize: 11, lineHeight: 1.5 }}>
                    {(selected.required_docs ?? []).map((d) => (
                      <li key={d.code} style={{ color: d.uploaded ? "#067647" : "#52605a" }}>
                        {d.uploaded ? "✓" : "○"} {d.label}
                      </li>
                    ))}
                  </ul>
                  {!isInternal && selected.status === "AWAITING_DOCS" && (
                    <button
                      type="button"
                      className="admin-button"
                      style={{ marginBottom: 12 }}
                      disabled={busy || !selected.can_submit_documents}
                      onClick={() => void submitDocuments(selected)}
                    >
                      Transmitir documentação para análise
                    </button>
                  )}
                  {selected.status === "AWAITING_DOCS" && !selected.can_submit_documents && (
                    <p className="muted" style={{ fontSize: 10, margin: "0 0 10px" }}>
                      Faltam itens do checklist — anexe todos os tipos obrigatórios antes de transmitir.
                    </p>
                  )}
                </div>
                <AdminDocumentPanel
                  title={`Arquivos anexados (${selected.documents.length})`}
                  hint="Escolha o tipo do checklist no seletor e anexe o arquivo correspondente."
                  documents={selected.documents}
                  busy={busy}
                  canDelete={isInternal}
                  docTypeOptions={[...sdcDocTypeOptions, { value: "SDC_SUPPORT", label: "Documento de apoio (opcional)" }]}
                  defaultDocType={docType}
                  onUpload={(file, type) => uploadDoc(selected, file, type || docType)}
                  onDownload={(doc) => downloadApi(`/documents/${doc.document_id}/download`, doc.filename || "documento")}
                  onDelete={(doc) => deleteDoc(selected, doc.id)}
                />
              </div>
            )}
          </div>
        )}

        {tab === "venda" && (
          <div style={{ padding: "0 18px 18px" }} className="stack-form">
            <p className="muted">Disponível somente para SDCs Aprovados sem proposta vinculada.</p>
            <select value={selectedId ?? ""} onChange={(e) => setSelectedId(e.target.value || null)}>
              <option value="">SDC aprovado…</option>
              {approvedForSale.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.contact_name} — {brl.format(Number(i.credit_estimated))}
                </option>
              ))}
            </select>
            <select value={saleQuotaId} onChange={(e) => setSaleQuotaId(e.target.value)}>
              <option value="">Cota disponível…</option>
              {quotas.map((q) => (
                <option key={q.id} value={q.id}>
                  {q.group_code}/{q.quota_code} · {q.category} · {brl.format(Number(q.credit_value))}
                </option>
              ))}
            </select>
            <button type="button" className="admin-button" disabled={!selectedId || !saleQuotaId || busy} onClick={() => void createSale()}>
              Criar cadastro de venda
            </button>
          </div>
        )}
      </section>

      {isInternal ? (
        <section className="panel operational-panel" style={{ marginTop: 16 }}>
          <div className="page-heading" style={{ marginBottom: 8 }}>
            <div>
              <span className="eyebrow dark">INTERNO</span>
              <h2 style={{ fontSize: 18, margin: "6px 0" }}>Esteira TAPAF / Valid-Stamp</h2>
              <p className="muted">Compliance pós-proposta — não faz parte da mesa comercial do parceiro.</p>
            </div>
          </div>
          <PreAnalysisModule />
        </section>
      ) : null}
    </>
  );
}
