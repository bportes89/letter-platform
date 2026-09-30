"use client";

import { CheckCircle2, FileUp, Plus, RefreshCw, ShoppingCart, ClipboardList, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  clearFlashHandoff,
  DeskFlashHandoff,
  saveFlashHandoff,
} from "@/lib/desk-flash-handoff";
import { lookupCep } from "@/lib/cep-lookup";
import { AdminDocumentPanel } from "@/components/admin-document-panel";
import { api, apiForm, deleteApi, downloadApi, User } from "@/lib/api";
import { isInternalProductRole } from "@/lib/product-nav";
import { PreAnalysisModule } from "@/components/pre-analysis-module";
import { DeskSourceMetaRow } from "@/lib/desk-source-meta";
import { PartnerSociosFields, SocioPartner, sociosPayload } from "@/components/partner-socios-fields";
import { CurrencyInput } from "@/components/currency-input";
import { DESK_SIMULATION_NOTICE } from "@/lib/desk-simulation-notice";
import { commercialQuotaDisplay } from "@/lib/commercial-quota-label";
import { formatDocumentDigits } from "@/lib/br-validation";

type RequiredDoc = { code: string; label: string; uploaded?: boolean };

type StatusLogEntry = {
  at: string;
  user_name: string;
  status: string;
  status_label: string;
  notes: string | null;
  pending_doc_codes?: string[];
};

type SdcSolicitation = {
  id: string;
  status: string;
  status_label: string;
  status_notes: string | null;
  status_log?: StatusLogEntry[];
  pending_doc_codes?: string[];
  partner_observation?: string | null;
  asset_category?: string;
  asset_category_label?: string;
  operation_type?: string;
  operation_type_label?: string;
  awaiting_pendency_upload?: boolean;
  full_required_docs?: RequiredDoc[];
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
  documents: Array<{
    id: string;
    doc_type: string;
    upload_batch?: string;
    document_id?: string | null;
    filename?: string | null;
    status?: string | null;
    created_at: string | null;
  }>;
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
  redirect_flash?: boolean;
  profile_blocked?: boolean;
  flash_handoff?: DeskFlashHandoff;
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
  entrada_final?: string | null;
  installment_value?: string;
  remaining_installments?: number | null;
  administrator_name?: string | null;
  status: string;
};

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const ASSET_TYPES = [
  { value: "imovel_urbano", label: "Imóvel urbano" },
  { value: "imovel_rural", label: "Imóvel rural" },
  { value: "veiculo", label: "Veículo" },
  { value: "maquina_agricola", label: "Máquina agrícola" },
] as const;

const OPERATION_TYPES = [
  { value: "PF_PF", label: "PF comprando de PF" },
  { value: "PF_PJ", label: "PF comprando de PJ" },
  { value: "PJ_PJ", label: "PJ comprando de PJ" },
  { value: "PJ_PF", label: "PJ comprando de PF" },
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
  operation_type: "PF_PF",
  address: "",
  occupation: "",
  income_value: "",
  partner_observation: "",
  asset_type: "imovel_urbano",
  asset_value: "",
  asset_year: "",
  asset_paid_off: true,
  asset_has_lien: false,
  docs_complete: true,
  client_credit_restriction: "" as "" | "NAO" | "SIM",
  company_credit_restriction: "" as "" | "NAO" | "SIM",
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

type SdcPropertyRow = {
  localKey: string;
  street: string;
  number: string;
  city: string;
  state: string;
  zip: string;
  matricula: string;
  property_value: string;
  paid_off_answer: "" | "SIM" | "NAO";
  debt_type: "" | "SFI" | "SFH" | "HIPOTECA" | "DEMAIS_FINANCEIRAS" | "NAO_FINANCEIRAS";
  debt_payoff_value: string;
};

type VehicleRow = { plate: string; renavam: string; year: string; vehicle_value: string };

function newSdcPropertyRow(): SdcPropertyRow {
  return {
    localKey: Math.random().toString(36).slice(2),
    street: "",
    number: "",
    city: "",
    state: "",
    zip: "",
    matricula: "",
    property_value: "",
    paid_off_answer: "",
    debt_type: "",
    debt_payoff_value: "",
  };
}

function composeSdcPropertyAddress(p: SdcPropertyRow): string {
  const parts = [
    [p.street.trim(), p.number.trim()].filter(Boolean).join(", "),
    p.city.trim(),
    p.state.trim(),
    p.zip.trim() ? `CEP ${p.zip.trim()}` : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

type ChecklistConfigRow = {
  asset_category: string;
  asset_category_label: string;
  operation_type: string;
  operation_type_label: string;
  items: Array<{ code: string; label: string }>;
  customized?: boolean;
};

type ChecklistItemDraft = { code: string; label: string };

type SdcCadastroOption = {
  lead_id: string;
  name: string;
  document: string | null;
  phone: string;
  email: string | null;
  person_type: string;
  address: Record<string, string>;
  label: string;
  monthly_income?: string | null;
  asset_value?: string | null;
  target_amount?: string | null;
  category?: string | null;
  has_credit_restriction?: boolean | null;
  occupation?: string | null;
};

function mapLeadCategoryToSdcAsset(category: string | null | undefined): string | undefined {
  if (!category) return undefined;
  if (category === "REAL_ESTATE") return "imovel_urbano";
  if (category === "VEHICLE") return "veiculo";
  return undefined;
}

function SdcChecklistConfigPanel() {
  const [rows, setRows] = useState<ChecklistConfigRow[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [draftItems, setDraftItems] = useState<ChecklistItemDraft[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const selected = useMemo(
    () => rows.find((r) => `${r.asset_category}:${r.operation_type}` === selectedKey) ?? null,
    [rows, selectedKey],
  );

  useEffect(() => {
    api<ChecklistConfigRow[]>("/sdc/desk/checklist-config")
      .then((list) => {
        setRows(list);
        if (!selectedKey && list[0]) setSelectedKey(`${list[0].asset_category}:${list[0].operation_type}`);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar checklists"));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setDraftItems(selected.items.map((it) => ({ code: it.code, label: it.label })));
  }, [selected?.asset_category, selected?.operation_type, selected?.items]);

  function patchDraftItem(index: number, patch: Partial<ChecklistItemDraft>) {
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
      .map((it) => ({ code: it.code.trim(), label: it.label.trim() }))
      .filter((it) => it.code && it.label);
    if (!cleaned.length) {
      setError("Informe ao menos um item com código e descrição.");
      return;
    }
    setBusy(true);
    try {
      const updated = await api<ChecklistConfigRow[]>("/sdc/desk/checklist-config", {
        method: "PUT",
        body: JSON.stringify({
          asset_category: selected.asset_category,
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
    <div style={{ marginTop: 12 }}>
      {error && <div className="error" style={{ marginBottom: 8 }}>{error}</div>}
      {notice && <div className="notice" style={{ marginBottom: 8 }}>{notice}</div>}
      <div style={{ display: "grid", gap: 10, gridTemplateColumns: "minmax(0,1fr) minmax(0,1.2fr)" }}>
        <select value={selectedKey} onChange={(e) => setSelectedKey(e.target.value)} style={{ padding: 8, borderRadius: 8 }}>
          {rows.map((r) => (
            <option key={`${r.asset_category}:${r.operation_type}`} value={`${r.asset_category}:${r.operation_type}`}>
              {r.asset_category_label} — {r.operation_type_label}{r.customized ? " *" : ""}
            </option>
          ))}
        </select>
        <button type="button" className="admin-button" disabled={busy || !selected} onClick={() => void saveConfig()}>
          Salvar itens obrigatórios
        </button>
      </div>
      <p className="muted" style={{ fontSize: 10, margin: "8px 0" }}>
        Itens exigidos na esteira comercial para cada combinação de bem + operação. * = personalizado.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {draftItems.map((it, idx) => (
          <div
            key={`${idx}-${it.code}`}
            style={{ display: "grid", gap: 8, gridTemplateColumns: "minmax(120px,0.35fr) minmax(0,1fr) auto", alignItems: "end" }}
          >
            <label style={{ fontSize: 11 }}>
              Código
              <input value={it.code} onChange={(e) => patchDraftItem(idx, { code: e.target.value })} placeholder="RG_CPF" />
            </label>
            <label style={{ fontSize: 11 }}>
              Documento / descrição
              <input value={it.label} onChange={(e) => patchDraftItem(idx, { label: e.target.value })} placeholder="RG e CPF do proponente" />
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
          onClick={() => setDraftItems((prev) => [...prev, { code: "", label: "" }])}
        >
          <Plus size={14} />
          Adicionar item
        </button>
      </div>
    </div>
  );
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
  const router = useRouter();
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
  const [properties, setProperties] = useState<SdcPropertyRow[]>(() => [newSdcPropertyRow()]);
  const [vehicles, setVehicles] = useState<VehicleRow[]>([{ plate: "", renavam: "", year: "", vehicle_value: "" }]);
  const tapafPanelRef = useRef<HTMLDivElement>(null);
  const [creditChoice, setCreditChoice] = useState<"limite" | "solicitada" | null>(null);
  const [tapafCheckout, setTapafCheckout] = useState<TapafCheckoutUi | null>(null);
  const [tapafProposalId, setTapafProposalId] = useState("");
  const [tapafScroll, setTapafScroll] = useState(false);
  const [tapafCb1, setTapafCb1] = useState(false);
  const [tapafCb2, setTapafCb2] = useState(false);
  const [adminStatus, setAdminStatus] = useState("AWAITING_DOCS");
  const [adminNotes, setAdminNotes] = useState("");
  const [adminPending, setAdminPending] = useState<string[]>([]);
  const [partnerObsDraft, setPartnerObsDraft] = useState("");
  const [cadastros, setCadastros] = useState<SdcCadastroOption[]>([]);
  const [existingCadastroId, setExistingCadastroId] = useState("");

  const isInternal = isInternalProductRole(user?.role);
  const needsYear = ["veiculo", "veiculo_leve", "veiculo_pesado", "maquina", "maquina_agricola"].includes(form.asset_type);
  const isImovel = ["imovel", "imovel_urbano", "imovel_rural"].includes(form.asset_type);
  const isVeiculo = ["veiculo", "veiculo_leve", "veiculo_pesado"].includes(form.asset_type);
  const isMaquina = ["maquina", "maquina_agricola"].includes(form.asset_type);

  const load = useCallback(async () => {
    const [me, list, qs, cadastroRows] = await Promise.all([
      api<User>("/auth/me"),
      api<SdcSolicitation[]>("/sdc/desk/solicitations"),
      api<QuotaRow[]>("/quotas"),
      api<SdcCadastroOption[]>("/marketplace/venda-direta-manual/cadastros").catch(() => [] as SdcCadastroOption[]),
    ]);
    setUser(me);
    setItems(list);
    setQuotas(qs.filter((q) => q.status === "AVAILABLE"));
    setCadastros(cadastroRows);
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

  useEffect(() => {
    if (!selected) return;
    setAdminStatus(selected.status);
    setAdminNotes(selected.status_notes || "");
    setAdminPending(selected.pending_doc_codes || []);
    setPartnerObsDraft(selected.partner_observation || "");
  }, [selected?.id, selected?.status, selected?.status_notes, selected?.pending_doc_codes, selected?.partner_observation]);

  function patchForm<K extends keyof typeof emptyForm>(key: K, value: (typeof emptyForm)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setEvalResult(null);
    setCreditChoice(null);
    setTapafCheckout(null);
    setTapafProposalId("");
  }

  function resetSimulationState() {
    setEvalResult(null);
    setCreditChoice(null);
    setTapafCheckout(null);
    setTapafProposalId("");
  }

  function fillCadastroFromRow(row: SdcCadastroOption) {
    resetSimulationState();
    const pt = row.person_type || "PF";
    const addr = row.address || {};
    const addressLine = [addr.street, addr.number, addr.neighborhood, addr.city, addr.uf].filter(Boolean).join(", ");
    const assetFromCat = mapLeadCategoryToSdcAsset(row.category);
    const restriction =
      row.has_credit_restriction === true ? "SIM" : row.has_credit_restriction === false ? "NAO" : ("" as "" | "NAO" | "SIM");
    setForm((prev) => ({
      ...prev,
      contact_name: row.name || "",
      contact_email: row.email || "",
      contact_phone: row.phone || "",
      document: formatDocumentDigits(row.document, pt),
      person_type: pt,
      occupation: row.occupation ? String(row.occupation) : prev.occupation,
      address: addressLine || prev.address,
      income_value: row.monthly_income ? String(row.monthly_income) : prev.income_value,
      requested_leverage_amount: row.target_amount ? String(row.target_amount) : prev.requested_leverage_amount,
      client_credit_restriction: restriction || prev.client_credit_restriction,
      ...(assetFromCat ? { asset_type: assetFromCat } : {}),
    }));
    if (pt === "PF") setSocios([]);
    const imovelCat = assetFromCat && ["imovel", "imovel_urbano", "imovel_rural"].includes(assetFromCat);
    if (imovelCat && (addr.street || addr.city)) {
      setProperties((prev) => {
        const next = prev.length ? [...prev] : [newSdcPropertyRow()];
        next[0] = {
          ...next[0],
          street: addr.street || next[0].street,
          number: addr.number || next[0].number,
          city: addr.city || next[0].city,
          state: addr.uf || next[0].state,
          zip: addr.zipcode || next[0].zip,
          ...(row.asset_value ? { property_value: String(row.asset_value) } : {}),
        };
        return next;
      });
    }
    if (assetFromCat && ["veiculo", "veiculo_leve", "veiculo_pesado"].includes(assetFromCat) && row.asset_value) {
      setVehicles((prev) => {
        const next = prev.length ? [...prev] : [{ plate: "", renavam: "", year: "", vehicle_value: "" }];
        next[0] = { ...next[0], vehicle_value: String(row.asset_value) };
        return next;
      });
    }
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

  function totalPropertiesValue() {
    return properties.reduce((sum, p) => sum + parseMoney(p.property_value), 0);
  }

  function totalVehiclesValue() {
    return vehicles.reduce((sum, v) => sum + parseMoney(v.vehicle_value), 0);
  }

  function partnersForPayload() {
    return sociosPayload(socios).map((row) => ({
      ...row,
      has_credit_restriction: row.has_credit_restriction === "SIM",
    }));
  }

  function propertiesForPayload() {
    return properties.map((p) => ({
      street: p.street.trim(),
      number: p.number.trim(),
      city: p.city.trim(),
      state: p.state.trim(),
      zip: p.zip.trim(),
      matricula: p.matricula.trim(),
      property_value: moneyPayload(p.property_value),
      is_paid_off: p.paid_off_answer === "SIM",
      debt_type: p.paid_off_answer === "NAO" ? p.debt_type : null,
      debt_payoff_value:
        p.paid_off_answer === "NAO" && p.debt_type ? moneyPayload(p.debt_payoff_value) : null,
      full_address: composeSdcPropertyAddress(p),
    }));
  }

  function validatePropertyFinancial(p: SdcPropertyRow, index: number): string | null {
    const label = `imóvel ${index + 1}`;
    if (!p.paid_off_answer) return `Informe se o ${label} está quitado.`;
    if (p.paid_off_answer === "SIM") return null;
    if (!parseMoney(p.debt_payoff_value)) return `Informe o valor de quitação do ${label}.`;
    if (!p.debt_type) return `Selecione o tipo de dívida do ${label}.`;
    return null;
  }

  function buildFlashHandoff(): DeskFlashHandoff {
    return {
      source: "SDC_DESK",
      saved_at: new Date().toISOString(),
      contact_name: form.contact_name.trim(),
      contact_email: form.contact_email.trim(),
      contact_phone: form.contact_phone.trim(),
      document: form.document.trim(),
      person_type: form.person_type,
      address: form.address.trim(),
      occupation: form.occupation.trim(),
      income_value: moneyPayload(form.income_value),
      requested_amount: form.requested_leverage_amount.trim()
        ? moneyPayload(form.requested_leverage_amount)
        : "",
      properties: properties.map((p) => ({
        street: p.street.trim(),
        number: p.number.trim(),
        city: p.city.trim(),
        state: p.state.trim(),
        zip: p.zip.trim(),
        matricula: p.matricula.trim(),
        property_value: moneyPayload(p.property_value),
        debt_answer: p.paid_off_answer === "NAO" ? "SIM" : p.paid_off_answer === "SIM" ? "NAO" : "",
        debt_type: p.debt_type,
        debt_payoff_value: moneyPayload(p.debt_payoff_value),
      })),
      partners_json: partnersForPayload(),
    };
  }

  function goToFlashCapital() {
    saveFlashHandoff(buildFlashHandoff());
    router.push("/modules/flash-capital");
  }

  function vehiclesForPayload() {
    return vehicles
      .map((v) => ({
        plate: v.plate.trim(),
        renavam: v.renavam.trim(),
        year: v.year ? Number(v.year) : null,
        vehicle_value: moneyPayload(v.vehicle_value),
      }))
      .filter((v) => v.plate || v.renavam || Number(v.vehicle_value) > 0);
  }

  function resolvedAssetValue(): number {
    if (isImovel) return totalPropertiesValue();
    if (isVeiculo) return totalVehiclesValue();
    return parseMoney(form.asset_value);
  }

  function resolvedAssetYear(): number | null {
    if (isVeiculo) {
      const years = vehicles.map((v) => Number(v.year)).filter((y) => y >= 1950 && y <= 2100);
      if (years.length) return Math.min(...years);
    }
    if (needsYear && form.asset_year) return Number(form.asset_year);
    return null;
  }

  function patchProperties(updater: (rows: SdcPropertyRow[]) => SdcPropertyRow[]) {
    setProperties(updater);
    setEvalResult(null);
    setCreditChoice(null);
    setTapafCheckout(null);
    setTapafProposalId("");
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
  }

  function evaluatePayload() {
    const requested = form.requested_leverage_amount ? moneyPayload(form.requested_leverage_amount) : null;
    const assetValue = resolvedAssetValue();
    const allPaidOff = isImovel && properties.every((p) => p.paid_off_answer === "SIM");
    return {
      asset_type: form.asset_type,
      asset_category: form.asset_type,
      operation_type: form.operation_type,
      asset_value: moneyPayload(String(assetValue)),
      asset_year: resolvedAssetYear(),
      asset_paid_off: isImovel ? allPaidOff : form.asset_paid_off,
      asset_has_lien: false,
      docs_complete: form.docs_complete,
      person_type: form.person_type,
      contact_name: form.contact_name.trim(),
      contact_email: form.contact_email.trim(),
      contact_phone: form.contact_phone.trim(),
      document: form.document.trim(),
      address: form.address.trim(),
      occupation: form.occupation.trim(),
      income_value: moneyPayload(form.income_value),
      client_has_credit_restriction: form.client_credit_restriction === "SIM",
      company_has_credit_restriction: form.company_credit_restriction === "SIM",
      partners_json: partnersForPayload(),
      properties_json: isImovel ? propertiesForPayload() : [],
      vehicles_json: isVeiculo ? vehiclesForPayload() : [],
      ...(requested && Number(requested) > 0 ? { requested_leverage_amount: requested } : {}),
    };
  }

  function validateBeforeCalculate(): string | null {
    if (!form.client_credit_restriction) return "Informe se o cliente possui restrição creditícia.";
    if (form.person_type === "PJ" && !form.company_credit_restriction) {
      return "Informe se a empresa (PJ) possui restrição creditícia.";
    }
    if (form.person_type === "PJ") {
      for (let i = 0; i < socios.length; i += 1) {
        const row = socios[i];
        if (!row.name.trim() && !row.document.trim()) continue;
        if (!row.has_credit_restriction) return `Informe restrição creditícia do sócio ${i + 1}.`;
      }
    }
    if (isImovel) {
      for (let i = 0; i < properties.length; i += 1) {
        const fin = validatePropertyFinancial(properties[i], i);
        if (fin) return fin;
      }
    }
    return null;
  }

  async function calculate() {
    const pre = validateBeforeCalculate();
    if (pre) {
      setError(pre);
      setEvalResult(null);
      return;
    }
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
      } else if (res.result.simulacao_solicitada) {
        setCreditChoice("solicitada");
      } else {
        setCreditChoice("limite");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no cálculo");
    } finally {
      setBusy(false);
    }
  }

  function validateBeforeStore(choiceOverride?: "limite" | "solicitada" | null): string | null {
    const choice = choiceOverride ?? creditChoice;
    if (!form.contact_name.trim()) return "Informe o nome do cliente.";
    if (!form.contact_email.trim()) return "Informe o e-mail.";
    if (!form.contact_phone.trim()) return "Informe o telefone.";
    if (!form.document.trim()) return "Informe CPF/CNPJ.";
    if (!resolvedAssetValue()) return isImovel ? "Informe o valor de ao menos um imóvel." : isVeiculo ? "Informe o valor de ao menos um veículo." : "Informe o valor do bem.";
    if (!evalResult?.viable) return "Calcule a viabilidade antes de avançar.";
    if (evalResult.show_choice && !choice) {
      return "No resultado da análise, escolha o limite máximo ou o valor solicitado.";
    }
    if (isImovel) {
      for (let i = 0; i < properties.length; i += 1) {
        const p = properties[i];
        if (!p.matricula.trim()) return `Informe a matrícula do imóvel ${i + 1}.`;
        if (!p.street.trim() || !p.city.trim()) return `Complete o endereço do imóvel ${i + 1} (logradouro e cidade).`;
        if (!parseMoney(p.property_value)) return `Informe o valor do imóvel ${i + 1}.`;
        const fin = validatePropertyFinancial(p, i);
        if (fin) return fin;
      }
    }
    if (isVeiculo) {
      for (let i = 0; i < vehicles.length; i += 1) {
        const v = vehicles[i];
        if (!v.plate.trim()) return `Informe a placa do veículo ${i + 1}.`;
        if (!v.year.trim()) return `Informe o ano do veículo ${i + 1}.`;
        if (!parseMoney(v.vehicle_value)) return `Informe o valor do veículo ${i + 1}.`;
      }
    }
    return null;
  }

  function parseMoney(value: string): number {
    const n = Number(moneyPayload(value));
    return Number.isFinite(n) && n > 0 ? n : 0;
  }

  async function advanceToTapaf(choice: "limite" | "solicitada") {
    setCreditChoice(choice);
    await store(choice);
  }

  async function store(choiceOverride?: "limite" | "solicitada") {
    const validation = validateBeforeStore(choiceOverride ?? creditChoice);
    if (validation) {
      setError(validation);
      window.setTimeout(() => tapafPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
      return;
    }
    if (!evalResult) return;
    const effectiveChoice = choiceOverride ?? creditChoice;
    const chosen = chosenCreditFromEval(evalResult, effectiveChoice);
    setError("");
    setBusy(true);
    try {
      const propsPayload = isImovel ? propertiesForPayload() : [];
      const vehicleRows = isVeiculo ? vehiclesForPayload() : [];
      const registryLines = propsPayload.map((p) => p.matricula).filter(Boolean);
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
          vehicles_json: vehicleRows,
          properties_json: propsPayload,
          asset_full_address: isImovel
            ? propsPayload.map((p) => p.full_address).filter(Boolean).join("\n---\n") || null
            : null,
          partners_json: form.person_type === "PJ" ? partnersForPayload() : [],
          asset_category: form.asset_type,
          operation_type: form.operation_type,
          partner_observation: form.partner_observation.trim() || null,
        }),
      });
      setNotice(`SDC gravado: ${created.contact_name} — ${created.status_label}. Conclua o TAPAF no painel ao lado.`);
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
          event_id: `sdc-desk-tapaf-${Date.now()}`,
          amount: tapafCheckout?.valor_nominal_taxa || "1500.00",
        }),
      });
      setNotice("TAPAF confirmada. Acompanhe o status na aba Acompanhamento.");
      setForm(emptyForm);
      setSocios([]);
      setProperties([newSdcPropertyRow()]);
      setVehicles([{ plate: "", renavam: "", year: "", vehicle_value: "" }]);
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

  async function updateStatus(
    item: SdcSolicitation,
    status: string,
    opts?: { status_notes?: string; pending_doc_codes?: string[] },
  ) {
    setError("");
    setBusy(true);
    try {
      const updated = await api<SdcSolicitation>(`/sdc/desk/solicitations/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status,
          status_notes: opts?.status_notes ?? null,
          pending_doc_codes: opts?.pending_doc_codes ?? [],
        }),
      });
      setNotice(`${updated.contact_name}: ${updated.status_label}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao atualizar status");
    } finally {
      setBusy(false);
    }
  }

  async function savePartnerObservation(item: SdcSolicitation) {
    setError("");
    setBusy(true);
    try {
      await api<SdcSolicitation>(`/sdc/desk/solicitations/${item.id}/partner-observation`, {
        method: "PATCH",
        body: JSON.stringify({ partner_observation: partnerObsDraft.trim() || null }),
      });
      setNotice("Observação salva.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar observação");
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
      if (item.awaiting_pendency_upload) body.append("upload_batch", "PENDENCY");
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
      setNotice(
        updated.status === "UNDER_REVIEW" && updated.awaiting_pendency_upload === false && item.status === "PENDING"
          ? `Pendências reenviadas — ${updated.contact_name} em análise LETTER.`
          : `Documentação transmitida — ${updated.contact_name} em análise LETTER.`,
      );
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
                <label style={{ gridColumn: "1 / -1", fontSize: 11, fontWeight: 700 }}>
                  Cliente já cadastrado na plataforma
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
                <label>
                  Cliente com restrição creditícia?
                  <select
                    value={form.client_credit_restriction}
                    onChange={(e) => patchForm("client_credit_restriction", e.target.value as "" | "NAO" | "SIM")}
                  >
                    <option value="">Selecione…</option>
                    <option value="NAO">Não</option>
                    <option value="SIM">Sim</option>
                  </select>
                </label>
                {form.person_type === "PJ" && (
                  <label>
                    Empresa (PJ) com restrição creditícia?
                    <select
                      value={form.company_credit_restriction}
                      onChange={(e) => patchForm("company_credit_restriction", e.target.value as "" | "NAO" | "SIM")}
                    >
                      <option value="">Selecione…</option>
                      <option value="NAO">Não</option>
                      <option value="SIM">Sim</option>
                    </select>
                  </label>
                )}
                <select
                  value={form.asset_type}
                  onChange={(e) => {
                    patchForm("asset_type", e.target.value);
                    setProperties([newSdcPropertyRow()]);
                    setVehicles([{ plate: "", renavam: "", year: "", vehicle_value: "" }]);
                  }}
                >
                  {ASSET_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                <select
                  value={form.operation_type}
                  onChange={(e) => patchForm("operation_type", e.target.value)}
                  title="Tipo de operação"
                >
                  {OPERATION_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                <textarea
                  placeholder="Observação do parceiro sobre esta proposta (opcional)"
                  value={form.partner_observation}
                  onChange={(e) => patchForm("partner_observation", e.target.value)}
                  rows={2}
                  style={{ gridColumn: "1 / -1" }}
                />
                {isMaquina && (
                  <>
                    <label>
                      Valor do bem (R$)
                      <CurrencyInput value={form.asset_value} onChange={(v) => patchForm("asset_value", v)} placeholder="R$ 0,00" />
                    </label>
                    <input type="number" placeholder="Ano fabricação" value={form.asset_year} onChange={(e) => patchForm("asset_year", e.target.value)} />
                  </>
                )}
                {(isImovel || isVeiculo) && (
                  <div className="notice" style={{ gridColumn: "1 / -1", margin: 0 }}>
                    Valor total dos bens: <b>{brl.format(resolvedAssetValue())}</b>
                    <small style={{ display: "block", marginTop: 4 }}>
                      Some o valor de cada {isImovel ? "imóvel" : "veículo"} abaixo. A viabilidade usa o total.
                    </small>
                  </div>
                )}
                <input
                  style={{ gridColumn: "1 / -1" }}
                  placeholder="Endereço resumido do cliente (residência / sede — não é o imóvel de garantia)"
                  value={form.address}
                  onChange={(e) => patchForm("address", e.target.value)}
                />
                <label style={{ gridColumn: "1 / -1" }}>
                  Valor alavancagem solicitado (R$)
                  <CurrencyInput value={form.requested_leverage_amount} onChange={(v) => patchForm("requested_leverage_amount", v)} placeholder="R$ 0,00" />
                </label>
                {isImovel &&
                  properties.map((prop, pIdx) => (
                    <div key={prop.localKey} className="desk-repeat-block" style={{ gridColumn: "1 / -1" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                        <b>Imóvel {pIdx + 1} — endereço do bem (garantia)</b>
                        {properties.length > 1 && (
                          <button
                            type="button"
                            className="table-action"
                            onClick={() => patchProperties((rows) => rows.filter((_, i) => i !== pIdx))}
                            aria-label="Remover imóvel"
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                      <small className="muted">CEP preenche logradouro, cidade e UF automaticamente (ViaCEP).</small>
                      <div style={{ display: "grid", gap: 9, gridTemplateColumns: "1fr 1fr", marginTop: 8 }}>
                        <label>
                          Matrícula do imóvel
                          <input
                            value={prop.matricula}
                            onChange={(e) =>
                              patchProperties((rows) => {
                                const next = [...rows];
                                next[pIdx] = { ...next[pIdx], matricula: e.target.value };
                                return next;
                              })
                            }
                            placeholder="Nº matrícula"
                          />
                        </label>
                        <label>
                          Valor do imóvel (R$)
                          <CurrencyInput
                            value={prop.property_value}
                            onChange={(v) =>
                              patchProperties((rows) => {
                                const next = [...rows];
                                next[pIdx] = { ...next[pIdx], property_value: v };
                                return next;
                              })
                            }
                            placeholder="R$ 0,00"
                          />
                        </label>
                        <label>
                          CEP do imóvel
                          <input
                            value={prop.zip}
                            onChange={(e) =>
                              patchProperties((rows) => {
                                const next = [...rows];
                                next[pIdx] = { ...next[pIdx], zip: e.target.value };
                                return next;
                              })
                            }
                            onBlur={(e) => {
                              const z = e.target.value;
                              if (z.replace(/\D/g, "").length === 8) void fillCepForProperty(pIdx, z);
                            }}
                            placeholder="00000-000"
                            inputMode="numeric"
                          />
                        </label>
                        <label>
                          Logradouro do imóvel
                          <input
                            value={prop.street}
                            onChange={(e) =>
                              patchProperties((rows) => {
                                const next = [...rows];
                                next[pIdx] = { ...next[pIdx], street: e.target.value };
                                return next;
                              })
                            }
                            placeholder="Rua / avenida"
                          />
                        </label>
                        <label>
                          Número
                          <input
                            value={prop.number}
                            onChange={(e) =>
                              patchProperties((rows) => {
                                const next = [...rows];
                                next[pIdx] = { ...next[pIdx], number: e.target.value };
                                return next;
                              })
                            }
                            placeholder="Nº"
                          />
                        </label>
                        <label>
                          Cidade do imóvel
                          <input
                            value={prop.city}
                            onChange={(e) =>
                              patchProperties((rows) => {
                                const next = [...rows];
                                next[pIdx] = { ...next[pIdx], city: e.target.value };
                                return next;
                              })
                            }
                            placeholder="Cidade"
                          />
                        </label>
                        <label>
                          UF do imóvel
                          <input
                            value={prop.state}
                            onChange={(e) =>
                              patchProperties((rows) => {
                                const next = [...rows];
                                next[pIdx] = { ...next[pIdx], state: e.target.value };
                                return next;
                              })
                            }
                            placeholder="MG"
                            maxLength={2}
                          />
                        </label>
                        <label>
                          Imóvel quitado?
                          <select
                            value={prop.paid_off_answer}
                            onChange={(e) => {
                              const v = e.target.value as SdcPropertyRow["paid_off_answer"];
                              patchProperties((rows) => {
                                const next = [...rows];
                                next[pIdx] = {
                                  ...next[pIdx],
                                  paid_off_answer: v,
                                  debt_type: v === "NAO" ? next[pIdx].debt_type : "",
                                  debt_payoff_value: v === "NAO" ? next[pIdx].debt_payoff_value : "",
                                };
                                return next;
                              });
                            }}
                          >
                            <option value="">Selecione…</option>
                            <option value="SIM">Sim, quitado</option>
                            <option value="NAO">Não — possui dívida</option>
                          </select>
                        </label>
                        {prop.paid_off_answer === "NAO" && (
                          <>
                            <label>
                              Valor de quitação do bem (R$)
                              <CurrencyInput
                                value={prop.debt_payoff_value}
                                onChange={(v) =>
                                  patchProperties((rows) => {
                                    const next = [...rows];
                                    next[pIdx] = { ...next[pIdx], debt_payoff_value: v };
                                    return next;
                                  })
                                }
                                placeholder="R$ 0,00"
                              />
                            </label>
                            <label style={{ gridColumn: "1 / -1" }}>
                              Tipo de dívida na matrícula
                              <select
                                value={prop.debt_type}
                                onChange={(e) =>
                                  patchProperties((rows) => {
                                    const next = [...rows];
                                    next[pIdx] = {
                                      ...next[pIdx],
                                      debt_type: e.target.value as SdcPropertyRow["debt_type"],
                                    };
                                    return next;
                                  })
                                }
                              >
                                <option value="">Selecione…</option>
                                <option value="SFI">Financiamento SFI</option>
                                <option value="SFH">Financiamento SFH</option>
                                <option value="HIPOTECA">Hipoteca</option>
                                <option value="DEMAIS_FINANCEIRAS">Demais dívidas financeiras</option>
                                <option value="NAO_FINANCEIRAS">Dívidas não financeiras</option>
                              </select>
                            </label>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                {isImovel && (
                  <button
                    type="button"
                    className="table-action"
                    style={{ gridColumn: "1 / -1" }}
                    onClick={() => patchProperties((rows) => [...rows, newSdcPropertyRow()])}
                  >
                    <Plus size={14} />
                    Adicionar outro imóvel
                  </button>
                )}
                {isVeiculo && (
                  <div className="desk-repeat-block" style={{ gridColumn: "1 / -1" }}>
                    <b>Veículo(s) — dados de cada bem</b>
                    <small className="muted">Sem endereço. Informe placa, RENAVAM, ano e valor de cada veículo.</small>
                    {vehicles.map((row, idx) => (
                      <div key={idx} className="desk-repeat-row" style={{ alignItems: "end" }}>
                        <label>
                          Placa
                          <input
                            placeholder="ABC1D23"
                            value={row.plate}
                            onChange={(e) => {
                              const next = [...vehicles];
                              next[idx] = { ...next[idx], plate: e.target.value };
                              setVehicles(next);
                              setEvalResult(null);
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
                              setEvalResult(null);
                            }}
                          />
                        </label>
                        <label>
                          Ano
                          <input
                            type="number"
                            placeholder="Ano"
                            value={row.year}
                            onChange={(e) => {
                              const next = [...vehicles];
                              next[idx] = { ...next[idx], year: e.target.value };
                              setVehicles(next);
                              setEvalResult(null);
                            }}
                          />
                        </label>
                        <label>
                          Valor (R$)
                          <CurrencyInput
                            value={row.vehicle_value}
                            onChange={(v) => {
                              const next = [...vehicles];
                              next[idx] = { ...next[idx], vehicle_value: v };
                              setVehicles(next);
                              setEvalResult(null);
                            }}
                            placeholder="R$ 0,00"
                          />
                        </label>
                        {vehicles.length > 1 && (
                          <button type="button" className="table-action" onClick={() => setVehicles(vehicles.filter((_, i) => i !== idx))} aria-label="Remover veículo">
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    ))}
                    <button
                      type="button"
                      className="table-action"
                      onClick={() => setVehicles([...vehicles, { plate: "", renavam: "", year: "", vehicle_value: "" }])}
                    >
                      <Plus size={14} />
                      Adicionar outro veículo
                    </button>
                  </div>
                )}
                {isMaquina && (
                  <p className="muted" style={{ gridColumn: "1 / -1", fontSize: 11, margin: 0 }}>
                    Máquina/equipamento: use ano de fabricação e valor do bem. Não exige matrícula de imóvel nem placa.
                  </p>
                )}
              </div>
              {form.person_type === "PJ" && (
                <PartnerSociosFields
                  value={socios}
                  onChange={setSocios}
                  captureCreditRestriction
                  title="Sócios / parceiros (PJ)"
                />
              )}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 14, fontSize: 12, fontWeight: 700 }}>
                <label>
                  <input type="checkbox" checked={form.docs_complete} onChange={(e) => patchForm("docs_complete", e.target.checked)} /> Documentação completa
                </label>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="admin-button" disabled={busy} onClick={() => void calculate()}>Calcular viabilidade</button>
              </div>
            </div>
            <div ref={tapafPanelRef} style={{ border: "1px solid var(--line)", borderRadius: 12, padding: 16, background: "#f7fbf9" }}>
              <b>Resultado da análise</b>
              {error && evalResult && !tapafCheckout && (
                <div className="error" style={{ marginTop: 10, fontSize: 12 }}>{error}</div>
              )}
              {!evalResult && !tapafCheckout && <p className="muted" style={{ marginTop: 10 }}>Preencha e clique em Calcular viabilidade.</p>}
              {evalResult?.required_docs?.length && !tapafCheckout && (
                <p className="muted" style={{ fontSize: 10, marginTop: 8 }}>
                  Após gravar, na aba Acompanhamento você anexará {evalResult.required_docs.length} documentos do checklist (
                  {OPERATION_TYPES.find((o) => o.value === form.operation_type)?.label ?? "operação"} ·{" "}
                  {ASSET_TYPES.find((a) => a.value === form.asset_type)?.label ?? "bem"}).
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
                        <button type="button" className="table-action" style={{ marginTop: 10 }} onClick={() => void advanceToTapaf("limite")}>
                          Avançar com limite máximo → TAPAF
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
                      <button type="button" className="table-action" style={{ marginTop: 10 }} onClick={() => void advanceToTapaf("solicitada")}>
                        Avançar com valor solicitado → TAPAF
                      </button>
                    </div>
                  )}
                  {evalResult.requested_exceeds_limit && (
                    <p style={{ color: "#b45309", fontSize: 11, lineHeight: 1.45, margin: 0 }}>{evalResult.message}</p>
                  )}
                  {!evalResult.requested_exceeds_limit && evalResult.message && (
                    <p style={{ color: "#067647", fontWeight: 700, fontSize: 11, margin: 0 }}>{evalResult.message}</p>
                  )}
                  {evalResult.viable && creditChoice && !evalResult.show_choice && (
                    <button type="button" className="admin-button" disabled={busy} onClick={() => void store()}>
                      Avançar para TAPAF
                    </button>
                  )}
                  {evalResult.show_choice && (
                    <p className="muted" style={{ fontSize: 11, margin: 0 }}>
                      Use um dos botões acima para gravar a solicitação e abrir o checkout TAPAF. Se nada acontecer, confira nome, e-mail, telefone, CPF/CNPJ e matrícula/endereço do bem no formulário à esquerda.
                    </p>
                  )}
                </div>
              )}
              {evalResult && !evalResult.viable && (
                <div style={{ marginTop: 12 }}>
                  <p style={{ color: "#b42318", fontWeight: 700 }}>{evalResult.message}</p>
                  <ul>{evalResult.motivos.map((m) => <li key={m}>{m}</li>)}</ul>
                  {evalResult.redirect_flash && (
                    <div style={{ marginTop: 12, padding: 12, borderRadius: 10, background: "#fff", border: "1px solid var(--line)" }}>
                      <p style={{ margin: "0 0 10px", fontSize: 12, lineHeight: 1.45 }}>
                        Este cliente deve seguir pela <b>esteira Flash Capital</b>. Os dados preenchidos no SDC serão
                        importados automaticamente.
                      </p>
                      <button type="button" className="admin-button" onClick={() => goToFlashCapital()}>
                        Ir para Flash Capital
                      </button>
                    </div>
                  )}
                  {evalResult.profile_blocked && (
                    <p className="muted" style={{ marginTop: 10, fontSize: 11 }}>
                      Sem perfil para SDC e sem encaminhamento automático para Flash Capital.
                    </p>
                  )}
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
                        <button
                          type="button"
                          className="table-action"
                          onClick={() => setSelectedId(item.id)}
                          title="Ver retorno e pendências no detalhe abaixo"
                        >
                          Esteira
                        </button>
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
                {(selected.operation_type_label || selected.asset_category_label) && (
                  <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
                    {selected.asset_category_label || selected.asset_type_label}
                    {selected.operation_type_label ? ` · ${selected.operation_type_label}` : ""}
                  </div>
                )}
                {!isInternal && (
                  <div style={{ marginTop: 12 }}>
                    <b style={{ fontSize: 12 }}>Observação do parceiro</b>
                    <textarea
                      value={partnerObsDraft}
                      onChange={(e) => setPartnerObsDraft(e.target.value)}
                      rows={3}
                      style={{ width: "100%", marginTop: 6, fontSize: 12 }}
                      placeholder="Informações adicionais sobre a proposta…"
                    />
                    <button type="button" className="table-action" style={{ marginTop: 6 }} disabled={busy} onClick={() => void savePartnerObservation(selected)}>
                      Salvar observação
                    </button>
                  </div>
                )}
                {selected.partner_observation && isInternal && (
                  <div style={{ marginTop: 10, fontSize: 11 }}>
                    <b>Observação do parceiro:</b> {selected.partner_observation}
                  </div>
                )}
                {isInternal && (
                  <div style={{ marginTop: 14, padding: 12, borderRadius: 10, border: "1px solid var(--line)", background: "#fafcfb" }}>
                    <b style={{ fontSize: 12 }}>Retorno LETTER (esteira)</b>
                    <div style={{ display: "grid", gap: 8, marginTop: 8, gridTemplateColumns: "1fr 1fr" }}>
                      <select value={adminStatus} onChange={(e) => setAdminStatus(e.target.value)} style={{ padding: 8, borderRadius: 8, border: "1px solid var(--line)" }}>
                        {STATUS_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                      </select>
                      <button
                        type="button"
                        className="admin-button"
                        disabled={busy}
                        onClick={() => {
                          if (adminStatus === "PENDING" && !adminPending.length) {
                            setError("Marque os documentos pendentes antes de salvar.");
                            return;
                          }
                          void updateStatus(selected, adminStatus, {
                            status_notes: adminNotes.trim() || undefined,
                            pending_doc_codes: adminStatus === "PENDING" ? adminPending : [],
                          });
                        }}
                      >
                        Salvar retorno
                      </button>
                    </div>
                    <textarea
                      value={adminNotes}
                      onChange={(e) => setAdminNotes(e.target.value)}
                      rows={3}
                      placeholder="Mensagem de retorno ao parceiro (pendência ou andamento)…"
                      style={{ width: "100%", marginTop: 8, fontSize: 12 }}
                    />
                    {adminStatus === "PENDING" && (
                      <div style={{ marginTop: 8 }}>
                        <small className="muted">Documentos a reenviar (lote separado):</small>
                        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 6 }}>
                          {(selected.full_required_docs ?? selected.required_docs ?? []).map((d) => (
                            <label key={d.code} style={{ fontSize: 11, display: "flex", gap: 6, alignItems: "center" }}>
                              <input
                                type="checkbox"
                                checked={adminPending.includes(d.code)}
                                onChange={(e) => {
                                  setAdminPending((prev) =>
                                    e.target.checked ? [...prev, d.code] : prev.filter((c) => c !== d.code),
                                  );
                                }}
                              />
                              {d.label}
                            </label>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                {(selected.status_log?.length ?? 0) > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <b style={{ fontSize: 12 }}>Histórico de retornos</b>
                    <ul style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 11, lineHeight: 1.5 }}>
                      {selected.status_log!.map((entry, idx) => (
                        <li key={`${entry.at}-${idx}`}>
                          <strong>{entry.status_label}</strong> — {entry.user_name} ·{" "}
                          {entry.at ? new Date(entry.at).toLocaleString("pt-BR") : "—"}
                          {entry.notes ? <div className="muted">{entry.notes}</div> : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div style={{ marginTop: 12 }}>
                  <b style={{ fontSize: 12 }}>
                    Checklist documental
                    {selected.awaiting_pendency_upload ? " — somente pendências" : ""}
                  </b>
                  <p className="muted" style={{ fontSize: 11, margin: "6px 0 8px" }}>
                    Anexe cada item do checklist. O botão <em>Transmitir documentação</em> só libera quando todos estiverem marcados.
                    {selected.awaiting_pendency_upload
                      ? " Os arquivos de pendência ficam em lote separado dos documentos iniciais."
                      : ""}
                  </p>
                  <ul style={{ margin: "0 0 12px", paddingLeft: 18, fontSize: 11, lineHeight: 1.5 }}>
                    {(selected.required_docs ?? []).map((d) => (
                      <li key={d.code} style={{ color: d.uploaded ? "#067647" : "#52605a" }}>
                        {d.uploaded ? "✓" : "○"} {d.label}
                      </li>
                    ))}
                  </ul>
                  {!isInternal && (selected.status === "AWAITING_DOCS" || selected.awaiting_pendency_upload) && (
                    <button
                      type="button"
                      className="admin-button"
                      style={{ marginBottom: 12 }}
                      disabled={busy || !selected.can_submit_documents}
                      onClick={() => void submitDocuments(selected)}
                    >
                      {selected.awaiting_pendency_upload
                        ? "Enviar documentação pendente"
                        : "Transmitir documentação para análise"}
                    </button>
                  )}
                  {(selected.status === "AWAITING_DOCS" || selected.awaiting_pendency_upload) && !selected.can_submit_documents && (
                    <p className="muted" style={{ fontSize: 10, margin: "0 0 10px" }}>
                      Faltam itens do checklist — anexe todos os tipos obrigatórios antes de transmitir.
                    </p>
                  )}
                </div>
                <AdminDocumentPanel
                  title={`Arquivos anexados (${selected.documents.length})`}
                  hint={
                    selected.awaiting_pendency_upload
                      ? "Anexe apenas os tipos marcados na pendência — serão enviados em lote separado."
                      : "Escolha o tipo do checklist no seletor e anexe o arquivo correspondente."
                  }
                  documents={selected.documents.map((d) => ({
                    ...d,
                    filename: d.upload_batch === "PENDENCY" ? `[Pendência] ${d.filename || d.doc_type}` : d.filename,
                  }))}
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
                  {commercialQuotaDisplay({
                    quota_id: q.id,
                    group_code: q.group_code,
                    quota_code: q.quota_code,
                    credit_value: q.credit_value,
                    entrada_final: q.entrada_final ?? q.credit_value,
                    installment_value: q.installment_value,
                    remaining_installments: q.remaining_installments,
                    administrator_name: q.administrator_name,
                  })}
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
              <h2 style={{ fontSize: 18, margin: "6px 0" }}>Checklists SDC (documentos obrigatórios)</h2>
              <p className="muted">Configure os itens por tipo de bem e tipo de operação (PF/PJ).</p>
            </div>
          </div>
          <div style={{ padding: "0 18px 18px" }}>
            <SdcChecklistConfigPanel />
          </div>
        </section>
      ) : null}

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
