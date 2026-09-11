"use client";

import { CheckCircle2, Plus, RefreshCw, Truck } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type QuotaSupplier = {
  id: string;
  active: boolean;
  person_type: string;
  name: string;
  trade_name: string | null;
  document: string;
  email: string | null;
  phone: string | null;
  source_key: string;
  markup_percent: string;
  quem_paga_comissao: number;
  platform_fee_percent: string;
  bank_name: string | null;
  pix_key: string | null;
  notes: string | null;
  sync_mode: string;
  api_url: string | null;
  scrape_config_json?: string;
  last_sync_at: string | null;
  last_sync_status: string | null;
  has_portal_token?: boolean;
  balance_available?: string;
};

type SupplierWithdrawal = {
  id: string;
  supplier_id: string;
  amount: string;
  status: string;
  pix_key: string;
  notes: string | null;
  created_at: string | null;
  supplier_name: string | null;
  supplier_source_key: string | null;
};

type SyncResult = {
  status?: string;
  created?: number;
  updated?: number;
  deactivated?: number;
  protected?: number;
  failed?: number;
  suppliers?: number;
  error?: string;
  message?: string;
};

export function FornecedoresModule() {
  const [items, setItems] = useState<QuotaSupplier[]>([]);
  const [withdrawals, setWithdrawals] = useState<SupplierWithdrawal[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState<QuotaSupplier | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setItems(await api<QuotaSupplier[]>("/marketplace/suppliers"));
  }, []);

  const loadWithdrawals = useCallback(async () => {
    setWithdrawals(await api<SupplierWithdrawal[]>("/marketplace/supplier-withdrawals?status=PENDING&limit=50"));
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar fornecedores"));
    loadWithdrawals().catch(() => undefined);
  }, [load, loadWithdrawals]);

  async function processWithdrawal(id: string, action: "PAID" | "CANCELLED") {
    setError("");
    setBusy(true);
    try {
      await api(`/marketplace/supplier-withdrawals/${id}/process`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      setNotice(action === "PAID" ? "Saque marcado como pago." : "Saque cancelado — saldo devolvido.");
      await Promise.all([load(), loadWithdrawals()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao processar saque");
    } finally {
      setBusy(false);
    }
  }

  async function ensureDefaults() {
    setError("");
    setBusy(true);
    try {
      const rows = await api<QuotaSupplier[]>("/marketplace/suppliers/ensure-defaults", { method: "POST" });
      setItems(rows);
      setNotice("Fornecedores padrão (Fraga, Bittelo, Lance, Uni, Contemplado SP, Lume) garantidos.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao criar padrões");
    } finally {
      setBusy(false);
    }
  }

  async function syncAll() {
    setError("");
    setBusy(true);
    try {
      const result = await api<SyncResult>("/marketplace/inventory/sync", { method: "POST" });
      setNotice(
        `Sync geral: ${result.suppliers ?? 0} fornecedor(es) · +${result.created ?? 0} · ~${result.updated ?? 0} · −${result.deactivated ?? 0}` +
          (result.failed ? ` · falhas ${result.failed}` : ""),
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no sync de inventário");
    } finally {
      setBusy(false);
    }
  }

  async function syncOne(item: QuotaSupplier) {
    setError("");
    setBusy(true);
    try {
      const result = await api<SyncResult>(`/marketplace/suppliers/${item.id}/sync`, { method: "POST" });
      if (result.status === "ERROR") {
        setError(result.error || `Falha no sync de ${item.source_key}`);
      } else {
        setNotice(
          `${item.source_key}: ${result.status || "OK"} · +${result.created ?? 0} · ~${result.updated ?? 0} · −${result.deactivated ?? 0}` +
            (result.message ? ` — ${result.message}` : ""),
        );
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no sync");
    } finally {
      setBusy(false);
    }
  }

  async function issuePortalToken(item: QuotaSupplier) {
    setError("");
    setBusy(true);
    try {
      const result = await api<{ portal_token: string; portal_url: string }>(
        `/marketplace/suppliers/${item.id}/portal-token`,
        { method: "POST" },
      );
      const url = `${window.location.origin}${result.portal_url}`;
      setNotice(`Token portal ${item.source_key}: ${result.portal_token} · ${url}`);
      try {
        await navigator.clipboard.writeText(url);
      } catch {
        /* ignore */
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao gerar token do portal");
    } finally {
      setBusy(false);
    }
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const form = e.currentTarget;
    const fd = new FormData(form);
    const body = {
      name: String(fd.get("name") || ""),
      trade_name: String(fd.get("trade_name") || "") || null,
      source_key: String(fd.get("source_key") || ""),
      document: String(fd.get("document") || ""),
      person_type: String(fd.get("person_type") || "PJ"),
      email: String(fd.get("email") || "") || null,
      phone: String(fd.get("phone") || "") || null,
      markup_percent: String(fd.get("markup_percent") || "0"),
      quem_paga_comissao: Number(fd.get("quem_paga_comissao") || 0),
      platform_fee_percent: String(fd.get("platform_fee_percent") || "0"),
      bank_name: String(fd.get("bank_name") || "") || null,
      pix_key: String(fd.get("pix_key") || "") || null,
      notes: String(fd.get("notes") || "") || null,
      active: fd.get("active") === "1",
      sync_mode: String(fd.get("sync_mode") || "NONE"),
      api_url: String(fd.get("api_url") || "") || null,
      scrape_table_id: String(fd.get("scrape_table_id") || "") || null,
      scrape_category: String(fd.get("scrape_category") || "REAL_ESTATE") || null,
    };
    try {
      if (editing) {
        await api(`/marketplace/suppliers/${editing.id}`, { method: "PATCH", body: JSON.stringify(body) });
        setNotice(`Fornecedor ${body.name} atualizado.`);
        setEditing(null);
      } else {
        await api("/marketplace/suppliers", { method: "POST", body: JSON.stringify(body) });
        setNotice(`Fornecedor ${body.name} cadastrado.`);
      }
      form.reset();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(item: QuotaSupplier) {
    setError("");
    try {
      await api(`/marketplace/suppliers/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ active: !item.active }),
      });
      setNotice(`${item.name} ${item.active ? "inativado" : "ativado"}.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao atualizar status");
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">CADASTRO</span>
          <h1>Fornecedores de cotas</h1>
          <p>
            Empresas que alimentam o inventário e o robô Esteira 2. Markup na entrada (% do crédito) e sync JSON da
            API do fornecedor.
          </p>
        </div>
        <div className="operational-icon">
          <Truck />
        </div>
      </div>

      <section className="panel operational-panel">
        <div className="notice">
          <Truck />
          Use o mesmo <b>source_key</b> da cota no Inventário (ex.: FRAGA). Com <b>sync_mode=JSON</b> e{" "}
          <b>api_url</b>, o botão Sincronizar importa/atualiza cotas e inativa as que sumiram (sem tocar em
          RESERVED/SOLD). Markup continua no match — não é embutido no sync. Em produção, o cron Render{" "}
          <code>letter-marketplace-quota-sync</code> repete o sync a cada 30 min.
        </div>

        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1rem" }}>
          <button type="button" className="table-action" onClick={ensureDefaults} disabled={busy}>
            <RefreshCw /> Garantir fornecedores API padrão
          </button>
          <button type="button" className="table-action" onClick={syncAll} disabled={busy}>
            <RefreshCw /> Sincronizar todos (JSON)
          </button>
          {editing && (
            <button type="button" className="table-action" onClick={() => setEditing(null)}>
              Cancelar edição
            </button>
          )}
        </div>

        {notice && (
          <div className="notice">
            <CheckCircle2 />
            {notice}
          </div>
        )}
        {error && <div className="error">{error}</div>}

        <form className="marketplace-form" onSubmit={submit} key={editing?.id || "new"}>
          <div className="marketplace-form-row">
            <label className="marketplace-field">
              Nome / Razão social
              <input name="name" required minLength={2} defaultValue={editing?.name || ""} />
            </label>
            <label className="marketplace-field">
              Nome fantasia
              <input name="trade_name" defaultValue={editing?.trade_name || ""} />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Tipo
              <select name="person_type" defaultValue={editing?.person_type || "PJ"}>
                <option value="PJ">PJ</option>
                <option value="PF">PF</option>
              </select>
            </label>
            <label className="marketplace-field">
              CPF / CNPJ
              <input name="document" required defaultValue={editing?.document || ""} />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Source key
              <input name="source_key" required placeholder="FRAGA" defaultValue={editing?.source_key || ""} />
            </label>
            <label className="marketplace-field">
              E-mail
              <input name="email" type="email" defaultValue={editing?.email || ""} />
            </label>
            <label className="marketplace-field">
              Telefone
              <input name="phone" defaultValue={editing?.phone || ""} />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Markup %
              <input name="markup_percent" type="number" min={0} max={100} step="0.01" defaultValue={editing?.markup_percent || "0"} />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Quem paga comissão
              <select name="quem_paga_comissao" defaultValue={String(editing?.quem_paga_comissao ?? 0)}>
                <option value="0">Fornecedor</option>
                <option value="1">Cliente (embute na entrada)</option>
              </select>
            </label>
            <label className="marketplace-field marketplace-field-compact">
              % plataforma
              <input
                name="platform_fee_percent"
                type="number"
                min={0}
                max={100}
                step="0.01"
                defaultValue={editing?.platform_fee_percent || "0"}
                title="Usado só se cliente paga a comissão"
              />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Sync
              <select name="sync_mode" defaultValue={editing?.sync_mode || "NONE"}>
                <option value="NONE">Manual</option>
                <option value="JSON">API JSON</option>
                <option value="SCRAPE">Scrape HTML (TablePress)</option>
              </select>
            </label>
            <label className="marketplace-field marketplace-field-wide">
              API URL / página HTML
              <input name="api_url" placeholder="https://..." defaultValue={editing?.api_url || ""} />
            </label>
            <label className="marketplace-field marketplace-field-wide">
              Table ID (SCRAPE)
              <input
                name="scrape_table_id"
                placeholder="tablepress-tab-imoveis"
                defaultValue={
                  editing?.scrape_config_json
                    ? (() => {
                        try {
                          return JSON.parse(editing.scrape_config_json).table_id || "";
                        } catch {
                          return "";
                        }
                      })()
                    : ""
                }
              />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Categoria (SCRAPE)
              <select
                name="scrape_category"
                defaultValue={
                  editing?.scrape_config_json
                    ? (() => {
                        try {
                          return JSON.parse(editing.scrape_config_json).category || "REAL_ESTATE";
                        } catch {
                          return "REAL_ESTATE";
                        }
                      })()
                    : "REAL_ESTATE"
                }
              >
                <option value="REAL_ESTATE">Imóvel</option>
                <option value="VEHICLE">Veículo</option>
              </select>
            </label>
            <label className="marketplace-field">
              Banco
              <input name="bank_name" defaultValue={editing?.bank_name || ""} />
            </label>
            <label className="marketplace-field">
              Pix
              <input name="pix_key" defaultValue={editing?.pix_key || ""} />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Ativo
              <select name="active" defaultValue={editing ? (editing.active ? "1" : "0") : "1"}>
                <option value="1">Sim</option>
                <option value="0">Não</option>
              </select>
            </label>
            <label className="marketplace-field marketplace-field-wide">
              Notas
              <input name="notes" defaultValue={editing?.notes || ""} />
            </label>
            <button type="submit" className="marketplace-submit" disabled={busy}>
              <Plus />
              {editing ? "Salvar alterações" : "Cadastrar fornecedor"}
            </button>
          </div>
        </form>

        <div className="table-wrap" style={{ marginTop: "1.25rem" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Nome</th>
                <th>Source</th>
                <th>Sync</th>
                <th>Markup</th>
                <th>Saldo</th>
                <th>Último sync</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.map((x) => (
                <tr key={x.id}>
                  <td>
                    <span className={`pill pill-${x.active ? "cleared" : "blocked"}`}>{x.active ? "Ativo" : "Inativo"}</span>
                  </td>
                  <td>
                    <b>{x.name}</b>
                    <small>{x.email || x.phone || "—"}</small>
                  </td>
                  <td>
                    <code>{x.source_key}</code>
                  </td>
                  <td>
                    <code>{x.sync_mode || "NONE"}</code>
                    {x.api_url ? <small title={x.api_url}>URL ok</small> : <small>—</small>}
                  </td>
                  <td>{x.markup_percent}%</td>
                  <td>R$ {x.balance_available ?? "0.00"}</td>
                  <td>
                    {x.last_sync_status || "—"}
                    <small>{x.last_sync_at ? new Date(x.last_sync_at).toLocaleString("pt-BR") : ""}</small>
                  </td>
                  <td className="actions-cell">
                    <button type="button" className="table-action" onClick={() => setEditing(x)}>
                      Editar
                    </button>
                    <button
                      type="button"
                      className="table-action"
                      onClick={() => syncOne(x)}
                      disabled={busy || (x.sync_mode || "NONE") === "NONE"}
                    >
                      Sincronizar
                    </button>
                    <button type="button" className="table-action" onClick={() => issuePortalToken(x)} disabled={busy}>
                      {x.has_portal_token ? "Novo token portal" : "Token portal"}
                    </button>
                    <button type="button" className="table-action" onClick={() => toggleActive(x)}>
                      {x.active ? "Inativar" : "Ativar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel operational-panel" style={{ marginTop: "1.25rem" }}>
        <div className="page-heading" style={{ marginBottom: "0.75rem" }}>
          <div>
            <span className="eyebrow dark">PEDIDOS</span>
            <h2 style={{ margin: 0, fontSize: "1.15rem" }}>Saques de fornecedores</h2>
            <p style={{ margin: "0.35rem 0 0" }}>Pendentes do portal — marcar pago ou cancelar (devolve saldo).</p>
          </div>
          <button type="button" className="table-action" onClick={() => loadWithdrawals()} disabled={busy}>
            <RefreshCw /> Atualizar
          </button>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Fornecedor</th>
                <th>Valor</th>
                <th>Pix</th>
                <th>Quando</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {withdrawals.map((w) => (
                <tr key={w.id}>
                  <td>
                    <b>{w.supplier_name || "—"}</b>
                    <small>
                      <code>{w.supplier_source_key || w.supplier_id.slice(0, 8)}</code>
                    </small>
                  </td>
                  <td>R$ {w.amount}</td>
                  <td>
                    <code>{w.pix_key || "—"}</code>
                    {w.notes ? <small>{w.notes}</small> : null}
                  </td>
                  <td>{w.created_at ? new Date(w.created_at).toLocaleString("pt-BR") : "—"}</td>
                  <td className="actions-cell">
                    <button type="button" className="table-action" disabled={busy} onClick={() => processWithdrawal(w.id, "PAID")}>
                      Pago
                    </button>
                    <button
                      type="button"
                      className="table-action"
                      disabled={busy}
                      onClick={() => processWithdrawal(w.id, "CANCELLED")}
                    >
                      Cancelar
                    </button>
                  </td>
                </tr>
              ))}
              {!withdrawals.length && (
                <tr>
                  <td colSpan={5}>Nenhum saque pendente.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
