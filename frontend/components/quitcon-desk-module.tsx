"use client";

import { CheckCircle2, FileUp, RefreshCw, ShoppingCart, Scale } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AdminDocumentPanel } from "@/components/admin-document-panel";
import { api, apiForm, deleteApi, downloadApi, User } from "@/lib/api";
import { isInternalProductRole } from "@/lib/product-nav";
import { QuitConModule } from "@/components/quitcon-module";
import { DeskSourceMetaRow } from "@/lib/desk-source-meta";
import { PartnerSociosFields, SocioPartner, sociosPayload } from "@/components/partner-socios-fields";
import { CurrencyInput } from "@/components/currency-input";
import { lookupCep } from "@/lib/cep-lookup";

type RequiredDoc = { code: string; label: string; uploaded?: boolean };

type QuitConSolicitation = {
  id: string;
  status: string;
  status_label: string;
  contact_name: string;
  contact_email: string;
  outstanding_balance: string;
  meses_restantes: number;
  registry_number: string;
  registry_office: string;
  quitacao_vp_amount: string;
  operational_service: boolean;
  proposal_id: string | null;
  quitcon_operacao_id: string | null;
  source_channel: string | null;
  source_channel_label: string | null;
  lead_id: string | null;
  required_docs: RequiredDoc[];
  documents: Array<{ id: string; doc_type: string; document_id?: string | null; filename?: string | null; status?: string | null; created_at: string | null }>;
  can_create_sale: boolean;
};

type QuotaBreakdownRow = {
  registry_number: string;
  saldo_devedor_calculado: string;
  valor_quitacao_vp: string;
  economia_linha: string;
};

type EvalResult = {
  viable: boolean;
  motivos: string[];
  required_docs: RequiredDoc[];
  valor_presente_quitacao: string;
  custos_entrada?: {
    total_obrigatorio_abertura: string;
    total_com_servico_operacional: string;
    itens: Array<{ codigo: string; nome: string; valor: string | null; aplicavel?: boolean }>;
  } | null;
  cedente?: { pagamento_total_quitacao_mais_intermediacao: string };
  cessionario?: { capital_giro_liquido_na_liberacao: string };
  quota_breakdown?: QuotaBreakdownRow[];
  totais?: { saldo_devedor_total: string; quitacao_vp_total: string; economia_total: string };
  message: string;
};

type AddressFields = {
  zip: string;
  street: string;
  number: string;
  complement: string;
  district: string;
  city: string;
  state: string;
};

type QuotaLine = {
  group_code: string;
  quota_code: string;
  credit_at_billing: string;
  installment_value: string;
  meses_restantes: string;
};

const OPERATIONAL_SERVICE_DISCLAIMER =
  "Declaro estar de acordo com a taxa de serviço LETTER (2% sobre a quitação VP): valor não reembolsável, " +
  "referente exclusivamente à intermediação/representação junto à administradora, e que não se confunde com o " +
  "fee de sucesso cobrado após a conclusão da operação.";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const STATUS_OPTIONS = [
  { value: "AWAITING_DOCS", label: "Aguardando Documentação" },
  { value: "UNDER_REVIEW", label: "Em Análise" },
  { value: "PENDING", label: "Pendente" },
  { value: "APPROVED", label: "Aprovado" },
  { value: "REJECTED", label: "Reprovado" },
  { value: "CANCELLED", label: "Cancelado" },
] as const;

const ADMINS = ["Embracon", "Ademicon", "Ancora", "HS", "Tradicao", "Recon", "Groscon", "Roma", "Reserva"];

const emptyForm = {
  contact_name: "",
  contact_email: "",
  contact_phone: "",
  document: "",
  person_type: "PF",
  address: "",
  occupation: "",
  income_value: "",
  registry_office: "Embracon",
  property_type: "VEICULO",
  operational_service: false,
  operational_service_accepted: false,
  contemplada: true,
  bem_faturado: true,
  parcelas_em_dia: true,
  docs_complete: true,
};

const emptyAddress = (): AddressFields => ({
  zip: "",
  street: "",
  number: "",
  complement: "",
  district: "",
  city: "",
  state: "",
});

const emptyQuotaLine = (): QuotaLine => ({
  group_code: "",
  quota_code: "",
  credit_at_billing: "",
  installment_value: "",
  meses_restantes: "",
});

function parseMoney(value: string): number {
  const raw = String(value || "").trim();
  if (!raw) return 0;
  if (raw.includes(",")) return Number(raw.replace(/\./g, "").replace(",", ".")) || 0;
  return Number(raw) || 0;
}

function moneyPayload(value: string) {
  const n = parseMoney(value);
  return n ? String(n) : "0";
}

function quotaSaldo(line: QuotaLine): number {
  const parcela = parseMoney(line.installment_value);
  const meses = Number(line.meses_restantes);
  if (!parcela || !Number.isFinite(meses) || meses < 1) return 0;
  return parcela * meses;
}

function quotaVp(saldo: number, meses: number): number {
  if (!saldo || meses < 1) return 0;
  return saldo / (1 + 0.01 * meses);
}

function composeAddress(addr: AddressFields): string {
  return [addr.street, addr.number, addr.complement, addr.district, addr.city, addr.state, addr.zip]
    .map((p) => p.trim())
    .filter(Boolean)
    .join(", ");
}

function addressPayload(addr: AddressFields) {
  return {
    zip: addr.zip.trim(),
    street: addr.street.trim(),
    number: addr.number.trim(),
    complement: addr.complement.trim(),
    district: addr.district.trim(),
    city: addr.city.trim(),
    state: addr.state.trim(),
  };
}

export function QuitConDeskModule() {
  const [tab, setTab] = useState<"nova" | "lista" | "venda">("nova");
  const [user, setUser] = useState<User | null>(null);
  const [items, setItems] = useState<QuitConSolicitation[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [evalResult, setEvalResult] = useState<EvalResult | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [docType, setDocType] = useState("EXTRATO_CONSORCIO");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [lastCheckout, setLastCheckout] = useState<Record<string, unknown> | null>(null);
  const [quotaLines, setQuotaLines] = useState<QuotaLine[]>([emptyQuotaLine()]);
  const [clientAddress, setClientAddress] = useState<AddressFields>(emptyAddress());
  const [assetAddress, setAssetAddress] = useState<AddressFields>(emptyAddress());
  const [alienatedRegistry, setAlienatedRegistry] = useState("");
  const [alienatedPlate, setAlienatedPlate] = useState("");
  const [alienatedChassi, setAlienatedChassi] = useState("");
  const [alienatedRenavam, setAlienatedRenavam] = useState("");
  const [socios, setSocios] = useState<SocioPartner[]>([]);

  const isInternal = isInternalProductRole(user?.role);
  const isImovel =
    form.property_type === "IMOVEL_URBANO" || form.property_type === "IMOVEL_RURAL";

  const load = useCallback(async () => {
    const [me, list] = await Promise.all([
      api<User>("/auth/me"),
      api<QuitConSolicitation[]>("/quitcon/desk/solicitations"),
    ]);
    setUser(me);
    setItems(list);
  }, []);

  useEffect(() => {
    setLoading(true);
    load()
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar mesa QuitCon"))
      .finally(() => setLoading(false));
  }, [load]);

  const filtered = useMemo(
    () => (statusFilter === "ALL" ? items : items.filter((i) => i.status === statusFilter)),
    [items, statusFilter],
  );
  const selected = useMemo(() => items.find((i) => i.id === selectedId) ?? null, [items, selectedId]);
  const approvedForSale = useMemo(() => items.filter((i) => i.can_create_sale), [items]);

  function patchForm<K extends keyof typeof emptyForm>(key: K, value: (typeof emptyForm)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setEvalResult(null);
  }

  const quotaPreview = useMemo(() => {
    const lines = quotaLines.filter((q) => q.group_code.trim() && q.quota_code.trim());
    let totalSaldo = 0;
    let totalVp = 0;
    let maxMeses = 0;
    const rows = lines.map((q) => {
      const meses = Number(q.meses_restantes);
      const saldo = quotaSaldo(q);
      const vp = quotaVp(saldo, meses);
      totalSaldo += saldo;
      totalVp += vp;
      if (Number.isFinite(meses)) maxMeses = Math.max(maxMeses, meses);
      return { line: q, saldo, vp, meses };
    });
    const registry =
      lines.length === 0
        ? ""
        : lines.length === 1
          ? `${lines[0].group_code.trim()}/${lines[0].quota_code.trim()}`
          : `${lines[0].group_code.trim()}/${lines[0].quota_code.trim()} (+${lines.length - 1} cotas)`;
    return { rows, totalSaldo, totalVp, maxMeses, registry, economia: totalSaldo - totalVp };
  }, [quotaLines]);

  function buildQuotaLinesPayload() {
    const active = quotaLines.filter((q) => q.group_code.trim() || q.quota_code.trim());
    if (!active.length) throw new Error("Informe ao menos uma cota (grupo e cota).");
    return active.map((q) => {
      const label = `${q.group_code.trim() || "?"}/${q.quota_code.trim() || "?"}`;
      const meses = Number(q.meses_restantes);
      if (!q.group_code.trim() || !q.quota_code.trim()) {
        throw new Error("Preencha grupo e cota em todas as linhas.");
      }
      if (!Number.isFinite(meses) || meses < 1 || meses > 240) {
        throw new Error(`Prazo restante inválido na cota ${label}.`);
      }
      if (parseMoney(q.installment_value) <= 0) {
        throw new Error(`Informe a parcela atual na cota ${label}.`);
      }
      if (parseMoney(q.credit_at_billing) <= 0) {
        throw new Error(`Informe o crédito no faturamento na cota ${label}.`);
      }
      return {
        group_code: q.group_code.trim(),
        quota_code: q.quota_code.trim(),
        installment_value: moneyPayload(q.installment_value),
        meses_restantes: meses,
        credit_at_billing: moneyPayload(q.credit_at_billing),
      };
    });
  }

  function addressValidationMessage(addr: AddressFields, label: string): string | null {
    if (!addr.zip.trim()) return `${label}: informe o CEP.`;
    if (!addr.street.trim()) return `${label}: informe o logradouro.`;
    if (!addr.number.trim()) return `${label}: informe o número.`;
    if (!addr.city.trim()) return `${label}: informe a cidade.`;
    if (!addr.state.trim()) return `${label}: informe a UF.`;
    return null;
  }

  function validateBeforeStore(): string | null {
    if (!form.contact_name.trim()) return "Informe o nome do cliente.";
    if (!form.contact_email.trim()) return "Informe o e-mail do cliente.";
    if (!form.contact_phone.trim()) return "Informe o telefone do cliente.";
    if (!form.registry_office.trim()) return "Informe a administradora.";
    try {
      buildQuotaLinesPayload();
    } catch (e) {
      return e instanceof Error ? e.message : "Revise os dados das cotas.";
    }
    const clientAddrMsg = addressValidationMessage(clientAddress, "Endereço do cliente");
    if (clientAddrMsg) return clientAddrMsg;
    const assetAddrMsg = addressValidationMessage(assetAddress, "Endereço do bem alienado");
    if (assetAddrMsg) return assetAddrMsg;
    if (isImovel && !alienatedRegistry.trim()) return "Informe a matrícula do imóvel alienado.";
    if (!isImovel && !alienatedPlate.trim() && !alienatedChassi.trim()) {
      return "Informe placa ou chassi do veículo alienado.";
    }
    if (form.operational_service && !form.operational_service_accepted) {
      return "Marque o aceite da taxa de serviço LETTER (2%) para gravar a solicitação.";
    }
    if (!evalResult?.viable) return "Calcule a viabilidade antes de avançar.";
    return null;
  }

  function evaluatePayload() {
    const quota_lines = buildQuotaLinesPayload();
    let totalSaldo = 0;
    let maxMeses = 0;
    for (const q of quota_lines) {
      totalSaldo += Number(q.installment_value) * q.meses_restantes;
      maxMeses = Math.max(maxMeses, q.meses_restantes);
    }
    const registry =
      quota_lines.length === 1
        ? `${quota_lines[0].group_code}/${quota_lines[0].quota_code}`
        : `${quota_lines[0].group_code}/${quota_lines[0].quota_code} (+${quota_lines.length - 1} cotas)`;
    if (!registry || totalSaldo <= 0 || maxMeses < 1) {
      throw new Error("Revise as cotas: parcela, prazo e valores para calcular o saldo.");
    }
    return {
      quota_lines,
      outstanding_balance: String(totalSaldo),
      meses_restantes: maxMeses,
      registry_number: registry,
      registry_office: form.registry_office.trim(),
      property_type: form.property_type,
      operational_service: form.operational_service,
      contemplada: form.contemplada,
      bem_faturado: form.bem_faturado,
      parcelas_em_dia: form.parcelas_em_dia,
      docs_complete: form.docs_complete,
    };
  }

  async function fillClientCep(cep: string) {
    const addr = await lookupCep(cep);
    if (!addr) return;
    setClientAddress((prev) => ({
      ...prev,
      zip: addr.zipcode || prev.zip,
      street: addr.street || prev.street,
      district: addr.neighborhood || prev.district,
      city: addr.city || prev.city,
      state: addr.uf || prev.state,
    }));
    setEvalResult(null);
  }

  async function fillAssetCep(cep: string) {
    const addr = await lookupCep(cep);
    if (!addr) return;
    setAssetAddress((prev) => ({
      ...prev,
      zip: addr.zipcode || prev.zip,
      street: addr.street || prev.street,
      district: addr.neighborhood || prev.district,
      city: addr.city || prev.city,
      state: addr.uf || prev.state,
    }));
    setEvalResult(null);
  }

  async function validateContactFields() {
    const { validationMessageForPerson } = await import("@/lib/br-validation");
    const docMsg = validationMessageForPerson(form.document, form.contact_email, form.contact_phone);
    if (docMsg) throw new Error(docMsg);
  }

  async function calculate() {
    setError("");
    setBusy(true);
    try {
      const payload = evaluatePayload();
      const res = await api<{ result: EvalResult }>("/quitcon/desk/evaluate", {
        method: "POST",
        body: JSON.stringify(payload),
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
      await validateContactFields();
      const payload = evaluatePayload();
      const assetFormatted = composeAddress(assetAddress);
      const created = await api<QuitConSolicitation>("/quitcon/desk/solicitations", {
        method: "POST",
        body: JSON.stringify({
          ...payload,
          contact_name: form.contact_name.trim(),
          contact_email: form.contact_email.trim(),
          contact_phone: form.contact_phone.trim(),
          document: form.document.trim() || null,
          person_type: form.person_type,
          address: composeAddress(clientAddress) || null,
          occupation: form.occupation.trim() || null,
          income_value: moneyPayload(form.income_value),
          client_address_json: addressPayload(clientAddress),
          asset_address_json: addressPayload(assetAddress),
          operational_service_accepted: form.operational_service_accepted,
          alienated_property_registry: isImovel ? alienatedRegistry.trim() || null : null,
          alienated_asset_address: assetFormatted || null,
          alienated_vehicle_plate: !isImovel ? alienatedPlate.trim() || null : null,
          alienated_vehicle_chassi: !isImovel ? alienatedChassi.trim() || null : null,
          alienated_vehicle_renavam: !isImovel ? alienatedRenavam.trim() || null : null,
          partners_json: sociosPayload(socios),
        }),
      });
      setNotice(`QuitCon gravado: ${created.contact_name} — ${created.status_label}`);
      setForm(emptyForm);
      setQuotaLines([emptyQuotaLine()]);
      setClientAddress(emptyAddress());
      setAssetAddress(emptyAddress());
      setAlienatedRegistry("");
      setAlienatedPlate("");
      setAlienatedChassi("");
      setAlienatedRenavam("");
      setSocios([]);
      setEvalResult(null);
      setSelectedId(created.id);
      setTab("lista");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao gravar solicitação");
    } finally {
      setBusy(false);
    }
  }

  async function updateStatus(item: QuitConSolicitation, status: string) {
    setError("");
    setBusy(true);
    try {
      const updated = await api<QuitConSolicitation>(`/quitcon/desk/solicitations/${item.id}`, {
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

  async function uploadDoc(item: QuitConSolicitation, file: File, type = docType) {
    setError("");
    setBusy(true);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("doc_type", type);
      await apiForm(`/quitcon/desk/solicitations/${item.id}/documents`, body);
      setNotice(`Documento anexado em ${item.contact_name}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no upload");
    } finally {
      setBusy(false);
    }
  }

  async function deleteDoc(item: QuitConSolicitation, docId: string) {
    setError("");
    setBusy(true);
    try {
      await deleteApi(`/quitcon/desk/solicitations/${item.id}/documents/${docId}`);
      setNotice("Documento excluído.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao excluir documento");
    } finally {
      setBusy(false);
    }
  }

  const quitconDocTypeOptions = useMemo(
    () =>
      (selected?.required_docs?.length
        ? selected.required_docs
        : [
            { code: "EXTRATO_CONSORCIO", label: "Extrato" },
            { code: "CONTRATO_CONSORCIO", label: "Contrato" },
            { code: "DOCUMENTOS_PESSOAIS", label: "Docs pessoais" },
            { code: "COMPROVANTE_PARCELAS", label: "Parcelas" },
          ]
      ).map((d) => ({ value: d.code, label: d.label })),
    [selected],
  );

  async function createSale() {
    if (!selectedId) return;
    setError("");
    setBusy(true);
    try {
      const res = await api<{
        message: string;
        quitcon_operacao_id: string;
        operacao_code: string;
        tapaf_checkout: Record<string, unknown>;
      }>(`/quitcon/desk/solicitations/${selectedId}/sale`, { method: "POST" });
      setNotice(`${res.message} (${res.operacao_code})`);
      setLastCheckout(res.tapaf_checkout);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao abrir operação");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="loading">Carregando mesa QuitCon…</div>;

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">COMERCIAL</span>
          <h1>QuitCon</h1>
          <p>
            Mesa doc253: simular VP e custos de entrada → documentos/status → abrir operação em AGUARDANDO_TAPAF.
            Parceiro anexa docs; operação LETTER altera status.
          </p>
        </div>
        <div className="operational-icon"><Scale /></div>
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
            3. Abrir operação
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
                Tipo doc
                <select value={docType} onChange={(e) => setDocType(e.target.value)} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid var(--line)" }}>
                  {(selected?.required_docs?.length
                    ? selected.required_docs
                    : [
                        { code: "EXTRATO_CONSORCIO", label: "Extrato" },
                        { code: "CONTRATO_CONSORCIO", label: "Contrato" },
                        { code: "DOCUMENTOS_PESSOAIS", label: "Docs pessoais" },
                        { code: "COMPROVANTE_PARCELAS", label: "Parcelas" },
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
              <div style={{ display: "grid", gap: 9, gridTemplateColumns: "1fr 1fr" }}>
                <input placeholder="Nome" value={form.contact_name} onChange={(e) => patchForm("contact_name", e.target.value)} />
                <input placeholder="E-mail" value={form.contact_email} onChange={(e) => patchForm("contact_email", e.target.value)} />
                <input placeholder="Telefone" value={form.contact_phone} onChange={(e) => patchForm("contact_phone", e.target.value)} />
                <input placeholder="CPF/CNPJ" value={form.document} onChange={(e) => patchForm("document", e.target.value)} />
                <select value={form.property_type} onChange={(e) => patchForm("property_type", e.target.value)} style={{ gridColumn: "1 / -1" }}>
                  <option value="VEICULO">Veículo</option>
                  <option value="PESADOS">Pesados</option>
                  <option value="IMOVEL_URBANO">Imóvel urbano</option>
                  <option value="IMOVEL_RURAL">Imóvel rural</option>
                </select>
              </div>

              <div style={{ display: "grid", gap: 8 }}>
                <b>Endereço do cliente (contrato)</b>
                <div style={{ display: "grid", gap: 8, gridTemplateColumns: "120px 1fr 1fr" }}>
                  <input
                    placeholder="CEP"
                    value={clientAddress.zip}
                    onChange={(e) => {
                      setClientAddress({ ...clientAddress, zip: e.target.value });
                      setEvalResult(null);
                    }}
                    onBlur={(e) => void fillClientCep(e.target.value)}
                  />
                  <input
                    placeholder="Logradouro"
                    value={clientAddress.street}
                    onChange={(e) => {
                      setClientAddress({ ...clientAddress, street: e.target.value });
                      setEvalResult(null);
                    }}
                    style={{ gridColumn: "span 2" }}
                  />
                  <input
                    placeholder="Número"
                    value={clientAddress.number}
                    onChange={(e) => {
                      setClientAddress({ ...clientAddress, number: e.target.value });
                      setEvalResult(null);
                    }}
                  />
                  <input
                    placeholder="Complemento"
                    value={clientAddress.complement}
                    onChange={(e) => {
                      setClientAddress({ ...clientAddress, complement: e.target.value });
                      setEvalResult(null);
                    }}
                  />
                  <input
                    placeholder="Bairro"
                    value={clientAddress.district}
                    onChange={(e) => {
                      setClientAddress({ ...clientAddress, district: e.target.value });
                      setEvalResult(null);
                    }}
                  />
                  <input
                    placeholder="Cidade"
                    value={clientAddress.city}
                    onChange={(e) => {
                      setClientAddress({ ...clientAddress, city: e.target.value });
                      setEvalResult(null);
                    }}
                  />
                  <input
                    placeholder="UF"
                    value={clientAddress.state}
                    maxLength={2}
                    onChange={(e) => {
                      setClientAddress({ ...clientAddress, state: e.target.value.toUpperCase() });
                      setEvalResult(null);
                    }}
                  />
                </div>
              </div>

              <p className="muted" style={{ fontSize: 12, lineHeight: 1.5, margin: 0 }}>
                A quitação QuitCon é permitida apenas para cotas com o <b>bem já faturado</b>. Informe somente as cotas
                <b> alienadas ao mesmo bem</b> (junção de cotas). Use o botão abaixo para incluir cada cota do conjunto.
              </p>

              <div style={{ display: "grid", gap: 8 }}>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
                  <b>Cotas do bem</b>
                  <label style={{ fontSize: 12, fontWeight: 700 }}>
                    Administradora
                    <select
                      value={form.registry_office}
                      onChange={(e) => patchForm("registry_office", e.target.value)}
                      style={{ marginLeft: 8, padding: "8px 10px", borderRadius: 8, border: "1px solid var(--line)" }}
                    >
                      {ADMINS.map((a) => <option key={a} value={a}>{a}</option>)}
                    </select>
                  </label>
                </div>
                {quotaLines.map((line, idx) => {
                  const saldo = quotaSaldo(line);
                  const meses = Number(line.meses_restantes);
                  const vp = quotaVp(saldo, meses);
                  return (
                    <div
                      key={idx}
                      style={{
                        display: "grid",
                        gap: 8,
                        padding: 10,
                        border: "1px solid var(--line)",
                        borderRadius: 10,
                        background: "#fafcfb",
                      }}
                    >
                      <div style={{ display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr 1fr 1fr 100px auto" }}>
                        <input
                          placeholder="Grupo"
                          value={line.group_code}
                          onChange={(e) => {
                            const next = [...quotaLines];
                            next[idx] = { ...next[idx], group_code: e.target.value };
                            setQuotaLines(next);
                            setEvalResult(null);
                          }}
                        />
                        <input
                          placeholder="Cota"
                          value={line.quota_code}
                          onChange={(e) => {
                            const next = [...quotaLines];
                            next[idx] = { ...next[idx], quota_code: e.target.value };
                            setQuotaLines(next);
                            setEvalResult(null);
                          }}
                        />
                        <CurrencyInput
                          placeholder="Crédito no faturamento"
                          value={line.credit_at_billing}
                          onChange={(v) => {
                            const next = [...quotaLines];
                            next[idx] = { ...next[idx], credit_at_billing: v };
                            setQuotaLines(next);
                            setEvalResult(null);
                          }}
                        />
                        <CurrencyInput
                          placeholder="Parcela atual"
                          value={line.installment_value}
                          onChange={(v) => {
                            const next = [...quotaLines];
                            next[idx] = { ...next[idx], installment_value: v };
                            setQuotaLines(next);
                            setEvalResult(null);
                          }}
                        />
                        <input
                          type="number"
                          min={1}
                          max={240}
                          placeholder="Meses"
                          value={line.meses_restantes}
                          onChange={(e) => {
                            const next = [...quotaLines];
                            next[idx] = { ...next[idx], meses_restantes: e.target.value };
                            setQuotaLines(next);
                            setEvalResult(null);
                          }}
                        />
                        {quotaLines.length > 1 && (
                          <button
                            type="button"
                            className="table-action"
                            onClick={() => {
                              setQuotaLines(quotaLines.filter((_, i) => i !== idx));
                              setEvalResult(null);
                            }}
                          >
                            Remover
                          </button>
                        )}
                      </div>
                      {saldo > 0 && meses >= 1 && (
                        <div style={{ fontSize: 11, color: "#52605a", display: "flex", flexWrap: "wrap", gap: 14 }}>
                          <span>Saldo devedor: <b>{brl.format(saldo)}</b></span>
                          <span>Quitação VP (1% a.m.): <b>{brl.format(vp)}</b></span>
                          <span>Economia: <b>{brl.format(saldo - vp)}</b></span>
                        </div>
                      )}
                    </div>
                  );
                })}
                <button
                  type="button"
                  className="table-action"
                  onClick={() => {
                    setQuotaLines([...quotaLines, emptyQuotaLine()]);
                    setEvalResult(null);
                  }}
                >
                  + Adicionar cota
                </button>
                {quotaPreview.totalSaldo > 0 && (
                  <div style={{ fontSize: 12, fontWeight: 700, padding: "8px 10px", background: "#eef8f3", borderRadius: 8 }}>
                    Total saldo devedor: {brl.format(quotaPreview.totalSaldo)} · Total quitação VP:{" "}
                    {brl.format(quotaPreview.totalVp)} · Economia: {brl.format(quotaPreview.economia)}
                  </div>
                )}
              </div>

              <div style={{ display: "grid", gap: 8 }}>
                <b>Endereço do bem alienado (contrato)</b>
                {isImovel && (
                  <input
                    placeholder="Matrícula do imóvel"
                    value={alienatedRegistry}
                    onChange={(e) => setAlienatedRegistry(e.target.value)}
                  />
                )}
                {!isImovel && (
                  <div style={{ display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr" }}>
                    <input placeholder="Placa" value={alienatedPlate} onChange={(e) => setAlienatedPlate(e.target.value)} />
                    <input placeholder="Renavam" value={alienatedRenavam} onChange={(e) => setAlienatedRenavam(e.target.value)} />
                    <input
                      placeholder="Chassi"
                      value={alienatedChassi}
                      onChange={(e) => setAlienatedChassi(e.target.value)}
                      style={{ gridColumn: "1 / -1" }}
                    />
                  </div>
                )}
                <div style={{ display: "grid", gap: 8, gridTemplateColumns: "120px 1fr 1fr" }}>
                  <input
                    placeholder="CEP do bem"
                    value={assetAddress.zip}
                    onChange={(e) => {
                      setAssetAddress({ ...assetAddress, zip: e.target.value });
                      setEvalResult(null);
                    }}
                    onBlur={(e) => void fillAssetCep(e.target.value)}
                  />
                  <input
                    placeholder="Logradouro"
                    value={assetAddress.street}
                    onChange={(e) => {
                      setAssetAddress({ ...assetAddress, street: e.target.value });
                      setEvalResult(null);
                    }}
                    style={{ gridColumn: "span 2" }}
                  />
                  <input
                    placeholder="Número"
                    value={assetAddress.number}
                    onChange={(e) => {
                      setAssetAddress({ ...assetAddress, number: e.target.value });
                      setEvalResult(null);
                    }}
                  />
                  <input
                    placeholder="Complemento"
                    value={assetAddress.complement}
                    onChange={(e) => {
                      setAssetAddress({ ...assetAddress, complement: e.target.value });
                      setEvalResult(null);
                    }}
                  />
                  <input
                    placeholder="Bairro"
                    value={assetAddress.district}
                    onChange={(e) => {
                      setAssetAddress({ ...assetAddress, district: e.target.value });
                      setEvalResult(null);
                    }}
                  />
                  <input
                    placeholder="Cidade"
                    value={assetAddress.city}
                    onChange={(e) => {
                      setAssetAddress({ ...assetAddress, city: e.target.value });
                      setEvalResult(null);
                    }}
                  />
                  <input
                    placeholder="UF"
                    value={assetAddress.state}
                    maxLength={2}
                    onChange={(e) => {
                      setAssetAddress({ ...assetAddress, state: e.target.value.toUpperCase() });
                      setEvalResult(null);
                    }}
                  />
                </div>
              </div>
              <PartnerSociosFields value={socios} onChange={setSocios} />
              <div style={{ display: "flex", flexWrap: "wrap", gap: 14, fontSize: 12, fontWeight: 700 }}>
                <label><input type="checkbox" checked={form.contemplada} onChange={(e) => patchForm("contemplada", e.target.checked)} /> Contemplada</label>
                <label><input type="checkbox" checked={form.bem_faturado} onChange={(e) => patchForm("bem_faturado", e.target.checked)} /> Bem faturado</label>
                <label><input type="checkbox" checked={form.parcelas_em_dia} onChange={(e) => patchForm("parcelas_em_dia", e.target.checked)} /> Parcelas em dia</label>
                <label>
                  <input
                    type="checkbox"
                    checked={form.operational_service}
                    onChange={(e) => {
                      patchForm("operational_service", e.target.checked);
                      if (!e.target.checked) patchForm("operational_service_accepted", false);
                    }}
                  />
                  Serviço LETTER 2%
                </label>
                <label><input type="checkbox" checked={form.docs_complete} onChange={(e) => patchForm("docs_complete", e.target.checked)} /> Docs ok</label>
              </div>
              {form.operational_service && (
                <label style={{ fontSize: 11, lineHeight: 1.45, display: "flex", gap: 8, alignItems: "flex-start" }}>
                  <input
                    type="checkbox"
                    checked={form.operational_service_accepted}
                    onChange={(e) => patchForm("operational_service_accepted", e.target.checked)}
                  />
                  <span>{OPERATIONAL_SERVICE_DISCLAIMER}</span>
                </label>
              )}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="admin-button" disabled={busy} onClick={() => void calculate()}>Calcular viabilidade</button>
              </div>
            </div>
            <div style={{ border: "1px solid var(--line)", borderRadius: 12, padding: 16, background: "#f7fbf9" }}>
              <b>Resultado doc253</b>
              {!evalResult && <p className="muted" style={{ marginTop: 10 }}>Preencha as cotas e clique em Calcular viabilidade.</p>}
              {evalResult?.required_docs?.length && (
                <p className="muted" style={{ fontSize: 11, marginTop: 10, marginBottom: 0, lineHeight: 1.45 }}>
                  Após gravar, na aba Acompanhamento você anexará {evalResult.required_docs.length} documentos do checklist.
                </p>
              )}
              {evalResult?.viable && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
                <div style={{ display: "grid", gap: 10 }}>
                  {evalResult.totais && (
                    <>
                      <div><small>Saldo devedor total</small><div><b>{brl.format(Number(evalResult.totais.saldo_devedor_total))}</b></div></div>
                      <div><small>Economia estimada</small><div><b>{brl.format(Number(evalResult.totais.economia_total))}</b></div></div>
                    </>
                  )}
                  {evalResult.quota_breakdown && evalResult.quota_breakdown.length > 0 && (
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 11 }}>
                      {evalResult.quota_breakdown.map((row) => (
                        <li key={row.registry_number}>
                          {row.registry_number}: saldo {brl.format(Number(row.saldo_devedor_calculado))} → VP{" "}
                          {brl.format(Number(row.valor_quitacao_vp))}
                        </li>
                      ))}
                    </ul>
                  )}
                  <div><small>VP quitação total</small><div><b>{brl.format(Number(evalResult.valor_presente_quitacao))}</b></div></div>
                  {evalResult.cedente && (
                    <div><small>Cedente (VP+3%)</small><div><b>{brl.format(Number(evalResult.cedente.pagamento_total_quitacao_mais_intermediacao))}</b></div></div>
                  )}
                  {evalResult.cessionario && (
                    <div><small>Capital giro líquido (VP−5%)</small><div><b>{brl.format(Number(evalResult.cessionario.capital_giro_liquido_na_liberacao))}</b></div></div>
                  )}
                  {evalResult.custos_entrada && (
                    <div>
                      <small>Custos de entrada</small>
                      <ul style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 12 }}>
                        {evalResult.custos_entrada.itens
                          .filter((i) => i.aplicavel !== false && i.valor)
                          .map((i) => (
                            <li key={i.codigo}>{i.nome}: {brl.format(Number(i.valor))}</li>
                          ))}
                      </ul>
                      <div style={{ marginTop: 8 }}>
                        <b>Total abertura: {brl.format(Number(evalResult.custos_entrada.total_com_servico_operacional))}</b>
                      </div>
                    </div>
                  )}
                  <p style={{ color: "#067647", fontWeight: 700, margin: 0 }}>{evalResult.message}</p>
                </div>
                  <button
                    type="button"
                    className="admin-button"
                    style={{ width: "100%" }}
                    disabled={busy}
                    onClick={() => void store()}
                  >
                    Avançar e gravar QuitCon
                  </button>
                </div>
              )}
              {evalResult && !evalResult.viable && (
                <div style={{ marginTop: 12 }}>
                  <p style={{ color: "#b42318", fontWeight: 700 }}>{evalResult.message}</p>
                  <ul>{evalResult.motivos.map((m) => <li key={m}>{m}</li>)}</ul>
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
                  <th>ADM / cota</th>
                  <th>Saldo</th>
                  <th>VP</th>
                  <th>Status</th>
                  <th>Docs</th>
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
                        {item.registry_office}
                        <div className="muted" style={{ fontSize: 11 }}>{item.registry_number}</div>
                      </td>
                      <td>{brl.format(Number(item.outstanding_balance))}</td>
                      <td>{brl.format(Number(item.quitacao_vp_amount))}</td>
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
                            <ShoppingCart />Abrir
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
                <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                  {selected.required_docs.map((d) => (
                    <li key={d.code}>{d.uploaded ? "✓" : "○"} {d.label}</li>
                  ))}
                </ul>
                <AdminDocumentPanel
                  title={`Documentos anexados (${selected.documents.length})`}
                  hint="Anexe, baixe ou exclua arquivos desta solicitação QuitCon."
                  documents={selected.documents}
                  busy={busy}
                  canDelete={isInternal}
                  docTypeOptions={quitconDocTypeOptions}
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
            <p className="muted">Abre proposta QUITCON + operação em AGUARDANDO_TAPAF com checkout TAPAF R$ 1.500.</p>
            <select value={selectedId ?? ""} onChange={(e) => setSelectedId(e.target.value || null)}>
              <option value="">QuitCon aprovado…</option>
              {approvedForSale.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.contact_name} — VP {brl.format(Number(i.quitacao_vp_amount))}
                </option>
              ))}
            </select>
            <button type="button" className="admin-button" disabled={!selectedId || busy} onClick={() => void createSale()}>
              Abrir operação QuitCon
            </button>
            {lastCheckout && (
              <div className="notice">
                <b>Checkout TAPAF</b>
                <div>Valor: {String(lastCheckout.valor_tapaf_brl ?? "1500.00")}</div>
                <small>{String(lastCheckout.texto_tooltip ?? "")}</small>
              </div>
            )}
          </div>
        )}
      </section>

      {isInternal ? (
        <section className="panel operational-panel" style={{ marginTop: 16 }}>
          <div className="page-heading" style={{ marginBottom: 8 }}>
            <div>
              <span className="eyebrow dark">INTERNO</span>
              <h2 style={{ fontSize: 18, margin: "6px 0" }}>Esteira FinOps QuitCon</h2>
            </div>
          </div>
          <QuitConModule />
        </section>
      ) : null}
    </>
  );
}
