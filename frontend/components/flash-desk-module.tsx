"use client";

import { CheckCircle2, FileUp, Plus, RefreshCw, ShoppingCart, Landmark, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AdminDocumentPanel } from "@/components/admin-document-panel";
import { api, apiForm, deleteApi, downloadApi, User } from "@/lib/api";
import { isInternalProductRole } from "@/lib/product-nav";
import { FinOpsModule } from "@/components/finops-module";
import { PreAnalysisModule } from "@/components/pre-analysis-module";
import { DeskSourceMetaRow } from "@/lib/desk-source-meta";
import { CurrencyInput } from "@/components/currency-input";
import { PartnerSociosFields, SocioPartner, sociosPayload } from "@/components/partner-socios-fields";
import { lookupCep, lookupMunicipalityPopulation } from "@/lib/cep-lookup";
import { DESK_SIMULATION_NOTICE } from "@/lib/desk-simulation-notice";

type RequiredDoc = { code: string; label: string; uploaded?: boolean };

type FlashSolicitation = {
  id: string;
  status: string;
  status_label: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  document: string | null;
  person_type: string;
  asset_type: string;
  asset_category: string;
  asset_value: string;
  capital_source: string;
  term_months: number;
  principal: string;
  ltv_percent: string;
  platform_fee: string;
  itbi_provision: string;
  net_payout: string;
  installment_estimated: string;
  interest_rate_monthly: string;
  proposal_id: string | null;
  source_channel: string | null;
  source_channel_label: string | null;
  lead_id: string | null;
  required_docs: RequiredDoc[];
  documents: Array<{ id: string; doc_type: string; document_id?: string | null; filename?: string | null; status?: string | null; created_at: string | null }>;
  can_create_sale: boolean;
};

type EvalResult = {
  viable: boolean;
  motivos: string[];
  category: string;
  required_docs: RequiredDoc[];
  principal: string;
  ltv_percent: string;
  platform_fee: string;
  itbi_provision: string;
  net_payout: string;
  monthly_payment: string;
  term_months: number;
  interest_rate_monthly: string;
  capital_source: string;
  message: string;
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

type StoreResponse = FlashSolicitation & {
  tapaf_checkout?: TapafCheckoutUi;
  tapaf_proposal_id?: string;
};

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

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
  person_type: "PJ",
  address: "",
  occupation: "",
  income_value: "",
  asset_type: "imovel",
  asset_value: "",
  requested_amount: "",
  asset_year: "",
  asset_paid_off: true,
  asset_has_lien: false,
  docs_complete: true,
  term_months: "36",
  capital_source: "RETAIL",
  lien_payoff_value: "",
};

type PropertyOwner = { name: string; document: string; share_percent: string };

type FlashPropertyRow = {
  localKey: string;
  zone: "URBANO" | "RURAL";
  street: string;
  number: string;
  city: string;
  state: string;
  zip: string;
  population: string;
  matricula: string;
  property_value: string;
  owner_same_as_borrower: boolean;
  owners: PropertyOwner[];
};

function newPropertyRow(): FlashPropertyRow {
  return {
    localKey: Math.random().toString(36).slice(2),
    zone: "URBANO",
    street: "",
    number: "",
    city: "",
    state: "",
    zip: "",
    population: "",
    matricula: "",
    property_value: "",
    owner_same_as_borrower: false,
    owners: [{ name: "", document: "", share_percent: "" }],
  };
}

function composePropertyAddress(p: FlashPropertyRow): string {
  const parts = [
    [p.street.trim(), p.number.trim()].filter(Boolean).join(", "),
    p.city.trim(),
    p.state.trim(),
    p.zip.trim() ? `CEP ${p.zip.trim()}` : "",
    p.population.trim() ? `Pop. ${p.population.trim()}` : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

function parseMoney(value: string): number {
  const raw = String(value || "").trim();
  if (!raw) return 0;
  const normalized = raw.includes(",") ? raw.replace(/\./g, "").replace(",", ".") : raw;
  const n = Number(normalized);
  return Number.isFinite(n) ? n : 0;
}

const emptyParties = {
  borrower_cnpj: "",
  property_owner_type: "PJ_BORROWER",
  property_owner_document: "",
  legal_representative_document: "",
  liveness_reference: "",
  qsa_representative_match: true,
  consent_confirmation: true,
};

function moneyPayload(value: string) {
  const raw = String(value || "").trim();
  if (!raw) return "0";
  if (raw.includes(",")) return raw.replace(/\./g, "").replace(",", ".");
  return raw;
}

export function FlashDeskModule() {
  const [tab, setTab] = useState<"nova" | "lista" | "venda">("nova");
  const [user, setUser] = useState<User | null>(null);
  const [items, setItems] = useState<FlashSolicitation[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [parties, setParties] = useState(emptyParties);
  const [evalResult, setEvalResult] = useState<EvalResult | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [docType, setDocType] = useState("MATRICULA_ENOTARIADO");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [socios, setSocios] = useState<SocioPartner[]>([]);
  const [properties, setProperties] = useState<FlashPropertyRow[]>(() => [newPropertyRow()]);
  const [tapafCheckout, setTapafCheckout] = useState<TapafCheckoutUi | null>(null);
  const [tapafProposalId, setTapafProposalId] = useState("");
  const [tapafScroll, setTapafScroll] = useState(false);
  const [tapafCb1, setTapafCb1] = useState(false);
  const [tapafCb2, setTapafCb2] = useState(false);
  const [hqZip, setHqZip] = useState("");
  const tapafPanelRef = useRef<HTMLDivElement>(null);

  const isInternal = isInternalProductRole(user?.role);

  function patchProperties(updater: (rows: FlashPropertyRow[]) => FlashPropertyRow[]) {
    setProperties(updater);
    setEvalResult(null);
  }

  function propertiesForPayload() {
    const borrowerName = form.contact_name.trim();
    const borrowerDoc = form.document.trim();
    return properties.map((p) => {
      const owners = p.owner_same_as_borrower
        ? [{ name: borrowerName, document: borrowerDoc, share_percent: "100" }]
        : p.owners
            .filter((o) => o.name.trim() || o.document.trim())
            .map((o) => ({
              name: o.name.trim(),
              document: o.document.trim(),
              share_percent: o.share_percent.trim() || "0",
            }));
      return {
        zone: p.zone,
        street: p.street.trim(),
        number: p.number.trim(),
        city: p.city.trim(),
        state: p.state.trim(),
        zip: p.zip.trim(),
        population: p.population.trim(),
        matricula: p.matricula.trim(),
        property_value: moneyPayload(p.property_value),
        owner_same_as_borrower: p.owner_same_as_borrower,
        owners,
        full_address: composePropertyAddress(p),
      };
    });
  }

  function totalPropertiesValue(): number {
    return properties.reduce((sum, p) => sum + parseMoney(p.property_value), 0);
  }

  async function fillCepForProperty(index: number, cep: string) {
    const addr = await lookupCep(cep);
    if (!addr) return;
    patchProperties((rows) => {
      const next = [...rows];
      const row = { ...next[index] };
      if (addr.street) row.street = addr.street;
      row.city = addr.city;
      row.state = addr.uf;
      row.zip = addr.zipcode;
      next[index] = row;
      return next;
    });
    if (addr.ibge) {
      const pop = await lookupMunicipalityPopulation(addr.ibge);
      if (pop) {
        patchProperties((rows) => {
          const next = [...rows];
          next[index] = { ...next[index], population: String(pop) };
          return next;
        });
      }
    }
  }

  function validateBeforeStore(): string | null {
    if (!form.contact_name.trim()) return "Informe a razão social do tomador (PJ).";
    if (!form.contact_email.trim()) return "Informe o e-mail do tomador.";
    if (!form.contact_phone.trim()) return "Informe o telefone do tomador.";
    if (!form.document.trim()) return "Informe o CNPJ do tomador.";
    if (!properties.length) return "Inclua ao menos um imóvel.";
    for (let i = 0; i < properties.length; i += 1) {
      const p = properties[i];
      if (!p.matricula.trim()) return `Informe a matrícula do imóvel ${i + 1}.`;
      if (!p.street.trim() || !p.city.trim()) return `Complete o endereço do imóvel ${i + 1}.`;
      if (!parseMoney(p.property_value)) return `Informe o valor do imóvel ${i + 1}.`;
      if (!p.owner_same_as_borrower) {
        const active = p.owners.filter((o) => o.name.trim() || o.document.trim());
        if (!active.length) return `Informe ao menos um titular do imóvel ${i + 1}.`;
        const shareSum = active.reduce((s, o) => s + Number(o.share_percent.replace(",", ".") || 0), 0);
        if (shareSum < 99.5 || shareSum > 100.5) {
          return `A soma das participações dos titulares do imóvel ${i + 1} deve ser 100%.`;
        }
      }
    }
    if (!totalPropertiesValue()) return "Informe o valor de pelo menos um imóvel.";
    if (!evalResult?.viable) return "Calcule a viabilidade antes de avançar.";
    return null;
  }

  const load = useCallback(async () => {
    const [me, list] = await Promise.all([
      api<User>("/auth/me"),
      api<FlashSolicitation[]>("/flash/desk/solicitations"),
    ]);
    setUser(me);
    setItems(list);
  }, []);

  useEffect(() => {
    setLoading(true);
    load()
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar mesa Flash"))
      .finally(() => setLoading(false));
  }, [load]);

  const filtered = useMemo(
    () => (statusFilter === "ALL" ? items : items.filter((i) => i.status === statusFilter)),
    [items, statusFilter],
  );
  const selected = useMemo(() => items.find((i) => i.id === selectedId) ?? null, [items, selectedId]);
  const approvedForSale = useMemo(() => items.filter((i) => i.can_create_sale), [items]);

  useEffect(() => {
    if (!selected) return;
    const firstMissing = selected.required_docs.find((d) => !d.uploaded)?.code;
    if (firstMissing) setDocType(firstMissing);
    else if (selected.required_docs[0]) setDocType(selected.required_docs[0].code);
  }, [selected]);

  function patchForm<K extends keyof typeof emptyForm>(key: K, value: (typeof emptyForm)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setEvalResult(null);
  }

  function evaluatePayload() {
    const props = propertiesForPayload();
    const total = props.reduce((s, p) => s + Number(p.property_value || 0), 0);
    const registry = properties.map((p) => p.matricula.trim()).filter(Boolean).join("\n");
    return {
      person_type: "PJ",
      asset_type: "imovel",
      asset_value: total > 0 ? String(total) : moneyPayload(form.asset_value),
      requested_amount: form.requested_amount.trim() ? moneyPayload(form.requested_amount) : null,
      asset_year: null,
      asset_paid_off: form.asset_paid_off,
      asset_has_lien: form.asset_has_lien,
      lien_payoff_value: form.asset_has_lien && form.lien_payoff_value ? moneyPayload(form.lien_payoff_value) : null,
      property_registry: registry || null,
      properties_json: props,
      docs_complete: form.docs_complete,
      term_months: Number(form.term_months),
      capital_source: form.capital_source,
    };
  }

  async function calculate() {
    setError("");
    setBusy(true);
    setTapafCheckout(null);
    setTapafProposalId("");
    try {
      const res = await api<{ result: EvalResult }>("/flash/desk/evaluate", {
        method: "POST",
        body: JSON.stringify(evaluatePayload()),
      });
      setEvalResult(res.result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no cálculo");
    } finally {
      setBusy(false);
    }
  }

  async function store() {
    const validation = validateBeforeStore();
    if (validation) {
      setError(validation);
      return;
    }
    setError("");
    setBusy(true);
    try {
      const fullAddress = properties.map(composePropertyAddress).filter(Boolean).join("\n---\n");
      const created = await api<StoreResponse>("/flash/desk/solicitations", {
        method: "POST",
        body: JSON.stringify({
          ...evaluatePayload(),
          contact_name: form.contact_name.trim(),
          contact_email: form.contact_email.trim(),
          contact_phone: form.contact_phone.trim(),
          document: form.document.trim() || null,
          person_type: "PJ",
          address: form.address.trim() || null,
          occupation: form.occupation.trim() || null,
          income_value: moneyPayload(form.income_value),
          asset_full_address: fullAddress || null,
          partners_json: sociosPayload(socios),
        }),
      });
      setNotice(`Flash gravado: ${created.contact_name} — ${created.status_label}. Conclua o TAPAF no painel ao lado.`);
      if (created.tapaf_checkout) {
        setTapafCheckout(created.tapaf_checkout);
        setTapafProposalId(created.tapaf_proposal_id || "");
        setTapafScroll(false);
        setTapafCb1(false);
        setTapafCb2(false);
        window.setTimeout(() => tapafPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 150);
      } else {
        setError("Solicitação gravada, mas o checkout TAPAF não foi gerado. Atualize a página ou contate o suporte.");
      }
      setSelectedId(created.id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao gravar solicitação");
    } finally {
      setBusy(false);
    }
  }

  async function refreshTapafCheckout() {
    const res = await api<{ interface_checkout_tapaf: TapafCheckoutUi }>("/finops/pre-analysis/generate-tapaf", {
      method: "POST",
      body: JSON.stringify({ proposal_id: tapafProposalId }),
    });
    setTapafCheckout(res.interface_checkout_tapaf);
  }

  async function fillHqCep(cep: string) {
    const addr = await lookupCep(cep);
    if (!addr) return;
    const line = [addr.street, addr.neighborhood, addr.city, addr.uf, addr.zipcode ? `CEP ${addr.zipcode}` : ""]
      .filter(Boolean)
      .join(", ");
    patchForm("address", line);
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
          asset_type: "REAL_ESTATE",
        }),
      });
      await refreshTapafCheckout();
      setNotice("Aceite TAPAF registrado. Use o botão abaixo para gerar boleto/Pix.");
      tapafPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
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
          event_id: `flash-desk-tapaf-${Date.now()}`,
          amount: tapafCheckout?.valor_nominal_taxa || "1500.00",
        }),
      });
      setNotice("TAPAF confirmada. Acompanhe o status na aba Acompanhamento.");
      setForm(emptyForm);
      setSocios([]);
      setProperties([newPropertyRow()]);
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

  async function updateStatus(item: FlashSolicitation, status: string) {
    setError("");
    setBusy(true);
    try {
      const updated = await api<FlashSolicitation>(`/flash/desk/solicitations/${item.id}`, {
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

  async function uploadDoc(item: FlashSolicitation, file: File, type = docType) {
    setError("");
    setBusy(true);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("doc_type", type);
      await apiForm(`/flash/desk/solicitations/${item.id}/documents`, body);
      setNotice(`Documento ${type} anexado em ${item.contact_name}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no upload");
    } finally {
      setBusy(false);
    }
  }

  async function deleteDoc(item: FlashSolicitation, docId: string) {
    setError("");
    setBusy(true);
    try {
      await deleteApi(`/flash/desk/solicitations/${item.id}/documents/${docId}`);
      setNotice("Documento excluído.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao excluir documento");
    } finally {
      setBusy(false);
    }
  }

  const flashDocTypeOptions = useMemo(
    () =>
      (selected?.required_docs?.length
        ? selected.required_docs
        : [
            { code: "MATRICULA_ENOTARIADO", label: "Matrícula e-notariado" },
            { code: "FIPE_MOLICAR", label: "FIPE/Molicar" },
            { code: "LAUDO_AVALIACAO", label: "Laudo" },
            { code: "SERASA", label: "Serasa" },
            { code: "BACEN", label: "Bacen" },
            { code: "CRLV", label: "CRLV" },
          ]
      ).map((d) => ({ value: d.code, label: d.label })),
    [selected],
  );

  async function createSale() {
    if (!selectedId) return;
    setError("");
    setBusy(true);
    try {
      const payload = parties.borrower_cnpj.trim()
        ? {
            borrower_cnpj: parties.borrower_cnpj.trim(),
            property_owner_type: parties.property_owner_type,
            property_owner_document: parties.property_owner_document.trim() || parties.borrower_cnpj.trim(),
            legal_representative_document: parties.legal_representative_document.trim() || null,
            liveness_reference: parties.liveness_reference.trim() || null,
            qsa_representative_match: parties.qsa_representative_match,
            consent_confirmation: parties.consent_confirmation,
          }
        : {};
      const res = await api<{ message: string; proposal_id: string }>(
        `/flash/desk/solicitations/${selectedId}/sale`,
        { method: "POST", body: JSON.stringify(payload) },
      );
      setNotice(`${res.message} (proposta ${res.proposal_id})`);
      setParties(emptyParties);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao criar proposta");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="loading">Carregando mesa Flash Capital…</div>;

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">COMERCIAL</span>
          <h1>Flash Capital</h1>
          <p>
            Mesa em 3 etapas: viabilidade LTV 40% → lastros/status → proposta com cálculo v3 e partes PJ.
            Parceiro anexa docs; operação LETTER altera status.
          </p>
        </div>
        <div className="operational-icon"><Landmark /></div>
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
            3. Proposta / partes PJ
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
                  {STATUS_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, fontWeight: 700, color: "#52605a" }}>
                Tipo lastro
                <select value={docType} onChange={(e) => setDocType(e.target.value)} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid var(--line)" }}>
                  {(selected?.required_docs?.length
                    ? selected.required_docs
                    : [
                        { code: "MATRICULA_ENOTARIADO", label: "Matrícula e-notariado" },
                        { code: "FIPE_MOLICAR", label: "FIPE/Molicar" },
                        { code: "LAUDO_AVALIACAO", label: "Laudo" },
                        { code: "SERASA", label: "Serasa" },
                        { code: "BACEN", label: "Bacen" },
                        { code: "CRLV", label: "CRLV" },
                      ]
                  ).map((d) => (
                    <option key={d.code} value={d.code}>{d.label}</option>
                  ))}
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
              <p className="muted" style={{ margin: 0, fontSize: 11 }}>
                Flash Capital é exclusivo para <b>Pessoa Jurídica (PJ)</b>. Informe o tomador do crédito e cada imóvel em garantia (operação em nome de terceiros titulares).
              </p>
              <div style={{ display: "grid", gap: 9, gridTemplateColumns: "1fr 1fr" }}>
                <div style={{ gridColumn: "1 / -1" }}>
                  <b style={{ fontSize: 12 }}>Tomador do crédito (PJ)</b>
                </div>
                <input placeholder="Razão social" value={form.contact_name} onChange={(e) => patchForm("contact_name", e.target.value)} />
                <input placeholder="CNPJ" value={form.document} onChange={(e) => patchForm("document", e.target.value)} />
                <input placeholder="E-mail" value={form.contact_email} onChange={(e) => patchForm("contact_email", e.target.value)} />
                <input placeholder="Telefone" value={form.contact_phone} onChange={(e) => patchForm("contact_phone", e.target.value)} />
                <label>
                  Faturamento mensal (R$)
                  <CurrencyInput value={form.income_value} onChange={(v) => patchForm("income_value", v)} placeholder="R$ 0,00" />
                  <small className="muted">Receita bruta média por mês da empresa.</small>
                </label>
                <input placeholder="Ramo de atividade" value={form.occupation} onChange={(e) => patchForm("occupation", e.target.value)} />
                <label>
                  CEP da sede (tomador)
                  <input
                    value={hqZip}
                    onChange={(e) => setHqZip(e.target.value)}
                    onBlur={(e) => {
                      const z = e.target.value;
                      if (z.replace(/\D/g, "").length === 8) void fillHqCep(z);
                    }}
                    placeholder="00000-000"
                    inputMode="numeric"
                  />
                </label>
                <input
                  style={{ gridColumn: "1 / -1" }}
                  placeholder="Endereço da sede (tomador) — preenchido pelo CEP ou digite manualmente"
                  value={form.address}
                  onChange={(e) => patchForm("address", e.target.value)}
                />
                <label>
                  Valor solicitado (R$)
                  <CurrencyInput value={form.requested_amount} onChange={(v) => patchForm("requested_amount", v)} placeholder="R$ 0,00" />
                </label>
                <select value={form.term_months} onChange={(e) => patchForm("term_months", e.target.value)}>
                  <option value="36">36 meses</option>
                  <option value="60">60 meses (balloon 36)</option>
                </select>
                {form.asset_has_lien && (
                  <label style={{ gridColumn: "1 / -1" }}>
                    Valor quitação gravame (R$)
                    <CurrencyInput value={form.lien_payoff_value} onChange={(v) => patchForm("lien_payoff_value", v)} />
                  </label>
                )}
              </div>
              <PartnerSociosFields value={socios} onChange={setSocios} />

              {properties.map((prop, pIdx) => (
                <div key={prop.localKey} className="desk-repeat-block" style={{ borderTop: "1px solid var(--line)", paddingTop: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <b style={{ fontSize: 12 }}>Imóvel {pIdx + 1}</b>
                    {properties.length > 1 && (
                      <button
                        type="button"
                        className="table-action"
                        onClick={() => patchProperties((rows) => rows.filter((_, i) => i !== pIdx))}
                        aria-label="Remover imóvel"
                      >
                        <Trash2 size={14} />
                        Remover imóvel
                      </button>
                    )}
                  </div>
                  <div style={{ display: "grid", gap: 9, gridTemplateColumns: "1fr 1fr" }}>
                    <label>
                      Tipo
                      <select
                        value={prop.zone}
                        onChange={(e) => {
                          const zone = e.target.value as FlashPropertyRow["zone"];
                          patchProperties((rows) => {
                            const next = [...rows];
                            next[pIdx] = { ...next[pIdx], zone };
                            return next;
                          });
                        }}
                      >
                        <option value="URBANO">Urbano</option>
                        <option value="RURAL">Rural</option>
                      </select>
                    </label>
                    <label>
                      Matrícula
                      <input
                        placeholder="Nº matrícula"
                        value={prop.matricula}
                        onChange={(e) => {
                          const v = e.target.value;
                          patchProperties((rows) => {
                            const next = [...rows];
                            next[pIdx] = { ...next[pIdx], matricula: v };
                            return next;
                          });
                        }}
                      />
                    </label>
                    <label>
                      Valor do imóvel (R$)
                      <CurrencyInput
                        value={prop.property_value}
                        onChange={(v) => {
                          patchProperties((rows) => {
                            const next = [...rows];
                            next[pIdx] = { ...next[pIdx], property_value: v };
                            return next;
                          });
                        }}
                        placeholder="R$ 0,00"
                      />
                    </label>
                    <label>
                      CEP
                      <input
                        placeholder="00000-000"
                        inputMode="numeric"
                        value={prop.zip}
                        onChange={(e) => {
                          const v = e.target.value;
                          patchProperties((rows) => {
                            const next = [...rows];
                            next[pIdx] = { ...next[pIdx], zip: v };
                            return next;
                          });
                        }}
                        onBlur={() => {
                          if (prop.zip.replace(/\D/g, "").length === 8) void fillCepForProperty(pIdx, prop.zip);
                        }}
                      />
                    </label>
                    <label>
                      População do município
                      <input
                        placeholder="Informe ou use CEP"
                        inputMode="numeric"
                        value={prop.population}
                        onChange={(e) => {
                          const v = e.target.value;
                          patchProperties((rows) => {
                            const next = [...rows];
                            next[pIdx] = { ...next[pIdx], population: v };
                            return next;
                          });
                        }}
                      />
                    </label>
                    <label>
                      Logradouro
                      <input
                        placeholder="Rua / avenida"
                        value={prop.street}
                        onChange={(e) => {
                          const v = e.target.value;
                          patchProperties((rows) => {
                            const next = [...rows];
                            next[pIdx] = { ...next[pIdx], street: v };
                            return next;
                          });
                        }}
                      />
                    </label>
                    <label>
                      Número
                      <input
                        placeholder="Nº"
                        value={prop.number}
                        onChange={(e) => {
                          const v = e.target.value;
                          patchProperties((rows) => {
                            const next = [...rows];
                            next[pIdx] = { ...next[pIdx], number: v };
                            return next;
                          });
                        }}
                      />
                    </label>
                    <label>
                      Cidade
                      <input
                        placeholder="Cidade"
                        value={prop.city}
                        onChange={(e) => {
                          const v = e.target.value;
                          patchProperties((rows) => {
                            const next = [...rows];
                            next[pIdx] = { ...next[pIdx], city: v };
                            return next;
                          });
                        }}
                      />
                    </label>
                    <label>
                      UF
                      <input
                        placeholder="MG"
                        maxLength={2}
                        value={prop.state}
                        onChange={(e) => {
                          const v = e.target.value.toUpperCase();
                          patchProperties((rows) => {
                            const next = [...rows];
                            next[pIdx] = { ...next[pIdx], state: v };
                            return next;
                          });
                        }}
                      />
                    </label>
                  </div>

                  <label style={{ fontSize: 11, fontWeight: 700, display: "flex", alignItems: "flex-start", gap: 8, marginTop: 4 }}>
                    <input
                      type="checkbox"
                      checked={prop.owner_same_as_borrower}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        patchProperties((rows) => {
                          const next = [...rows];
                          next[pIdx] = { ...next[pIdx], owner_same_as_borrower: checked };
                          return next;
                        });
                      }}
                    />
                    O titular do imóvel é o mesmo tomador do crédito (espelhar dados do tomador PJ)
                  </label>

                  {!prop.owner_same_as_borrower && (
                    <div className="desk-repeat-block" style={{ marginTop: 4 }}>
                      <b style={{ fontSize: 11 }}>Titular(es) do imóvel</b>
                      <small className="muted">Informe nome, CPF/CNPJ e % de participação (soma 100%).</small>
                      {prop.owners.map((owner, oIdx) => (
                        <div key={oIdx} className="desk-repeat-row">
                          <label>
                            Nome
                            <input
                              placeholder="Nome do titular"
                              value={owner.name}
                              onChange={(e) => {
                                const v = e.target.value;
                                patchProperties((rows) => {
                                  const next = [...rows];
                                  const owners = [...next[pIdx].owners];
                                  owners[oIdx] = { ...owners[oIdx], name: v };
                                  next[pIdx] = { ...next[pIdx], owners };
                                  return next;
                                });
                              }}
                            />
                          </label>
                          <label>
                            CPF/CNPJ · %
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 72px", gap: 6 }}>
                              <input
                                placeholder="Documento"
                                value={owner.document}
                                onChange={(e) => {
                                  const v = e.target.value;
                                  patchProperties((rows) => {
                                    const next = [...rows];
                                    const owners = [...next[pIdx].owners];
                                    owners[oIdx] = { ...owners[oIdx], document: v };
                                    next[pIdx] = { ...next[pIdx], owners };
                                    return next;
                                  });
                                }}
                              />
                              <input
                                placeholder="%"
                                inputMode="decimal"
                                value={owner.share_percent}
                                onChange={(e) => {
                                  const v = e.target.value;
                                  patchProperties((rows) => {
                                    const next = [...rows];
                                    const owners = [...next[pIdx].owners];
                                    owners[oIdx] = { ...owners[oIdx], share_percent: v };
                                    next[pIdx] = { ...next[pIdx], owners };
                                    return next;
                                  });
                                }}
                              />
                            </div>
                          </label>
                          {prop.owners.length > 1 && (
                            <button
                              type="button"
                              className="table-action"
                              onClick={() => {
                                patchProperties((rows) => {
                                  const next = [...rows];
                                  next[pIdx] = {
                                    ...next[pIdx],
                                    owners: next[pIdx].owners.filter((_, i) => i !== oIdx),
                                  };
                                  return next;
                                });
                              }}
                              aria-label="Remover titular"
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      ))}
                      <button
                        type="button"
                        className="table-action"
                        onClick={() => {
                          patchProperties((rows) => {
                            const next = [...rows];
                            next[pIdx] = {
                              ...next[pIdx],
                              owners: [...next[pIdx].owners, { name: "", document: "", share_percent: "" }],
                            };
                            return next;
                          });
                        }}
                      >
                        <Plus size={14} />
                        Adicionar outro titular
                      </button>
                    </div>
                  )}
                </div>
              ))}

              <button
                type="button"
                className="table-action"
                onClick={() => patchProperties((rows) => [...rows, newPropertyRow()])}
              >
                <Plus size={14} />
                Adicionar outro imóvel
              </button>

              <div style={{ display: "flex", flexWrap: "wrap", gap: 14, fontSize: 12, fontWeight: 700 }}>
                <label><input type="checkbox" checked={form.asset_paid_off} onChange={(e) => patchForm("asset_paid_off", e.target.checked)} /> Bem quitado</label>
                <label><input type="checkbox" checked={form.asset_has_lien} onChange={(e) => patchForm("asset_has_lien", e.target.checked)} /> Bem com pendência</label>
                <label><input type="checkbox" checked={form.docs_complete} onChange={(e) => patchForm("docs_complete", e.target.checked)} /> Checklist lastros ok</label>
              </div>
              {totalPropertiesValue() > 0 && (
                <p className="muted" style={{ margin: 0, fontSize: 11 }}>
                  Valor total dos imóveis: <b>{brl.format(totalPropertiesValue())}</b>
                </p>
              )}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="admin-button" disabled={busy} onClick={() => void calculate()}>Calcular viabilidade</button>
              </div>
            </div>
            <div ref={tapafPanelRef} style={{ border: "1px solid var(--line)", borderRadius: 12, padding: 16, background: "#f7fbf9" }}>
              <b>Resultado Flash Capital</b>
              {!evalResult && !tapafCheckout && <p className="muted" style={{ marginTop: 10 }}>Preencha e clique em Calcular.</p>}
              {evalResult?.viable && !tapafCheckout && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
                  <div style={{ display: "grid", gap: 10, gridTemplateColumns: "1fr 1fr" }}>
                    <div><small>Principal (LTV {evalResult.ltv_percent}%)</small><div><b>{brl.format(Number(evalResult.principal))}</b></div></div>
                    <div><small>Líquido ao cliente</small><div><b>{brl.format(Number(evalResult.net_payout))}</b></div></div>
                    <div><small>ITBI 3%</small><div><b>{brl.format(Number(evalResult.itbi_provision))}</b></div></div>
                    <div><small>Parcela Price</small><div><b>{brl.format(Number(evalResult.monthly_payment))}</b></div></div>
                    <div><small>Prazo / taxa</small><div><b>{evalResult.term_months}m @ {evalResult.interest_rate_monthly}%</b></div></div>
                    <div style={{ gridColumn: "1 / -1" }}>
                      <small>Lastros obrigatórios ({evalResult.category})</small>
                      <ul style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 12 }}>
                        {evalResult.required_docs.map((d) => <li key={d.code}>{d.label}</li>)}
                      </ul>
                    </div>
                    <p style={{ gridColumn: "1 / -1", color: "#067647", fontWeight: 700, margin: 0 }}>{evalResult.message}</p>
                  </div>
                  <button type="button" className="admin-button" style={{ width: "100%" }} disabled={busy} onClick={() => void store()}>
                    Avançar e gerar TAPAF
                  </button>
                </div>
              )}
              {evalResult && !evalResult.viable && !tapafCheckout && (
                <div style={{ marginTop: 12 }}>
                  <p style={{ color: "#b42318", fontWeight: 700 }}>{evalResult.message}</p>
                  <ul>{evalResult.motivos.map((m) => <li key={m}>{m}</li>)}</ul>
                </div>
              )}
              {evalResult && !tapafCheckout && (
                <p className="muted" style={{ fontSize: 10, lineHeight: 1.45, marginTop: 12, marginBottom: 0 }}>
                  {DESK_SIMULATION_NOTICE}
                </p>
              )}
              {tapafCheckout && (
                <div className="tapaf-checkout" style={{ marginTop: 14 }}>
                  <b>TAPAF — taxa de abertura</b>
                  <div className="finops-summary tapaf-price" style={{ marginTop: 10 }}>
                    <article>
                      <small>Taxa nominal TAPAF</small>
                      <strong>{brl.format(Number(tapafCheckout.valor_nominal_taxa))}</strong>
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
                  <th>Principal</th>
                  <th>Líquido</th>
                  <th>Status</th>
                  <th>Lastros</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => {
                  const uploaded = item.required_docs.filter((d) => d.uploaded).length;
                  return (
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
                        {item.asset_category}
                        <div className="muted" style={{ fontSize: 11 }}>{brl.format(Number(item.asset_value))}</div>
                      </td>
                      <td>{brl.format(Number(item.principal))}</td>
                      <td>{brl.format(Number(item.net_payout))}</td>
                      <td>{item.status_label}</td>
                      <td>{uploaded}/{item.required_docs.length}</td>
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
                              if (f) void uploadDoc(item, f);
                              e.target.value = "";
                            }}
                          />
                        </label>
                        {item.can_create_sale && (
                          <button type="button" className="table-action" onClick={() => { setSelectedId(item.id); setTab("venda"); }}>
                            <ShoppingCart />Proposta
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {selected && (
              <div className="notice" style={{ marginTop: 14 }}>
                <b>Detalhe — {selected.contact_name}</b>
                <div>
                  Principal {brl.format(Number(selected.principal))} · líquido {brl.format(Number(selected.net_payout))} · parcela{" "}
                  {brl.format(Number(selected.installment_estimated))} · {selected.term_months}m @ {selected.interest_rate_monthly}%
                </div>
                {selected.proposal_id && <div>Proposta: {selected.proposal_id}</div>}
                <DeskSourceMetaRow
                  channel={selected.source_channel}
                  label={selected.source_channel_label}
                  leadId={selected.lead_id}
                />
                <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                  {selected.required_docs.map((d) => (
                    <li key={d.code}>{d.uploaded ? "✓" : "○"} {d.label}</li>
                  ))}
                </ul>
                <AdminDocumentPanel
                  title={`Documentos anexados (${selected.documents.length})`}
                  hint="Anexe, baixe ou exclua arquivos desta solicitação Flash Capital."
                  documents={selected.documents}
                  busy={busy}
                  canDelete={isInternal}
                  docTypeOptions={flashDocTypeOptions}
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
            <p className="muted">Disponível para Flash Aprovado. Partes PJ opcionais na criação (tomador CNPJ).</p>
            <select value={selectedId ?? ""} onChange={(e) => setSelectedId(e.target.value || null)}>
              <option value="">Flash aprovado…</option>
              {approvedForSale.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.contact_name} — {brl.format(Number(i.principal))}
                </option>
              ))}
            </select>
            <div style={{ display: "grid", gap: 9, gridTemplateColumns: "1fr 1fr" }}>
              <input placeholder="CNPJ tomador (opcional)" value={parties.borrower_cnpj} onChange={(e) => setParties((p) => ({ ...p, borrower_cnpj: e.target.value }))} />
              <select value={parties.property_owner_type} onChange={(e) => setParties((p) => ({ ...p, property_owner_type: e.target.value }))}>
                <option value="PJ_BORROWER">Proprietário = tomador PJ</option>
                <option value="PF">Proprietário PF (terceiro)</option>
                <option value="PJ_THIRD_PARTY">Proprietário PJ terceiro</option>
              </select>
              <input placeholder="Doc proprietário" value={parties.property_owner_document} onChange={(e) => setParties((p) => ({ ...p, property_owner_document: e.target.value }))} />
              <input placeholder="Doc representante legal" value={parties.legal_representative_document} onChange={(e) => setParties((p) => ({ ...p, legal_representative_document: e.target.value }))} />
              <input placeholder="Liveness ref (se terceiro)" value={parties.liveness_reference} onChange={(e) => setParties((p) => ({ ...p, liveness_reference: e.target.value }))} />
            </div>
            <button type="button" className="admin-button" disabled={!selectedId || busy} onClick={() => void createSale()}>
              Criar proposta Flash Capital
            </button>
          </div>
        )}
      </section>

      {isInternal ? (
        <>
          <section className="panel operational-panel" style={{ marginTop: 16 }}>
            <div className="page-heading" style={{ marginBottom: 8 }}>
              <div>
                <span className="eyebrow dark">INTERNO</span>
                <h2 style={{ fontSize: 18, margin: "6px 0" }}>FinOps / parâmetros</h2>
              </div>
            </div>
            <FinOpsModule />
          </section>
          <section className="panel operational-panel" style={{ marginTop: 16 }}>
            <div className="page-heading" style={{ marginBottom: 8 }}>
              <div>
                <span className="eyebrow dark">INTERNO</span>
                <h2 style={{ fontSize: 18, margin: "6px 0" }}>Esteira TAPAF / Valid-Stamp</h2>
              </div>
            </div>
            <PreAnalysisModule variant="flash" />
          </section>
        </>
      ) : null}
    </>
  );
}
