"use client";

import { CheckCircle2, FileUp, RefreshCw, ShoppingCart, Scale } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, apiForm, User } from "@/lib/api";
import { isInternalProductRole } from "@/lib/product-nav";
import { QuitConModule } from "@/components/quitcon-module";

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
  required_docs: RequiredDoc[];
  documents: Array<{ id: string; doc_type: string; created_at: string | null }>;
  can_create_sale: boolean;
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
  message: string;
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
  outstanding_balance: "",
  meses_restantes: "48",
  registry_number: "",
  registry_office: "Embracon",
  property_type: "CONSORCIO",
  operational_service: false,
  contemplada: true,
  bem_faturado: true,
  parcelas_em_dia: true,
  docs_complete: true,
};

function moneyPayload(value: string) {
  return value.replace(/\./g, "").replace(",", ".") || "0";
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

  const isInternal = isInternalProductRole(user?.role);

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

  function evaluatePayload() {
    return {
      outstanding_balance: moneyPayload(form.outstanding_balance),
      meses_restantes: Number(form.meses_restantes),
      registry_number: form.registry_number.trim(),
      registry_office: form.registry_office.trim(),
      property_type: form.property_type,
      operational_service: form.operational_service,
      contemplada: form.contemplada,
      bem_faturado: form.bem_faturado,
      parcelas_em_dia: form.parcelas_em_dia,
      docs_complete: form.docs_complete,
    };
  }

  async function calculate() {
    setError("");
    setBusy(true);
    try {
      const res = await api<{ result: EvalResult }>("/quitcon/desk/evaluate", {
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
      const created = await api<QuitConSolicitation>("/quitcon/desk/solicitations", {
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
      setNotice(`QuitCon gravado: ${created.contact_name} — ${created.status_label}`);
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

  async function uploadDoc(item: QuitConSolicitation, file: File) {
    setError("");
    setBusy(true);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("doc_type", docType);
      await apiForm(`/quitcon/desk/solicitations/${item.id}/documents`, body);
      setNotice(`Documento anexado em ${item.contact_name}`);
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
                <input placeholder="Saldo devedor bruto (R$)" value={form.outstanding_balance} onChange={(e) => patchForm("outstanding_balance", e.target.value)} />
                <input type="number" placeholder="Meses restantes" value={form.meses_restantes} onChange={(e) => patchForm("meses_restantes", e.target.value)} />
                <input placeholder="Grupo/cota (registry)" value={form.registry_number} onChange={(e) => patchForm("registry_number", e.target.value)} />
                <select value={form.registry_office} onChange={(e) => patchForm("registry_office", e.target.value)}>
                  {ADMINS.map((a) => <option key={a} value={a}>{a}</option>)}
                </select>
                <select value={form.property_type} onChange={(e) => patchForm("property_type", e.target.value)}>
                  <option value="CONSORCIO">Consórcio</option>
                  <option value="REAL_ESTATE">Imóvel</option>
                  <option value="RURAL">Rural</option>
                </select>
                <input placeholder="Endereço" value={form.address} onChange={(e) => patchForm("address", e.target.value)} style={{ gridColumn: "1 / -1" }} />
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 14, fontSize: 12, fontWeight: 700 }}>
                <label><input type="checkbox" checked={form.contemplada} onChange={(e) => patchForm("contemplada", e.target.checked)} /> Contemplada</label>
                <label><input type="checkbox" checked={form.bem_faturado} onChange={(e) => patchForm("bem_faturado", e.target.checked)} /> Bem faturado</label>
                <label><input type="checkbox" checked={form.parcelas_em_dia} onChange={(e) => patchForm("parcelas_em_dia", e.target.checked)} /> Parcelas em dia</label>
                <label><input type="checkbox" checked={form.operational_service} onChange={(e) => patchForm("operational_service", e.target.checked)} /> Serviço LETTER 2%</label>
                <label><input type="checkbox" checked={form.docs_complete} onChange={(e) => patchForm("docs_complete", e.target.checked)} /> Docs ok</label>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="admin-button" disabled={busy} onClick={() => void calculate()}>Calcular viabilidade</button>
                {evalResult?.viable && (
                  <button type="button" className="admin-button" disabled={busy} onClick={() => void store()}>Avançar (gravar QuitCon)</button>
                )}
              </div>
            </div>
            <div style={{ border: "1px solid var(--line)", borderRadius: 12, padding: 16, background: "#f7fbf9" }}>
              <b>Resultado doc253</b>
              {!evalResult && <p className="muted" style={{ marginTop: 10 }}>Preencha e clique em Calcular.</p>}
              {evalResult?.viable && (
                <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
                  <div><small>VP quitação</small><div><b>{brl.format(Number(evalResult.valor_presente_quitacao))}</b></div></div>
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
                  <p style={{ color: "#067647", fontWeight: 700 }}>{evalResult.message}</p>
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
