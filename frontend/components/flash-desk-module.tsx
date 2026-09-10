"use client";

import { CheckCircle2, FileUp, RefreshCw, ShoppingCart, Landmark } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, apiForm, User } from "@/lib/api";
import { isInternalProductRole } from "@/lib/product-nav";
import { FinOpsModule } from "@/components/finops-module";
import { PreAnalysisModule } from "@/components/pre-analysis-module";

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
  required_docs: RequiredDoc[];
  documents: Array<{ id: string; doc_type: string; created_at: string | null }>;
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

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const ASSET_TYPES = [
  { value: "imovel", label: "Imóvel" },
  { value: "veiculo", label: "Veículo" },
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
  requested_amount: "",
  asset_year: "",
  asset_paid_off: true,
  asset_has_lien: false,
  docs_complete: true,
  term_months: "36",
  capital_source: "RETAIL",
};

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
  return value.replace(/\./g, "").replace(",", ".") || "0";
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

  const isInternal = isInternalProductRole(user?.role);

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
    return {
      asset_type: form.asset_type,
      asset_value: moneyPayload(form.asset_value),
      requested_amount: form.requested_amount.trim() ? moneyPayload(form.requested_amount) : null,
      asset_year: form.asset_year ? Number(form.asset_year) : null,
      asset_paid_off: form.asset_paid_off,
      asset_has_lien: form.asset_has_lien,
      docs_complete: form.docs_complete,
      term_months: Number(form.term_months),
      capital_source: form.capital_source,
    };
  }

  async function calculate() {
    setError("");
    setBusy(true);
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
    setError("");
    setBusy(true);
    try {
      const created = await api<FlashSolicitation>("/flash/desk/solicitations", {
        method: "POST",
        body: JSON.stringify({
          ...evaluatePayload(),
          contact_name: form.contact_name.trim(),
          contact_email: form.contact_email.trim(),
          contact_phone: form.contact_phone.trim(),
          document: form.document.trim() || null,
          person_type: form.person_type,
          address: form.address.trim() || null,
          occupation: form.occupation.trim() || null,
          income_value: moneyPayload(form.income_value),
        }),
      });
      setNotice(`Flash gravado: ${created.contact_name} — ${created.status_label}`);
      setForm(emptyForm);
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

  async function uploadDoc(item: FlashSolicitation, file: File) {
    setError("");
    setBusy(true);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("doc_type", docType);
      await apiForm(`/flash/desk/solicitations/${item.id}/documents`, body);
      setNotice(`Documento ${docType} anexado em ${item.contact_name}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no upload");
    } finally {
      setBusy(false);
    }
  }

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
              <div style={{ display: "grid", gap: 9, gridTemplateColumns: "1fr 1fr" }}>
                <input placeholder="Nome" value={form.contact_name} onChange={(e) => patchForm("contact_name", e.target.value)} />
                <input placeholder="E-mail" value={form.contact_email} onChange={(e) => patchForm("contact_email", e.target.value)} />
                <input placeholder="Telefone" value={form.contact_phone} onChange={(e) => patchForm("contact_phone", e.target.value)} />
                <input placeholder="CPF/CNPJ" value={form.document} onChange={(e) => patchForm("document", e.target.value)} />
                <select value={form.person_type} onChange={(e) => patchForm("person_type", e.target.value)}>
                  <option value="PF">PF</option>
                  <option value="PJ">PJ</option>
                </select>
                <select value={form.asset_type} onChange={(e) => patchForm("asset_type", e.target.value)}>
                  {ASSET_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                <input placeholder="Valor do bem (R$)" value={form.asset_value} onChange={(e) => patchForm("asset_value", e.target.value)} />
                <input placeholder="Principal solicitado (opcional, máx 40%)" value={form.requested_amount} onChange={(e) => patchForm("requested_amount", e.target.value)} />
                <select value={form.term_months} onChange={(e) => patchForm("term_months", e.target.value)}>
                  <option value="36">36 meses</option>
                  <option value="60">60 meses (balloon 36)</option>
                </select>
                <select value={form.capital_source} onChange={(e) => patchForm("capital_source", e.target.value)}>
                  <option value="RETAIL">Pool (RETAIL)</option>
                  <option value="INSTITUTIONAL">Fundo (INSTITUTIONAL)</option>
                </select>
                <input placeholder="Renda / faturamento" value={form.income_value} onChange={(e) => patchForm("income_value", e.target.value)} />
                <input placeholder="Profissão / ramo" value={form.occupation} onChange={(e) => patchForm("occupation", e.target.value)} />
                <input style={{ gridColumn: "1 / -1" }} placeholder="Endereço" value={form.address} onChange={(e) => patchForm("address", e.target.value)} />
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 14, fontSize: 12, fontWeight: 700 }}>
                <label><input type="checkbox" checked={form.asset_paid_off} onChange={(e) => patchForm("asset_paid_off", e.target.checked)} /> Bem quitado</label>
                <label><input type="checkbox" checked={form.asset_has_lien} onChange={(e) => patchForm("asset_has_lien", e.target.checked)} /> Bem com pendência</label>
                <label><input type="checkbox" checked={form.docs_complete} onChange={(e) => patchForm("docs_complete", e.target.checked)} /> Checklist lastros ok</label>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="admin-button" disabled={busy} onClick={() => void calculate()}>Calcular viabilidade</button>
                {evalResult?.viable && (
                  <button type="button" className="admin-button" disabled={busy} onClick={() => void store()}>Avançar (gravar Flash)</button>
                )}
              </div>
            </div>
            <div style={{ border: "1px solid var(--line)", borderRadius: 12, padding: 16, background: "#f7fbf9" }}>
              <b>Resultado Flash Capital</b>
              {!evalResult && <p className="muted" style={{ marginTop: 10 }}>Preencha e clique em Calcular.</p>}
              {evalResult?.viable && (
                <div style={{ display: "grid", gap: 10, marginTop: 12, gridTemplateColumns: "1fr 1fr" }}>
                  <div><small>Principal (LTV {evalResult.ltv_percent}%)</small><div><b>{brl.format(Number(evalResult.principal))}</b></div></div>
                  <div><small>Líquido ao cliente</small><div><b>{brl.format(Number(evalResult.net_payout))}</b></div></div>
                  <div><small>Fee 10%</small><div><b>{brl.format(Number(evalResult.platform_fee))}</b></div></div>
                  <div><small>ITBI 3%</small><div><b>{brl.format(Number(evalResult.itbi_provision))}</b></div></div>
                  <div><small>Parcela Price</small><div><b>{brl.format(Number(evalResult.monthly_payment))}</b></div></div>
                  <div><small>Prazo / taxa</small><div><b>{evalResult.term_months}m @ {evalResult.interest_rate_monthly}%</b></div></div>
                  <div style={{ gridColumn: "1 / -1" }}>
                    <small>Lastros obrigatórios ({evalResult.category})</small>
                    <ul style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 12 }}>
                      {evalResult.required_docs.map((d) => <li key={d.code}>{d.label}</li>)}
                    </ul>
                  </div>
                  <p style={{ gridColumn: "1 / -1", color: "#067647", fontWeight: 700 }}>{evalResult.message}</p>
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
                <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                  {selected.required_docs.map((d) => (
                    <li key={d.code}>{d.uploaded ? "✓" : "○"} {d.label}</li>
                  ))}
                </ul>
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
