"use client";

import { CheckCircle2, ClipboardList, RefreshCw } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, API_URL } from "@/lib/api";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type CadastroRow = {
  lead_id: string;
  created_at: string | null;
  name: string;
  document: string | null;
  phone: string;
  email: string | null;
  source: string;
  lead_status: string;
  pipeline: string;
  situation: string;
  situation_label: string;
  credit_value: string | null;
  entrada_value: string | null;
  partner_name: string | null;
  proposal_id: string | null;
  proposal_status: string | null;
  quota_codes: string[];
  supplier_sources: string[];
  supplier_transfer_confirmed?: boolean;
  commission_release_status?: string | null;
  paid_at?: string | null;
  lifecycle_editable?: boolean;
};

type CadastroDetail = CadastroRow & {
  address: Record<string, string>;
  purchase_readonly: Record<string, unknown>;
  snapshot: Record<string, unknown>;
  can_conclude?: boolean;
  commission_release?: {
    reference?: string;
    supplier_total?: string;
    platform_total?: string;
    affiliate_total?: string;
    affiliate_skipped?: string | null;
    lines?: Array<{ type?: string; amount?: string; supplier_name?: string | null; supplier_source?: string | null }>;
  } | null;
  boleto?: {
    provider?: string;
    codigo_solicitacao?: string;
    amount?: string;
    pdf_url?: string | null;
    download_token?: string | null;
    due_date?: string | null;
  } | null;
};

const SALE_SITUATIONS = [
  { value: "AGUARDANDO_PAGAMENTO", label: "Aguardando pagamento" },
  { value: "PAGO", label: "Pagou" },
  { value: "CONCLUIDO", label: "Concluído" },
  { value: "CANCELADO", label: "Cancelado" },
  { value: "CANCELADO_FALTA_PAGAMENTO", label: "Cancelado (falta de pagamento)" },
] as const;

const TABS = [
  { key: "ALL", label: "Clientes" },
  { key: "NOVOS", label: "Novos" },
  { key: "NEGOCIACAO", label: "Em negociação" },
  { key: "CONCLUIDO", label: "Concluído" },
  { key: "INCOMPLETO", label: "Incompleto" },
  { key: "COMPRAS", label: "Compras" },
] as const;

export function CadastroMarketplaceModule() {
  const [tab, setTab] = useState<string>("ALL");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<CadastroRow[]>([]);
  const [selected, setSelected] = useState<CadastroDetail | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ pipeline: tab });
    if (q.trim()) params.set("q", q.trim());
    setRows(await api<CadastroRow[]>(`/marketplace/cadastros?${params}`));
  }, [tab, q]);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar cadastros"));
  }, [load]);

  async function openDetail(leadId: string) {
    setError("");
    try {
      setSelected(await api<CadastroDetail>(`/marketplace/cadastros/${leadId}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao abrir cadastro");
    }
  }

  async function issueBoleto() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ boleto: CadastroDetail["boleto"]; created: boolean }>(
        `/marketplace/cadastros/${selected.lead_id}/boleto`,
        { method: "POST" },
      );
      setSelected({ ...selected, boleto: result.boleto });
      setNotice(result.created ? "Boleto emitido." : "Boleto já existia — reutilizado.");
      const token = result.boleto?.download_token;
      if (token) {
        window.open(`${API_URL}/marketplace/cadastros/${selected.lead_id}/boleto/${token}`, "_blank");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao emitir boleto");
    } finally {
      setBusy(false);
    }
  }

  async function saveDetail(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError("");
    const fd = new FormData(e.currentTarget);
    try {
      const updated = await api<CadastroDetail>(`/marketplace/cadastros/${selected.lead_id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: fd.get("name"),
          phone: fd.get("phone"),
          document: fd.get("document") || null,
          email: fd.get("email") || null,
          lead_status: fd.get("lead_status"),
          zipcode: fd.get("zipcode") || null,
          street: fd.get("street") || null,
          number: fd.get("number") || null,
          neighborhood: fd.get("neighborhood") || null,
          city: fd.get("city") || null,
          uf: fd.get("uf") || null,
          situation: selected.lifecycle_editable ? String(fd.get("situation") || selected.situation) : undefined,
          supplier_transfer_confirmed: selected.lifecycle_editable ? fd.get("supplier_transfer_confirmed") === "1" : undefined,
          force_admin_conclude: selected.lifecycle_editable ? fd.get("force_admin_conclude") === "1" : false,
        }),
      });
      setSelected(updated);
      setNotice("Cadastro atualizado.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar");
    } finally {
      setBusy(false);
    }
  }

  const counts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const row of rows) map[row.pipeline] = (map[row.pipeline] || 0) + 1;
    return map;
  }, [rows]);

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">CADASTRO</span>
          <h1>Cadastros — Marketplace</h1>
          <p>
            Onde mora a venda: chat, Venda Direta Manual e Robô. Filtre por etapa (novos, negociação, concluído,
            incompleto) e edite dados do cliente sem alterar a compra.
          </p>
        </div>
        <div className="operational-icon">
          <ClipboardList />
        </div>
      </div>

      <section className="panel operational-panel">
        <div className="notice">
          <ClipboardList />
          Novas vendas: <Link href="/modules/venda-direta-manual">Manual</Link> ·{" "}
          <Link href="/modules/venda-direta-robo">Robô</Link> · Finalize contrato em{" "}
          <Link href="/modules/proposals">Propostas</Link>.
        </div>

        <div className="marketplace-tabs" style={{ marginBottom: "1rem" }}>
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={`marketplace-tab${tab === t.key ? " active" : ""}`}
              onClick={() => {
                setTab(t.key);
                setSelected(null);
              }}
            >
              {t.label}
              {t.key !== "ALL" && counts[t.key] ? ` (${counts[t.key]})` : ""}
            </button>
          ))}
        </div>

        <form
          className="quick-form"
          onSubmit={(e) => {
            e.preventDefault();
            load().catch((err) => setError(err instanceof Error ? err.message : "Falha"));
          }}
          style={{ marginBottom: "1rem" }}
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar nome, documento, telefone, e-mail"
          />
          <button type="submit">
            <RefreshCw /> Buscar
          </button>
        </form>

        {notice && (
          <div className="notice">
            <CheckCircle2 />
            {notice}
          </div>
        )}
        {error && <div className="error">{error}</div>}

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Data</th>
                <th>Cliente</th>
                <th>Contato</th>
                <th>Crédito</th>
                <th>Entrada</th>
                <th>Parceiro</th>
                <th>Situação</th>
                <th>Origem</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.lead_id}>
                  <td>
                    <small>{row.created_at ? new Date(row.created_at).toLocaleString("pt-BR") : "—"}</small>
                  </td>
                  <td>
                    <b>{row.name}</b>
                    <small>{row.document || "—"}</small>
                  </td>
                  <td>
                    {row.phone}
                    <small>{row.email || "—"}</small>
                  </td>
                  <td>{row.credit_value ? brl.format(Number(row.credit_value)) : "—"}</td>
                  <td>{row.entrada_value ? brl.format(Number(row.entrada_value)) : "—"}</td>
                  <td>{row.partner_name || "—"}</td>
                  <td>
                    <span className={`pill pill-${row.situation.toLowerCase()}`}>{row.situation_label}</span>
                  </td>
                  <td>
                    <small>{row.source}</small>
                  </td>
                  <td>
                    <button type="button" className="table-action" onClick={() => openDetail(row.lead_id)}>
                      Abrir
                    </button>
                  </td>
                </tr>
              ))}
              {!rows.length && (
                <tr>
                  <td colSpan={9}>Nenhum cadastro nesta etapa.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {selected && (
          <form className="marketplace-form" onSubmit={saveDetail} style={{ marginTop: "1.5rem" }} key={selected.lead_id}>
            <h3>
              {selected.name} · {selected.situation_label}
            </h3>
            <div className="notice">
              Compra (somente leitura): crédito{" "}
              {selected.credit_value ? brl.format(Number(selected.credit_value)) : "—"} · entrada{" "}
              {selected.entrada_value ? brl.format(Number(selected.entrada_value)) : "—"} · cotas{" "}
              {(selected.quota_codes || []).join(", ") || "—"} · fornecedores{" "}
              {(selected.supplier_sources || []).join(", ") || "—"}
              {selected.commission_release_status ? ` · comissão ${selected.commission_release_status}` : ""}
              {selected.proposal_id ? (
                <>
                  {" "}
                  · <Link href="/modules/proposals">Proposta {selected.proposal_id.slice(0, 8)}…</Link>
                </>
              ) : null}
            </div>
            {selected.commission_release ? (
              <div className="notice">
                Liberação: fornecedor{" "}
                {selected.commission_release.supplier_total
                  ? brl.format(Number(selected.commission_release.supplier_total))
                  : "—"}{" "}
                · plataforma{" "}
                {selected.commission_release.platform_total
                  ? brl.format(Number(selected.commission_release.platform_total))
                  : "—"}{" "}
                · rede{" "}
                {selected.commission_release.affiliate_total
                  ? brl.format(Number(selected.commission_release.affiliate_total))
                  : "—"}
                {selected.commission_release.affiliate_skipped
                  ? ` (afiliado: ${selected.commission_release.affiliate_skipped})`
                  : ""}
                {selected.commission_release.reference ? ` · ${selected.commission_release.reference}` : ""}
              </div>
            ) : null}
            {selected.lifecycle_editable && selected.situation === "AGUARDANDO_PAGAMENTO" ? (
              <div className="notice">
                Boleto entrada:{" "}
                {selected.boleto?.codigo_solicitacao
                  ? `${selected.boleto.provider || "—"} · ${selected.boleto.codigo_solicitacao}`
                  : "ainda não emitido"}
                {selected.boleto?.amount ? ` · ${brl.format(Number(selected.boleto.amount))}` : ""}
                <button type="button" className="table-action" style={{ marginLeft: "0.75rem" }} onClick={issueBoleto} disabled={busy}>
                  {selected.boleto?.download_token ? "Ver boleto" : "Emitir boleto"}
                </button>
              </div>
            ) : null}
            <div className="marketplace-form-row">
              <label className="marketplace-field">
                Nome
                <input name="name" defaultValue={selected.name} required />
              </label>
              <label className="marketplace-field">
                Telefone
                <input name="phone" defaultValue={selected.phone} required />
              </label>
              <label className="marketplace-field">
                Documento
                <input name="document" defaultValue={selected.document || ""} />
              </label>
              <label className="marketplace-field">
                E-mail
                <input name="email" type="email" defaultValue={selected.email || ""} />
              </label>
              {selected.lifecycle_editable ? (
                <>
                  <label className="marketplace-field marketplace-field-compact">
                    Situação da venda
                    <select name="situation" defaultValue={selected.situation}>
                      {SALE_SITUATIONS.map((s) => (
                        <option key={s.value} value={s.value}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="marketplace-field marketplace-field-compact">
                    Fornecedor confirmou transferência
                    <select name="supplier_transfer_confirmed" defaultValue={selected.supplier_transfer_confirmed ? "1" : "0"}>
                      <option value="0">Não</option>
                      <option value="1">Sim</option>
                    </select>
                  </label>
                  <label className="marketplace-field marketplace-field-wide">
                    Forçar conclusão sem confirmação do fornecedor
                    <select name="force_admin_conclude" defaultValue="0">
                      <option value="0">Não</option>
                      <option value="1">Sim (admin)</option>
                    </select>
                  </label>
                </>
              ) : null}
              <label className="marketplace-field marketplace-field-compact">
                Status lead
                <select name="lead_status" defaultValue={selected.lead_status}>
                  {["NEW", "CONTACTED", "QUALIFIED", "PROPOSAL", "CONVERTED", "CANCELLED"].map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label className="marketplace-field marketplace-field-compact">
                CEP
                <input name="zipcode" defaultValue={selected.address?.zipcode || ""} />
              </label>
              <label className="marketplace-field">
                Rua
                <input name="street" defaultValue={selected.address?.street || ""} />
              </label>
              <label className="marketplace-field marketplace-field-compact">
                Número
                <input name="number" defaultValue={selected.address?.number || ""} />
              </label>
              <label className="marketplace-field">
                Bairro
                <input name="neighborhood" defaultValue={selected.address?.neighborhood || ""} />
              </label>
              <label className="marketplace-field">
                Cidade
                <input name="city" defaultValue={selected.address?.city || ""} />
              </label>
              <label className="marketplace-field marketplace-field-compact">
                UF
                <input name="uf" defaultValue={selected.address?.uf || ""} maxLength={2} />
              </label>
            </div>
            <button type="submit" className="marketplace-submit" disabled={busy}>
              <RefreshCw />
              {busy ? "Salvando…" : "Salvar cadastro"}
            </button>
            <button type="button" className="table-action" style={{ marginLeft: "0.75rem" }} onClick={() => setSelected(null)}>
              Fechar
            </button>
          </form>
        )}
      </section>
    </>
  );
}
