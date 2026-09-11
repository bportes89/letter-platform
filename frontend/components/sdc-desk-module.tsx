"use client";

import { CheckCircle2, FileUp, RefreshCw, ShoppingCart, ClipboardList } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, apiForm, User } from "@/lib/api";
import { isInternalProductRole } from "@/lib/product-nav";
import { PreAnalysisModule } from "@/components/pre-analysis-module";
import { DeskSourceMetaRow } from "@/lib/desk-source-meta";

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
  documents: Array<{ id: string; doc_type: string; created_at: string | null }>;
  can_create_sale: boolean;
};

type EvalResult = {
  viable: boolean;
  motivos: string[];
  credito_estimado: string;
  parcela_estimada: string;
  prazo_meses: number;
  taxa_juros_mensal: string;
  message: string;
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
};

function moneyPayload(value: string) {
  return value.replace(/\./g, "").replace(",", ".") || "0";
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

  const isInternal = isInternalProductRole(user?.role);
  const needsYear = ["veiculo_leve", "veiculo_pesado", "maquina"].includes(form.asset_type);

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

  function patchForm<K extends keyof typeof emptyForm>(key: K, value: (typeof emptyForm)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setEvalResult(null);
  }

  function evaluatePayload() {
    return {
      asset_type: form.asset_type,
      asset_value: moneyPayload(form.asset_value),
      asset_year: needsYear && form.asset_year ? Number(form.asset_year) : null,
      asset_paid_off: form.asset_paid_off,
      asset_has_lien: form.asset_has_lien,
      docs_complete: form.docs_complete,
    };
  }

  async function calculate() {
    setError("");
    setBusy(true);
    try {
      const res = await api<{ result: EvalResult }>("/sdc/desk/evaluate", {
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
      const created = await api<SdcSolicitation>("/sdc/desk/solicitations", {
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
      setNotice(`SDC gravado: ${created.contact_name} — ${created.status_label}`);
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

  async function uploadDoc(item: SdcSolicitation, file: File) {
    setError("");
    setBusy(true);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("doc_type", docType);
      await apiForm(`/sdc/desk/solicitations/${item.id}/documents`, body);
      setNotice(`Documento anexado em ${item.contact_name}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no upload");
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
                  <option value="RG_CPF">RG/CPF</option>
                  <option value="COMPROVANTE_RENDA">Comprovante de renda</option>
                  <option value="MATRICULA">Matrícula / CRLV</option>
                  <option value="SDC_SUPPORT">Outro</option>
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
                <input placeholder="Profissão / ramo" value={form.occupation} onChange={(e) => patchForm("occupation", e.target.value)} />
                <input placeholder="Renda / faturamento" value={form.income_value} onChange={(e) => patchForm("income_value", e.target.value)} />
                <select value={form.asset_type} onChange={(e) => patchForm("asset_type", e.target.value)}>
                  {ASSET_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                <input placeholder="Valor do bem (R$)" value={form.asset_value} onChange={(e) => patchForm("asset_value", e.target.value)} />
                {needsYear && (
                  <input type="number" placeholder="Ano fabricação" value={form.asset_year} onChange={(e) => patchForm("asset_year", e.target.value)} />
                )}
                <input style={{ gridColumn: "1 / -1" }} placeholder="Endereço" value={form.address} onChange={(e) => patchForm("address", e.target.value)} />
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 14, fontSize: 12, fontWeight: 700 }}>
                <label><input type="checkbox" checked={form.asset_paid_off} onChange={(e) => patchForm("asset_paid_off", e.target.checked)} /> Bem quitado</label>
                <label><input type="checkbox" checked={form.asset_has_lien} onChange={(e) => patchForm("asset_has_lien", e.target.checked)} /> Bem com pendência</label>
                <label><input type="checkbox" checked={form.docs_complete} onChange={(e) => patchForm("docs_complete", e.target.checked)} /> Documentação completa</label>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="admin-button" disabled={busy} onClick={() => void calculate()}>Calcular viabilidade</button>
                {evalResult?.viable && (
                  <button type="button" className="admin-button" disabled={busy} onClick={() => void store()}>Avançar (gravar SDC)</button>
                )}
              </div>
            </div>
            <div style={{ border: "1px solid var(--line)", borderRadius: 12, padding: 16, background: "#f7fbf9" }}>
              <b>Resultado da análise</b>
              {!evalResult && <p className="muted" style={{ marginTop: 10 }}>Preencha e clique em Calcular.</p>}
              {evalResult?.viable && (
                <div style={{ display: "grid", gap: 10, marginTop: 12, gridTemplateColumns: "1fr 1fr" }}>
                  <div><small>Valor alavancado</small><div><b>{brl.format(Number(evalResult.credito_estimado))}</b></div></div>
                  <div><small>Prazo</small><div><b>{evalResult.prazo_meses} meses</b></div></div>
                  <div><small>Parcela</small><div><b>{brl.format(Number(evalResult.parcela_estimada))}</b></div></div>
                  <div><small>Taxa</small><div><b>{evalResult.taxa_juros_mensal}% a.m.</b></div></div>
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
                    <td>{item.documents.length}</td>
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
                <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                  {selected.documents.map((d) => (
                    <li key={d.id}>{d.doc_type} — {d.created_at ? new Date(d.created_at).toLocaleString("pt-BR") : "—"}</li>
                  ))}
                </ul>
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
