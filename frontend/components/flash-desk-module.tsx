"use client";

import { CheckCircle2, FileUp, Plus, RefreshCw, ShoppingCart, Landmark, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { AdminDocumentPanel } from "@/components/admin-document-panel";
import { api, apiForm, deleteApi, downloadApi, User } from "@/lib/api";
import { canEditLetterFinOpsParams, isInternalProductRole } from "@/lib/product-nav";
import { FinOpsModule } from "@/components/finops-module";
import { PreAnalysisModule } from "@/components/pre-analysis-module";
import { DeskSourceMetaRow } from "@/lib/desk-source-meta";
import { CurrencyInput } from "@/components/currency-input";
import { DeskPropertyInspectionPanel } from "@/components/desk-property-inspection-panel";
import { DeskTapafConfigPanel } from "@/components/desk-tapaf-config-panel";
import { PartnerSociosFields, SocioPartner, sociosPayload } from "@/components/partner-socios-fields";
import { validateSocioMaritalRows } from "@/lib/marital-status";
import { lookupCep, lookupMunicipalityPopulation } from "@/lib/cep-lookup";
import { DESK_SIMULATION_NOTICE } from "@/lib/desk-simulation-notice";
import { clearFlashHandoff, loadFlashHandoff } from "@/lib/desk-flash-handoff";

type RequiredDoc = { code: string; label: string; uploaded?: boolean; required?: boolean };

type CadastroOption = {
  lead_id: string;
  name: string;
  document: string | null;
  phone: string;
  email: string | null;
  person_type: string;
  occupation?: string | null;
  monthly_income?: string | null;
  label: string;
};

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
  can_submit_documents?: boolean;
  properties_json?: Array<{ matricula?: string; zone?: string; lot_type?: string }>;
  property_inspections_json?: unknown[];
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
  client_tapaf_path?: string;
};

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const STATUS_OPTIONS = [
  { value: "AWAITING_DOCS", label: "Aguardando Documentação" },
  { value: "UNDER_REVIEW", label: "Em Análise" },
  { value: "PENDING", label: "Pendente" },
  { value: "AWAITING_TAPAF_PAYMENT", label: "Pendente pagamento TAPAF" },
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
  hq_street: "",
  hq_number: "",
  hq_neighborhood: "",
  hq_city: "",
  hq_state: "",
  hq_zip: "",
  hq_complement: "",
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
  operation_type: "IMOVEL_PROPRIO" as "IMOVEL_PROPRIO" | "IMOVEL_TERCEIRO",
  third_party_name: "",
  third_party_document: "",
  third_party_email: "",
  third_party_phone: "",
};

type FlashChecklistConfigRow = {
  asset_category: string;
  asset_category_label: string;
  operation_type: string;
  operation_type_label: string;
  items: Array<{ code: string; label: string }>;
  customized?: boolean;
};

type FlashChecklistItemDraft = { code: string; label: string; required: boolean };

const FLASH_OPERATION_OPTIONS = [
  { value: "IMOVEL_PROPRIO", label: "Imóvel próprio" },
  { value: "IMOVEL_TERCEIRO", label: "Imóvel de terceiro" },
] as const;

function FlashChecklistConfigPanel({
  highlightKey,
  editorAnchorRef,
}: {
  highlightKey?: string;
  editorAnchorRef?: RefObject<HTMLDivElement | null>;
}) {
  const [rows, setRows] = useState<FlashChecklistConfigRow[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [draftItems, setDraftItems] = useState<FlashChecklistItemDraft[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const selected = useMemo(
    () => rows.find((r) => r.operation_type === selectedKey) ?? null,
    [rows, selectedKey],
  );

  useEffect(() => {
    setLoading(true);
    api<FlashChecklistConfigRow[]>("/flash/desk/checklist-config")
      .then((list) => {
        setRows(list);
        if (!selectedKey && list[0]) setSelectedKey(list[0].operation_type);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar checklists"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!highlightKey || !rows.length) return;
    if (rows.some((r) => r.operation_type === highlightKey)) setSelectedKey(highlightKey);
  }, [highlightKey, rows]);

  useEffect(() => {
    if (!selected) return;
    const items = selected.items.map((it) => ({
      code: it.code,
      label: it.label,
      required: (it as { required?: boolean }).required !== false,
    }));
    setDraftItems(items.length ? items : [{ code: "", label: "", required: true }]);
  }, [selected?.operation_type, selected?.items]);

  function patchDraftItem(index: number, patch: Partial<FlashChecklistItemDraft>) {
    setDraftItems((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], ...patch };
      return next;
    });
  }

  async function saveConfig() {
    if (!selected) return;
    setError("");
    setNotice("");
    const cleaned = draftItems
      .map((it) => ({ code: it.code.trim(), label: it.label.trim(), required: it.required }))
      .filter((it) => it.code && it.label);
    if (!cleaned.length) {
      setError("Informe ao menos um item com código e descrição.");
      return;
    }
    setBusy(true);
    try {
      const updated = await api<FlashChecklistConfigRow[]>("/flash/desk/checklist-config", {
        method: "PUT",
        body: JSON.stringify({
          operation_type: selected.operation_type,
          items: cleaned,
        }),
      });
      setRows(updated);
      setNotice("Checklist salvo.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar checklist");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ marginTop: 12 }} ref={editorAnchorRef}>
      {error && <div className="error" style={{ marginBottom: 8 }}>{error}</div>}
      {notice && <div className="notice" style={{ marginBottom: 8 }}>{notice}</div>}
      <p className="muted" style={{ fontSize: 11, margin: "0 0 10px", lineHeight: 1.45 }}>
        <b>Passo 1:</b> escolha o tipo de operação (igual ao cadastro da solicitação).
        <br />
        <b>Passo 2:</b> cadastre cada documento (código + descrição).
        <br />
        <b>Passo 3:</b> salve — o checklist vale na esteira e nos anexos.
      </p>
      <div style={{ display: "grid", gap: 10, gridTemplateColumns: "minmax(0,1fr) minmax(0,1.2fr)" }}>
        <label style={{ fontSize: 11, fontWeight: 700 }}>
          Tipo de operação
          <select
            value={selectedKey}
            onChange={(e) => setSelectedKey(e.target.value)}
            style={{ width: "100%", marginTop: 4, padding: 8, borderRadius: 8, fontWeight: 400 }}
            disabled={loading || !rows.length}
          >
            {rows.map((r) => (
              <option key={r.operation_type} value={r.operation_type}>
                {r.operation_type_label}{r.customized ? " *" : ""}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="admin-button" disabled={busy || !selected} onClick={() => void saveConfig()}>
          Salvar itens obrigatórios
        </button>
      </div>
      {loading && <p className="muted" style={{ fontSize: 11, margin: "10px 0 0" }}>Carregando checklists…</p>}
      <div style={{ marginTop: 14, padding: 14, borderRadius: 10, border: "1px solid var(--line)", background: "#fff" }}>
        <b style={{ fontSize: 12 }}>Documentos obrigatórios</b>
        <p className="muted" style={{ fontSize: 10, margin: "6px 0 10px" }}>
          Comprovantes, fotos e laudos. Documentos gerados por API não precisam ser anexados pelo parceiro.
        </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {draftItems.map((it, idx) => (
          <div
            key={`${idx}-${it.code}`}
            style={{ display: "grid", gap: 8, gridTemplateColumns: "minmax(120px,0.35fr) minmax(0,1fr) auto auto", alignItems: "end" }}
          >
            <label style={{ fontSize: 11 }}>
              Código
              <input value={it.code} onChange={(e) => patchDraftItem(idx, { code: e.target.value })} placeholder="RG_CPF" />
            </label>
            <label style={{ fontSize: 11 }}>
              Documento / descrição
              <input value={it.label} onChange={(e) => patchDraftItem(idx, { label: e.target.value })} placeholder="Comprovante de renda" />
            </label>
            <label style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 6, paddingBottom: 8 }}>
              <input
                type="checkbox"
                checked={it.required}
                onChange={(e) => patchDraftItem(idx, { required: e.target.checked })}
              />
              Obrigatório
            </label>
            <button
              type="button"
              className="table-action"
              title="Remover item"
              disabled={draftItems.length <= 1}
              onClick={() => setDraftItems((prev) => prev.filter((_, i) => i !== idx))}
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        <button
          type="button"
          className="table-action"
          style={{ alignSelf: "flex-start" }}
          onClick={() => setDraftItems((prev) => [...prev, { code: "", label: "", required: true }])}
        >
          <Plus size={14} />
          Adicionar documento obrigatório
        </button>
      </div>
      </div>
    </div>
  );
}

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
  debt_answer: "" | "NAO" | "SIM";
  debt_type: "" | "FINANCEIRA" | "OUTRAS";
  debt_payoff_value: string;
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
    debt_answer: "",
    debt_type: "",
    debt_payoff_value: "",
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

function composeBorrowerAddress(form: typeof emptyForm): string {
  const line1 = [form.hq_street.trim(), form.hq_number.trim()].filter(Boolean).join(", ");
  const parts = [
    line1,
    form.hq_complement.trim(),
    form.hq_neighborhood.trim(),
    [form.hq_city.trim(), form.hq_state.trim()].filter(Boolean).join(" / "),
    form.hq_zip.trim() ? `CEP ${form.hq_zip.trim()}` : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

function borrowerAddressPayload(form: typeof emptyForm) {
  return {
    street: form.hq_street.trim(),
    number: form.hq_number.trim(),
    neighborhood: form.hq_neighborhood.trim(),
    city: form.hq_city.trim(),
    state: form.hq_state.trim(),
    zip: form.hq_zip.trim(),
    complement: form.hq_complement.trim(),
    full_address: composeBorrowerAddress(form),
  };
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
  const tapafPanelRef = useRef<HTMLDivElement>(null);
  const resultPanelRef = useRef<HTMLDivElement>(null);
  const checklistEditorRef = useRef<HTMLDivElement>(null);
  const [checklistCatalog, setChecklistCatalog] = useState<FlashChecklistConfigRow[]>([]);
  const [cadastros, setCadastros] = useState<CadastroOption[]>([]);
  const [existingCadastroId, setExistingCadastroId] = useState("");
  const [docSubmitNotes, setDocSubmitNotes] = useState("");

  const isInternal = isInternalProductRole(user?.role);
  const letterOps = canEditLetterFinOpsParams(user?.role);
  const canEditFinOpsRate = letterOps;
  const formChecklistPreview = useMemo(() => {
    const row = checklistCatalog.find((r) => r.operation_type === form.operation_type);
    return row?.items ?? [];
  }, [checklistCatalog, form.operation_type]);

  function patchProperties(updater: (rows: FlashPropertyRow[]) => FlashPropertyRow[]) {
    setProperties(updater);
    setEvalResult(null);
  }

  function propertiesForPayload() {
    const borrowerName = form.contact_name.trim();
    const borrowerDoc = form.document.trim();
    const isProprio = form.operation_type === "IMOVEL_PROPRIO";
    return properties.map((p) => {
      const owners = isProprio
        ? [{ name: borrowerName, document: borrowerDoc, share_percent: "100" }]
        : [
            {
              name: form.third_party_name.trim(),
              document: form.third_party_document.trim(),
              share_percent: "100",
            },
          ];
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
        has_debt: p.debt_answer === "SIM",
        debt_type: p.debt_answer === "SIM" ? p.debt_type : null,
        debt_payoff_value:
          p.debt_answer === "SIM" && p.debt_type === "FINANCEIRA"
            ? moneyPayload(p.debt_payoff_value)
            : null,
        owner_same_as_borrower: isProprio,
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
    let population = "";
    if (addr.ibge) {
      const pop = await lookupMunicipalityPopulation(addr.ibge);
      if (pop) population = String(pop);
    }
    patchProperties((rows) => {
      const next = [...rows];
      const row = { ...next[index] };
      if (addr.street) row.street = addr.street;
      row.city = addr.city;
      row.state = addr.uf;
      row.zip = addr.zipcode;
      if (population) row.population = population;
      next[index] = row;
      return next;
    });
  }

  function validatePropertyDebts(p: FlashPropertyRow, index: number): string | null {
    const label = `imóvel ${index + 1}`;
    if (!p.debt_answer) return `Informe se o ${label} possui dívidas.`;
    if (p.debt_answer === "NAO") return null;
    if (!p.debt_type) return `Selecione o tipo de dívida do ${label}.`;
    if (p.debt_type === "OUTRAS") return `Outras dívidas no ${label} — sem perfil para Flash Capital.`;
    if (!parseMoney(p.debt_payoff_value)) return `Informe o valor da quitação financeira do ${label}.`;
    const pv = parseMoney(p.property_value);
    const payoff = parseMoney(p.debt_payoff_value);
    if (pv > 0 && payoff > pv * 0.3) {
      return `Quitação financeira do ${label} superior a 30% do valor do bem — sem perfil para o produto.`;
    }
    return null;
  }

  function validateBeforeCalculate(): string | null {
    if (!properties.length) return "Inclua ao menos um imóvel.";
    for (let i = 0; i < properties.length; i += 1) {
      const p = properties[i];
      if (!p.matricula.trim()) return `Informe a matrícula do imóvel ${i + 1}.`;
      if (!parseMoney(p.property_value)) return `Informe o valor do imóvel ${i + 1}.`;
      if (!p.street.trim() || !p.city.trim()) return `Complete o endereço do imóvel ${i + 1}.`;
      const debtErr = validatePropertyDebts(p, i);
      if (debtErr) return debtErr;
    }
    if (!totalPropertiesValue()) return "Informe o valor de pelo menos um imóvel.";
    return null;
  }

  function validateBeforeStore(): string | null {
    if (!form.contact_name.trim()) return "Informe a razão social do tomador (PJ).";
    if (!form.contact_email.trim()) return "Informe o e-mail do tomador.";
    if (!form.contact_phone.trim()) return "Informe o telefone do tomador.";
    if (!form.document.trim()) return "Informe o CNPJ do tomador.";
    if (!form.hq_street.trim() || !form.hq_number.trim()) {
      return "Informe logradouro e número da sede do tomador (PJ).";
    }
    if (!form.hq_city.trim() || !form.hq_state.trim()) {
      return "Informe cidade e UF da sede do tomador.";
    }
    if (form.hq_zip.replace(/\D/g, "").length !== 8) return "Informe o CEP completo da sede do tomador.";
    if (!properties.length) return "Inclua ao menos um imóvel.";
    for (let i = 0; i < properties.length; i += 1) {
      const p = properties[i];
      if (!p.matricula.trim()) return `Informe a matrícula do imóvel ${i + 1}.`;
      if (!p.street.trim() || !p.city.trim()) return `Complete o endereço do imóvel ${i + 1}.`;
      if (!parseMoney(p.property_value)) return `Informe o valor do imóvel ${i + 1}.`;
      const debtErr = validatePropertyDebts(p, i);
      if (debtErr) return debtErr;
    }
    if (form.operation_type === "IMOVEL_TERCEIRO") {
      if (!form.third_party_name.trim()) return "Informe o nome do proprietário do imóvel (terceiro).";
      if (!form.third_party_document.trim()) return "Informe o CPF/CNPJ do proprietário (terceiro).";
      if (!form.third_party_email.trim()) return "Informe o e-mail do proprietário (terceiro).";
      if (!form.third_party_phone.trim()) return "Informe o telefone do proprietário (terceiro).";
    }
    if (!totalPropertiesValue()) return "Informe o valor de pelo menos um imóvel.";
    if (!evalResult?.viable) return "Calcule a viabilidade antes de avançar.";
    const socioMarital = validateSocioMaritalRows(sociosPayload(socios));
    if (socioMarital) return socioMarital;
    return null;
  }

  function mergeSolicitation(updated: FlashSolicitation) {
    setItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
  }

  const load = useCallback(async () => {
    const [me, list, cadastroRows] = await Promise.all([
      api<User>("/auth/me"),
      api<FlashSolicitation[]>("/flash/desk/solicitations"),
      api<CadastroOption[]>("/marketplace/venda-direta-manual/cadastros").catch(() => [] as CadastroOption[]),
    ]);
    setUser(me);
    setItems(list);
    setCadastros(
      cadastroRows.filter((c) => {
        const pt = (c.person_type || "PF").toUpperCase();
        const docDigits = (c.document || "").replace(/\D/g, "");
        return pt === "PJ" || docDigits.length === 14;
      }),
    );
  }, []);

  useEffect(() => {
    setLoading(true);
    load()
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar mesa Flash"))
      .finally(() => setLoading(false));
  }, [load]);

  useEffect(() => {
    api<FlashChecklistConfigRow[]>("/flash/desk/checklist-config")
      .then(setChecklistCatalog)
      .catch(() => setChecklistCatalog([]));
  }, [user?.role]);

  function fillCadastroFromRow(row: CadastroOption) {
    const addr = (row as { address?: Record<string, string> }).address || {};
    setForm((prev) => ({
      ...prev,
      contact_name: row.name || prev.contact_name,
      contact_email: row.email || prev.contact_email,
      contact_phone: row.phone || prev.contact_phone,
      document: row.document || prev.document,
      person_type: "PJ",
      occupation: row.occupation || prev.occupation,
      income_value: row.monthly_income ? String(row.monthly_income) : prev.income_value,
      hq_street: addr.street || prev.hq_street,
      hq_number: addr.number || prev.hq_number,
      hq_neighborhood: addr.neighborhood || prev.hq_neighborhood,
      hq_city: addr.city || prev.hq_city,
      hq_state: addr.uf || addr.state || prev.hq_state,
      hq_zip: addr.zipcode || addr.zip || prev.hq_zip,
    }));
    setEvalResult(null);
  }

  function applyCadastro(id: string) {
    setExistingCadastroId(id);
    if (!id) return;
    const row = cadastros.find((x) => x.lead_id === id);
    if (!row) {
      setError("Cadastro não encontrado. Clique em Atualizar e tente de novo.");
      return;
    }
    setError("");
    fillCadastroFromRow(row);
    setNotice(`Dados de ${row.name} importados do cadastro na plataforma.`);
  }

  useEffect(() => {
    const handoff = loadFlashHandoff();
    if (!handoff) return;
    clearFlashHandoff();
    setTab("nova");
    if (handoff.source === "PROPOSAL_SIMULATOR") {
      setForm((prev) => ({
        ...prev,
        contact_name: handoff.contact_name || prev.contact_name,
        contact_email: handoff.contact_email || prev.contact_email,
        contact_phone: handoff.contact_phone || prev.contact_phone,
        requested_amount: handoff.requested_amount || prev.requested_amount,
        asset_value: handoff.asset_value || prev.asset_value,
        term_months: handoff.term_months ? String(handoff.term_months) : prev.term_months,
        person_type: handoff.person_type || prev.person_type,
      }));
      if (handoff.lead_id) {
        setExistingCadastroId(handoff.lead_id);
      }
      setNotice(
        handoff.proposal_id
          ? `Simulação importada (proposta ${handoff.proposal_id.slice(0, 8)}…) — revise os dados e calcule a viabilidade.`
          : "Simulação importada do Simulador Flash Capital — revise os dados e calcule a viabilidade.",
      );
      return;
    }
    setForm((prev) => ({
      ...prev,
      contact_name: handoff.contact_name || prev.contact_name,
      contact_email: handoff.contact_email || prev.contact_email,
      contact_phone: handoff.contact_phone || prev.contact_phone,
      document: handoff.document || prev.document,
      occupation: handoff.occupation || prev.occupation,
      income_value: handoff.income_value || prev.income_value,
      requested_amount: handoff.requested_amount || prev.requested_amount,
      address: handoff.address || prev.address,
    }));
    if (handoff.properties?.length) {
      setProperties(
        handoff.properties.map((p) => {
          const hasDebt = p.debt_answer === "SIM";
          let debtType: FlashPropertyRow["debt_type"] = "";
          if (hasDebt) {
            if (p.debt_type === "NAO_FINANCEIRAS") debtType = "OUTRAS";
            else debtType = "FINANCEIRA";
          }
          return {
            localKey: Math.random().toString(36).slice(2),
            zone: "URBANO",
            street: p.street || "",
            number: p.number || "",
            city: p.city || "",
            state: p.state || "",
            zip: p.zip || "",
            population: "",
            matricula: p.matricula || "",
            property_value: p.property_value || "",
            debt_answer: hasDebt ? "SIM" : "NAO",
            debt_type: debtType,
            debt_payoff_value: p.debt_payoff_value || "",
            owner_same_as_borrower: true,
            owners: [{ name: "", document: "", share_percent: "" }],
          };
        }),
      );
    }
    if (handoff.partners_json?.length) {
      setSocios(
        handoff.partners_json.map((p) => ({
          name: p.name,
          document: p.document,
          role: p.role,
          share_percent: p.share_percent,
          marital_status: p.marital_status || "",
          spouse_name: p.spouse_name || "",
          spouse_document: p.spouse_document || "",
        })),
      );
    }
    setNotice("Dados importados da mesa SDC — revise e calcule a viabilidade Flash Capital.");
  }, []);

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
      asset_paid_off: properties.every((p) => p.debt_answer === "NAO"),
      asset_has_lien: false,
      lien_payoff_value: null,
      property_registry: registry || null,
      properties_json: props,
      docs_complete: true,
      term_months: Number(form.term_months),
      capital_source: form.capital_source,
      operation_type: form.operation_type,
      third_party_signer:
        form.operation_type === "IMOVEL_TERCEIRO"
          ? {
              name: form.third_party_name.trim(),
              document: form.third_party_document.trim(),
              email: form.third_party_email.trim(),
              phone: form.third_party_phone.trim(),
            }
          : null,
      partners_json: sociosPayload(socios),
    };
  }

  function setOperationType(op: "IMOVEL_PROPRIO" | "IMOVEL_TERCEIRO") {
    setForm((prev) => ({ ...prev, operation_type: op }));
    setEvalResult(null);
    patchProperties((rows) =>
      rows.map((r) => ({
        ...r,
        owner_same_as_borrower: op === "IMOVEL_PROPRIO",
      })),
    );
  }

  async function calculate() {
    const precheck = validateBeforeCalculate();
    if (precheck) {
      setError(precheck);
      setEvalResult(null);
      return;
    }
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
      window.setTimeout(() => resultPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 120);
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
          address: composeBorrowerAddress(form) || null,
          borrower_address_json: borrowerAddressPayload(form),
          occupation: form.occupation.trim() || null,
          income_value: moneyPayload(form.income_value),
          asset_full_address: fullAddress || null,
          partners_json: sociosPayload(socios),
        }),
      });
      setTapafCheckout(null);
      setTapafProposalId("");
      const clientPath = created.client_tapaf_path || "";
      const clientUrl = clientPath ? `${window.location.origin}${clientPath}` : "";
      if (clientUrl) {
        setNotice(
          `Solicitação gravada (${created.status_label}). Envie o link TAPAF ao cliente (tomador) por e-mail ou WhatsApp — só ele aceita e paga a taxa.`,
        );
        try {
          await navigator.clipboard.writeText(clientUrl);
          setNotice((n) => `${n} Link copiado: ${clientUrl}`);
        } catch {
          setNotice((n) => `${n} Link para o cliente: ${clientUrl}`);
        }
      } else {
        setNotice(`Flash gravado: ${created.contact_name} — ${created.status_label}.`);
      }
      if (letterOps && created.tapaf_checkout) {
        setTapafCheckout(created.tapaf_checkout);
        setTapafProposalId(created.tapaf_proposal_id || "");
        window.setTimeout(() => tapafPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 150);
      }
      setSelectedId(created.id);
      setTab("lista");
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
    setForm((prev) => {
      const next = {
        ...prev,
        hq_zip: addr.zipcode,
        hq_street: addr.street || prev.hq_street,
        hq_neighborhood: addr.neighborhood || prev.hq_neighborhood,
        hq_city: addr.city || prev.hq_city,
        hq_state: addr.uf || prev.hq_state,
      };
      return { ...next, address: composeBorrowerAddress(next) };
    });
    setEvalResult(null);
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
      setNotice("Aceite TAPAF registrado. Abra o boleto ou Pix abaixo.");
      await refreshTapafCheckout();
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
      const mode = tapafCheckout?.checkout_mode || "";
      const url = tapafCheckout?.checkout_url || "";
      const isGateway = (mode === "ASAAS" || mode === "INTER" || mode === "SANDBOX") && url.startsWith("http");
      if (isGateway) {
        window.open(url, "_blank", "noopener,noreferrer");
        setNotice(
          mode === "INTER"
            ? "Boleto Inter aberto — após pagar, TAPAF confirma via webhook."
            : "Cobrança aberta — aguarde confirmação do pagamento.",
        );
        return;
      }
      setNotice(
        "Checkout sandbox — use a confirmação manual apenas em ambiente de teste.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao abrir pagamento TAPAF");
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
      const updated = await apiForm<FlashSolicitation>(`/flash/desk/solicitations/${item.id}/documents`, body);
      mergeSolicitation(updated);
      setNotice(`Documento ${type} anexado em ${item.contact_name}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no upload");
    } finally {
      setBusy(false);
    }
  }

  async function submitDocuments(item: FlashSolicitation) {
    setError("");
    setBusy(true);
    try {
      const updated = await api<FlashSolicitation>(`/flash/desk/solicitations/${item.id}/submit-documents`, {
        method: "POST",
        body: JSON.stringify({ status_notes: docSubmitNotes.trim() || null }),
      });
      setNotice(`${updated.contact_name}: documentação enviada — ${updated.status_label}.`);
      setDocSubmitNotes("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao enviar documentação");
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
      const fresh = await api<FlashSolicitation>(`/flash/desk/solicitations/${item.id}`);
      mergeSolicitation(fresh);
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
                <label style={{ gridColumn: "1 / -1", fontSize: 11, fontWeight: 700 }}>
                  Cliente PJ já cadastrado na plataforma
                  <select
                    value={existingCadastroId}
                    onChange={(e) => applyCadastro(e.target.value)}
                    style={{ width: "100%", marginTop: 4, padding: 8, borderRadius: 8, fontWeight: 400 }}
                  >
                    <option value="">Preencher manualmente</option>
                    {cadastros.map((c) => (
                      <option key={c.lead_id} value={c.lead_id}>{c.label}</option>
                    ))}
                  </select>
                </label>
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
                <label style={{ gridColumn: "1 / -1" }}>
                  Tipo de operação
                  <select
                    value={form.operation_type}
                    onChange={(e) => setOperationType(e.target.value as "IMOVEL_PROPRIO" | "IMOVEL_TERCEIRO")}
                    style={{ width: "100%", marginTop: 4, padding: 8, borderRadius: 8 }}
                  >
                    {FLASH_OPERATION_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                  <small className="muted">
                    Imóvel próprio: garantia do tomador PJ. Imóvel de terceiro: o proprietário também assina o contrato.
                  </small>
                </label>
                <div
                  style={{
                    gridColumn: "1 / -1",
                    padding: 12,
                    borderRadius: 10,
                    border: "1px dashed var(--line)",
                    background: "#f9fcfb",
                    fontSize: 11,
                  }}
                >
                  <b>Checklist que será exigido nesta operação</b>
                  {formChecklistPreview.length ? (
                    <ul style={{ margin: "8px 0", paddingLeft: 18 }}>
                      {formChecklistPreview.map((d) => (
                        <li key={d.code}>
                          {(d as { required?: boolean }).required === false ? "○ (opcional) " : "● "}
                          {d.label}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted" style={{ margin: "8px 0 0" }}>Carregando checklist…</p>
                  )}
                  {letterOps && (
                    <button
                      type="button"
                      className="table-action"
                      onClick={() => checklistEditorRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
                    >
                      Editar checklist (admin)
                    </button>
                  )}
                </div>
                {form.operation_type === "IMOVEL_TERCEIRO" && (
                  <>
                    <div style={{ gridColumn: "1 / -1", marginTop: 4 }}>
                      <b style={{ fontSize: 11 }}>Proprietário do imóvel (terceiro — assinatura do contrato)</b>
                    </div>
                    <input
                      placeholder="Nome do proprietário"
                      value={form.third_party_name}
                      onChange={(e) => patchForm("third_party_name", e.target.value)}
                    />
                    <input
                      placeholder="CPF/CNPJ do proprietário"
                      value={form.third_party_document}
                      onChange={(e) => patchForm("third_party_document", e.target.value)}
                    />
                    <input
                      placeholder="E-mail do proprietário"
                      value={form.third_party_email}
                      onChange={(e) => patchForm("third_party_email", e.target.value)}
                    />
                    <input
                      placeholder="Telefone do proprietário"
                      value={form.third_party_phone}
                      onChange={(e) => patchForm("third_party_phone", e.target.value)}
                    />
                  </>
                )}
                <div style={{ gridColumn: "1 / -1", marginTop: 4 }}>
                  <b style={{ fontSize: 11 }}>Endereço da sede (tomador)</b>
                  <small className="muted" style={{ display: "block" }}>
                    Dados completos para o contrato (logradouro, número, bairro, cidade e UF).
                  </small>
                </div>
                <label>
                  CEP
                  <input
                    value={form.hq_zip}
                    onChange={(e) => patchForm("hq_zip", e.target.value)}
                    onBlur={(e) => {
                      const z = e.target.value;
                      if (z.replace(/\D/g, "").length === 8) void fillHqCep(z);
                    }}
                    placeholder="00000-000"
                    inputMode="numeric"
                  />
                </label>
                <label>
                  Logradouro
                  <input
                    placeholder="Rua / avenida"
                    value={form.hq_street}
                    onChange={(e) => patchForm("hq_street", e.target.value)}
                  />
                </label>
                <label>
                  Número
                  <input placeholder="Nº" value={form.hq_number} onChange={(e) => patchForm("hq_number", e.target.value)} />
                </label>
                <label>
                  Bairro
                  <input
                    placeholder="Bairro"
                    value={form.hq_neighborhood}
                    onChange={(e) => patchForm("hq_neighborhood", e.target.value)}
                  />
                </label>
                <label>
                  Cidade
                  <input placeholder="Cidade" value={form.hq_city} onChange={(e) => patchForm("hq_city", e.target.value)} />
                </label>
                <label>
                  UF
                  <input
                    placeholder="MG"
                    maxLength={2}
                    value={form.hq_state}
                    onChange={(e) => patchForm("hq_state", e.target.value.toUpperCase())}
                  />
                </label>
                <label style={{ gridColumn: "1 / -1" }}>
                  Complemento (opcional)
                  <input
                    placeholder="Sala, andar, bloco…"
                    value={form.hq_complement}
                    onChange={(e) => patchForm("hq_complement", e.target.value)}
                  />
                </label>
                {composeBorrowerAddress(form) ? (
                  <p className="muted" style={{ gridColumn: "1 / -1", margin: 0, fontSize: 11 }}>
                    Resumo: {composeBorrowerAddress(form)}
                  </p>
                ) : null}
                <label>
                  Valor solicitado (R$)
                  <CurrencyInput value={form.requested_amount} onChange={(v) => patchForm("requested_amount", v)} placeholder="R$ 0,00" />
                </label>
                <select value={form.term_months} onChange={(e) => patchForm("term_months", e.target.value)}>
                  <option value="36">36 meses</option>
                  <option value="60">60 meses (balloon 36)</option>
                </select>
              </div>
              <PartnerSociosFields value={socios} onChange={setSocios} captureMaritalStatus title="Sócios (PJ)" />

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
                        onBlur={(e) => {
                          const z = e.currentTarget.value;
                          if (z.replace(/\D/g, "").length === 8) void fillCepForProperty(pIdx, z);
                        }}
                      />
                    </label>
                    <label>
                      População do município (IBGE)
                      <input
                        readOnly
                        placeholder="Preenchido automaticamente ao informar o CEP"
                        value={prop.population ? Number(prop.population).toLocaleString("pt-BR") : ""}
                      />
                      <small className="muted">Estimativa municipal via CEP — não precisa digitar.</small>
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
                    <label>
                      O imóvel possui dívidas?
                      <select
                        value={prop.debt_answer}
                        onChange={(e) => {
                          const v = e.target.value as FlashPropertyRow["debt_answer"];
                          patchProperties((rows) => {
                            const next = [...rows];
                            next[pIdx] = {
                              ...next[pIdx],
                              debt_answer: v,
                              debt_type: v === "SIM" ? next[pIdx].debt_type : "",
                              debt_payoff_value: v === "SIM" ? next[pIdx].debt_payoff_value : "",
                            };
                            return next;
                          });
                        }}
                      >
                        <option value="">Selecione…</option>
                        <option value="NAO">Não</option>
                        <option value="SIM">Sim</option>
                      </select>
                    </label>
                    {prop.debt_answer === "SIM" && (
                      <>
                        <label>
                          Tipo de dívida
                          <select
                            value={prop.debt_type}
                            onChange={(e) => {
                              const v = e.target.value as FlashPropertyRow["debt_type"];
                              patchProperties((rows) => {
                                const next = [...rows];
                                next[pIdx] = {
                                  ...next[pIdx],
                                  debt_type: v,
                                  debt_payoff_value: v === "FINANCEIRA" ? next[pIdx].debt_payoff_value : "",
                                };
                                return next;
                              });
                            }}
                          >
                            <option value="">Selecione…</option>
                            <option value="FINANCEIRA">Financeira</option>
                            <option value="OUTRAS">Outras dívidas</option>
                          </select>
                        </label>
                        {prop.debt_type === "OUTRAS" && (
                          <p className="muted" style={{ gridColumn: "1 / -1", margin: 0, fontSize: 11, color: "#b42318" }}>
                            Outras dívidas não têm perfil para Flash Capital.
                          </p>
                        )}
                        {prop.debt_type === "FINANCEIRA" && (
                          <label style={{ gridColumn: "1 / -1" }}>
                            Valor da quitação financeira (R$)
                            <CurrencyInput
                              value={prop.debt_payoff_value}
                              onChange={(v) => {
                                patchProperties((rows) => {
                                  const next = [...rows];
                                  next[pIdx] = { ...next[pIdx], debt_payoff_value: v };
                                  return next;
                                });
                              }}
                              placeholder="R$ 0,00"
                            />
                            <small className="muted">Limite: até 30% do valor do imóvel.</small>
                          </label>
                        )}
                      </>
                    )}
                  </div>

                  {form.operation_type === "IMOVEL_PROPRIO" ? (
                    <p className="muted" style={{ fontSize: 11, margin: "8px 0 0" }}>
                      Titular do imóvel: mesmo tomador PJ informado acima.
                    </p>
                  ) : (
                    <p className="muted" style={{ fontSize: 11, margin: "8px 0 0" }}>
                      Titular: proprietário terceiro informado no início do cadastro (assinatura do contrato).
                    </p>
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

              {totalPropertiesValue() > 0 && (
                <p className="muted" style={{ margin: 0, fontSize: 11 }}>
                  Valor total dos imóveis: <b>{brl.format(totalPropertiesValue())}</b>
                </p>
              )}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="admin-button" disabled={busy} onClick={() => void calculate()}>Calcular viabilidade</button>
              </div>
            </div>
            <div ref={resultPanelRef} style={{ border: "1px solid var(--line)", borderRadius: 12, padding: 16, background: "#f7fbf9" }}>
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
              {letterOps && tapafCheckout && (
                <div ref={tapafPanelRef} className="tapaf-checkout" style={{ marginTop: 14 }}>
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
                    {(tapafCheckout.botao_habilitado || tapafCheckout.checkout_url?.startsWith("http")) ? (
                      <button type="button" className="admin-button" disabled={busy} onClick={() => void payTapaf()}>
                        {tapafCheckout.botao_label || "Abrir boleto / Pix TAPAF"}
                      </button>
                    ) : (
                      <p className="muted" style={{ fontSize: 11, margin: 0, lineHeight: 1.45 }}>
                        Após o aceite do cliente, o boleto/Pix Inter será liberado neste painel (sandbox: confirmação manual).
                      </p>
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
                  const mandatory = item.required_docs.filter((d) => d.required !== false);
                  const uploaded = mandatory.filter((d) => d.uploaded).length;
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
                      <td>{uploaded}/{mandatory.length || item.required_docs.length}</td>
                      <td style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                        {letterOps && (
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
                {selected.properties_json?.length ? (
                  <DeskPropertyInspectionPanel
                    desk="flash"
                    solicitationId={selected.id}
                    properties={selected.properties_json.map((p) => ({
                      matricula: String(p.matricula || ""),
                      zone: p.zone || "URBANO",
                      lot_type: p.lot_type,
                    }))}
                    disabled={selected.status !== "AWAITING_DOCS"}
                  />
                ) : null}
                {selected.status === "AWAITING_DOCS" && !letterOps && (
                  <>
                    <label style={{ display: "block", marginTop: 12, fontSize: 11 }}>
                      Observações para a operação (opcional)
                      <textarea
                        rows={3}
                        value={docSubmitNotes}
                        onChange={(e) => setDocSubmitNotes(e.target.value)}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </label>
                    <button
                      type="button"
                      className="admin-button"
                      style={{ marginTop: 8 }}
                      disabled={busy || !selected.can_submit_documents}
                      onClick={() => void submitDocuments(selected)}
                    >
                      Enviar documentação para análise
                    </button>
                    {!selected.can_submit_documents && (
                      <p className="muted" style={{ fontSize: 10, margin: "8px 0 0" }}>
                        Anexe todos os documentos obrigatórios do checklist antes de enviar.
                      </p>
                    )}
                  </>
                )}
                <AdminDocumentPanel
                  title="Documentação"
                  hint="Anexe cada item do checklist. Itens já enviados somem da lista até você excluir o arquivo."
                  documents={selected.documents}
                  busy={busy}
                  canDelete={letterOps || selected.status === "AWAITING_DOCS"}
                  checklistDocs={selected.required_docs}
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

      {letterOps ? (
        <DeskTapafConfigPanel />
      ) : null}
      {letterOps ? (
        <>
          <section className="panel operational-panel" style={{ marginTop: 16 }}>
            <div className="page-heading" style={{ marginBottom: 8 }}>
              <div>
                <span className="eyebrow dark">INTERNO</span>
                <h2 style={{ fontSize: 18, margin: "6px 0" }}>Checklists Flash Capital</h2>
                <p className="muted">Somente operação LETTER edita documentos por tipo de operação. Parceiros só anexam e enviam.</p>
              </div>
            </div>
            <div style={{ padding: "0 18px 18px" }}>
              <FlashChecklistConfigPanel highlightKey={form.operation_type} editorAnchorRef={checklistEditorRef} />
            </div>
          </section>
          <section className="panel operational-panel" style={{ marginTop: 16 }}>
            <div className="page-heading" style={{ marginBottom: 8 }}>
              <div>
                <span className="eyebrow dark">INTERNO</span>
                <h2 style={{ fontSize: 18, margin: "6px 0" }}>FinOps / parâmetros</h2>
              </div>
            </div>
            <FinOpsModule allowRateEdit={canEditFinOpsRate} />
          </section>
          {isInternal && (
            <section className="panel operational-panel" style={{ marginTop: 16 }}>
              <div className="page-heading" style={{ marginBottom: 8 }}>
                <div>
                  <span className="eyebrow dark">INTERNO</span>
                  <h2 style={{ fontSize: 18, margin: "6px 0" }}>Esteira TAPAF / Valid-Stamp</h2>
                </div>
              </div>
              <PreAnalysisModule variant="flash" />
            </section>
          )}
        </>
      ) : null}
    </>
  );
}
