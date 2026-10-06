"use client";

import { CheckCircle2, Plus, RefreshCw, Truck } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { PartnerWithdrawalsAdminPanel } from "@/components/partner-withdrawals-admin-panel";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type InventoryQuotaFilter = "active" | "protected" | "inactive" | "all";

type SupplierInventoryAudit = {
  supplier_id: string;
  source_key: string;
  supplier_name: string;
  filter: string;
  summary: {
    active_count: number;
    active_credit_total: string;
    protected_count: number;
    inactive_count: number;
    total_count: number;
  };
  quotas: Array<{
    id: string;
    group_code: string;
    quota_code: string;
    category: string;
    credit_value: string;
    premium_value: string;
    entrada_final?: string | null;
    status: string;
    nina_scan_status?: string | null;
    installment_due_date?: string | null;
  }>;
};

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
  last_sync_detail_json?: string;
  has_portal_token?: boolean;
  balance_available?: string;
};

type SupplierWithdrawal = {
  id: string;
  supplier_id: string;
  amount: string;
  status: string;
  status_label?: string | null;
  pix_key: string;
  notes: string | null;
  inter_codigo_solicitacao?: string | null;
  inter_end_to_end_id?: string | null;
  payment_error?: string | null;
  created_at: string | null;
  supplier_name: string | null;
  supplier_source_key: string | null;
};

const SUPPLIER_WITHDRAWAL_RETRY = new Set(["PENDING", "PROCESSING", "FAILED", "AWAITING_BALANCE"]);
const SUPPLIER_WITHDRAWAL_OPEN = new Set(["PENDING", "PROCESSING", "AWAITING_BALANCE", "FAILED"]);

function parseScrapeConfig(raw?: string | null) {
  try {
    return JSON.parse(raw || "{}") as { layout?: string; table_id?: string; category?: string; ca?: string };
  } catch {
    return {};
  }
}

function formatSyncDetail(raw?: string | null) {
  try {
    const detail = JSON.parse(raw || "{}") as {
      created?: number;
      updated?: number;
      deactivated?: number;
      skipped?: number;
      protected?: number;
      error?: string;
      fetched?: number;
    };
    if (detail.error) {
      return detail.error;
    }
    const parts: string[] = [];
    if (detail.created) parts.push(`+${detail.created}`);
    if (detail.updated) parts.push(`~${detail.updated}`);
    if (detail.deactivated) parts.push(`−${detail.deactivated}`);
    if (detail.protected) parts.push(`⊘${detail.protected}`);
    return parts.join(" ");
  } catch {
    return "";
  }
}

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
  const [formKey, setFormKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [inventorySupplierId, setInventorySupplierId] = useState("");
  const [inventoryFilter, setInventoryFilter] = useState<InventoryQuotaFilter>("active");
  const [inventoryAudit, setInventoryAudit] = useState<SupplierInventoryAudit | null>(null);

  const load = useCallback(async () => {
    setItems(await api<QuotaSupplier[]>("/marketplace/suppliers"));
  }, []);

  const loadInventoryAudit = useCallback(async () => {
    if (!inventorySupplierId) {
      setInventoryAudit(null);
      return;
    }
    setError("");
    try {
      const params = new URLSearchParams({ filter: inventoryFilter });
      setInventoryAudit(
        await api<SupplierInventoryAudit>(
          `/marketplace/suppliers/${inventorySupplierId}/inventory-quotas?${params}`,
        ),
      );
    } catch (e) {
      setInventoryAudit(null);
      setError(e instanceof Error ? e.message : "Falha ao carregar cotas do fornecedor");
    }
  }, [inventorySupplierId, inventoryFilter]);

  useEffect(() => {
    void loadInventoryAudit();
  }, [loadInventoryAudit]);

  const inventorySupplier = useMemo(
    () => items.find((x) => x.id === inventorySupplierId) ?? null,
    [items, inventorySupplierId],
  );

  const loadWithdrawals = useCallback(async () => {
    const data = await api<SupplierWithdrawal[]>("/marketplace/supplier-withdrawals?limit=80");
    setWithdrawals(data.filter((w) => SUPPLIER_WITHDRAWAL_OPEN.has(w.status)));
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
      setNotice(
        action === "PAID"
          ? "Saque marcado como pago (manual — sem Inter)."
          : "Saque cancelado — saldo devolvido.",
      );
      await Promise.all([load(), loadWithdrawals()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao processar saque");
    } finally {
      setBusy(false);
    }
  }

  async function retrySupplierInter(id: string) {
    setError("");
    setBusy(true);
    try {
      await api(`/marketplace/supplier-withdrawals/${id}/retry-inter-payout`, { method: "POST", body: "{}" });
      setNotice("PIX reenviado via Banco Inter.");
      await loadWithdrawals();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao reenviar PIX");
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
      setNotice(
        "Fornecedores padrão garantidos. Uni/Lume/Contemplado SP (scrape) e Fraga e Bitello / Lance (API JSON do legado) já vêm com URL.",
      );
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
    const apiUrl = String(fd.get("api_url") || "").trim();
    const sourceKey = String(fd.get("source_key") || "");
    let syncMode = String(fd.get("sync_mode") || "NONE");
    if (apiUrl && syncMode === "NONE") {
      const lower = apiUrl.toLowerCase();
      syncMode = lower.includes(".json") || lower.includes("/api/json") ? "JSON" : "SCRAPE";
    }
    const vehicleKey = /veicul|vehicle|auto|moto|carro/i.test(sourceKey) || /veicul/i.test(apiUrl);
    const body = {
      name: String(fd.get("name") || ""),
      trade_name: String(fd.get("trade_name") || "") || null,
      source_key: sourceKey,
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
      sync_mode: syncMode,
      api_url: apiUrl || null,
      scrape_table_id: String(fd.get("scrape_table_id") || "") || null,
      scrape_category: vehicleKey
        ? "VEHICLE"
        : String(fd.get("scrape_category") || "REAL_ESTATE") || null,
      scrape_layout: String(fd.get("scrape_layout") || "tablepress") || null,
      scrape_tls_ca: String(fd.get("scrape_tls_ca") || "") || null,
    };
    try {
      let saved: QuotaSupplier;
      if (editing) {
        saved = await api<QuotaSupplier>(`/marketplace/suppliers/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
        setNotice(`Fornecedor ${body.name} atualizado.`);
        setEditing(null);
      } else {
        saved = await api<QuotaSupplier>("/marketplace/suppliers", { method: "POST", body: JSON.stringify(body) });
        setNotice(`Fornecedor ${body.name} cadastrado.`);
        setFormKey((k) => k + 1);
      }
      form.reset();
      await load();
      const mode = saved.sync_mode || "NONE";
      if (mode !== "NONE" && (saved.api_url || "").trim() && !saved.last_sync_at) {
        await syncOne(saved);
      }
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
            Cadastre fornecedores, aponte a URL da API JSON ou da página HTML (scrape) e o inventário atualiza no cron
            (~30 min) ou pelo botão Sincronizar.
          </p>
        </div>
        <div className="operational-icon">
          <Truck />
        </div>
      </div>

      <section className="panel operational-panel">
        <div className="notice">
          <Truck />
          <div>
            <b>Sincronização automática</b> (cron Render ~30 min) só roda em fornecedores com{" "}
            <b>Sync = API JSON</b> ou <b>Scrape HTML</b> e <b>URL preenchida</b>. Fraga e Bitello (uma empresa) e Lance
            já recebem URL do legado em «Garantir padrões». Quem está manual não aparece em «Último sync» — use «Garantir
            padrão» após configurar as URLs no servidor.
            <br />
            <small style={{ display: "block", marginTop: "0.35rem" }}>
              Use o mesmo <b>source_key</b> no Inventário. Markup não é alterado pelo sync.
            </small>
          </div>
        </div>

        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1rem" }}>
          <button
            type="button"
            className="marketplace-submit"
            disabled={busy}
            onClick={() => {
              setEditing(null);
              setFormKey((k) => k + 1);
              document.getElementById("fornecedor-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
            }}
          >
            <Plus /> Adicionar fornecedor
          </button>
          <button type="button" className="table-action" onClick={ensureDefaults} disabled={busy}>
            <RefreshCw /> Garantir fornecedores padrão
          </button>
          <button type="button" className="table-action" onClick={syncAll} disabled={busy}>
            <RefreshCw /> Sincronizar todos (JSON/SCRAPE)
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

        <h2 id="fornecedor-form" className="panel-inline-title" style={{ margin: "0 18px 0", fontSize: "1rem" }}>
          {editing ? `Editar: ${editing.name}` : "Cadastrar fornecedor — aponte o site ou API"}
        </h2>
        <p style={{ margin: "0.35rem 18px 0", fontSize: "10px", color: "#6b7280", lineHeight: 1.45 }}>
          Preencha os dados abaixo. <b>Source key</b> é obrigatório — invente um código único (não use FRAGA/LANCE se não for
          esses fornecedores; eles já vêm em «Garantir padrões»). Em <b>Sync</b>: <b>API JSON</b> se o fornecedor tem link
          de arquivo/API em JSON; <b>Scrape HTML</b> se as cotas estão numa página com tabela. <b>Manual</b> = sem sync
          automático (cotas pelo Inventário ou portal). Depois salve e use <b>Sincronizar</b> ou aguarde o cron.
        </p>

        <form className="marketplace-form" onSubmit={submit} key={editing?.id || `new-${formKey}`}>
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
              <input
                name="source_key"
                required
                minLength={2}
                autoComplete="off"
                placeholder="Ex.: ACME_COTAS"
                defaultValue={editing?.source_key || ""}
                title="Código único do fornecedor (maiúsculas, sem espaço). Usado no Inventário."
              />
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
                <option value="SCRAPE">Scrape HTML</option>
              </select>
            </label>
            <label className="marketplace-field marketplace-field-wide">
              URL do site ou API (obrigatório para sync automático)
              <input
                name="api_url"
                placeholder="https://fornecedor.com.br/cotas.json ou https://site.com.br/cartas-contempladas/"
                defaultValue={editing?.api_url || ""}
              />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Layout (SCRAPE)
              <select name="scrape_layout" defaultValue={parseScrapeConfig(editing?.scrape_config_json).layout || "tablepress"}>
                <option value="tablepress">TablePress (Uni/Lume)</option>
                <option value="contempladosp">Contemplado SP</option>
                <option value="cartascontempladas">Cartas Contempladas</option>
              </select>
            </label>
            <label className="marketplace-field marketplace-field-wide">
              Table ID (SCRAPE)
              <input
                name="scrape_table_id"
                placeholder="tablepress-tab-imoveis · tbCotasGerais · listaCotas"
                defaultValue={parseScrapeConfig(editing?.scrape_config_json).table_id || ""}
              />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Categoria (SCRAPE)
              <select name="scrape_category" defaultValue={parseScrapeConfig(editing?.scrape_config_json).category || "REAL_ESTATE"}>
                <option value="REAL_ESTATE">Imóvel</option>
                <option value="VEHICLE">Veículo</option>
              </select>
            </label>
            <label className="marketplace-field marketplace-field-compact">
              CA TLS (opcional)
              <select name="scrape_tls_ca" defaultValue={parseScrapeConfig(editing?.scrape_config_json).ca || ""}>
                <option value="">Padrão do sistema</option>
                <option value="lets-encrypt-root-yr.pem">Contemplado SP (Lets Encrypt YR)</option>
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
              {items.map((x) => {
                const syncDetail = formatSyncDetail(x.last_sync_detail_json);
                return (
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
                    {(x.sync_mode || "NONE") === "NONE" && !(x.api_url || "").trim() ? (
                      <small>Manual — configure URL + Sync</small>
                    ) : (
                      <>
                        {x.last_sync_status || "—"}
                        {syncDetail ? <small title={x.last_sync_detail_json}>{syncDetail}</small> : null}
                        <small>{x.last_sync_at ? new Date(x.last_sync_at).toLocaleString("pt-BR") : "Ainda não sincronizado"}</small>
                      </>
                    )}
                  </td>
                  <td className="actions-cell">
                    <button
                      type="button"
                      className="table-action"
                      onClick={() => {
                        setInventorySupplierId(x.id);
                        setInventoryFilter("active");
                        window.setTimeout(() => {
                          document.getElementById("fornecedor-inventory-audit")?.scrollIntoView({ behavior: "smooth", block: "start" });
                        }, 80);
                      }}
                    >
                      Ver cotas
                    </button>
                    <button type="button" className="table-action" onClick={() => setEditing(x)}>
                      Editar
                    </button>
                    <button
                      type="button"
                      className="table-action"
                      onClick={() => syncOne(x)}
                      disabled={
                        busy ||
                        ((x.sync_mode || "NONE") === "NONE" && !(x.api_url || "").trim())
                      }
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
              );
              })}
            </tbody>
          </table>
        </div>

        <section id="fornecedor-inventory-audit" className="panel" style={{ margin: "1.25rem 18px 18px", padding: "1rem" }}>
          <div className="page-heading" style={{ marginBottom: "0.75rem" }}>
            <div>
              <span className="eyebrow dark">CONFERÊNCIA</span>
              <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Cotas do fornecedor no inventário</h2>
              <p style={{ margin: "0.35rem 0 0", fontSize: 10, color: "#6b7280", lineHeight: 1.45 }}>
                O sync automático mantém apenas cotas <b>ativas</b> (disponíveis ou em revisão).{" "}
                <b>Reservadas</b> e <b>vendidas</b> ficam protegidas — o sistema não sobrescreve nem reimporta.
              </p>
            </div>
            <button
              type="button"
              className="table-action"
              disabled={!inventorySupplierId || busy}
              onClick={() => void loadInventoryAudit()}
            >
              <RefreshCw /> Atualizar lista
            </button>
          </div>
          <div className="marketplace-form-row" style={{ marginBottom: "0.75rem" }}>
            <label className="marketplace-field marketplace-field-wide">
              Fornecedor
              <select
                value={inventorySupplierId}
                onChange={(e) => setInventorySupplierId(e.target.value)}
              >
                <option value="">Selecione o fornecedor para conferir</option>
                {items.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.source_key})
                  </option>
                ))}
              </select>
            </label>
          </div>
          {inventoryAudit && (
            <>
              <div className="network-metrics" style={{ marginBottom: "0.75rem" }}>
                <article>
                  <small>Ativas (sync / venda)</small>
                  <strong>{inventoryAudit.summary.active_count}</strong>
                </article>
                <article>
                  <small>Crédito ativo</small>
                  <strong>{brl.format(Number(inventoryAudit.summary.active_credit_total))}</strong>
                </article>
                <article>
                  <small>Reservadas ou vendidas</small>
                  <strong>{inventoryAudit.summary.protected_count}</strong>
                </article>
                <article>
                  <small>Inativas (sumiram do site)</small>
                  <strong>{inventoryAudit.summary.inactive_count}</strong>
                </article>
              </div>
              <div className="marketplace-tabs" style={{ marginBottom: "0.75rem" }}>
                {(
                  [
                    { key: "active" as const, label: "Ativas" },
                    { key: "protected" as const, label: "Reservadas / vendidas" },
                    { key: "inactive" as const, label: "Inativas" },
                    { key: "all" as const, label: "Todas" },
                  ] as const
                ).map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    className={`marketplace-tab${inventoryFilter === tab.key ? " active" : ""}`}
                    onClick={() => setInventoryFilter(tab.key)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Grupo / cota</th>
                      <th>Categoria</th>
                      <th>Crédito</th>
                      <th>Entrada</th>
                      <th>Status</th>
                      <th>Nina</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventoryAudit.quotas.map((q) => (
                      <tr key={q.id}>
                        <td>
                          <b>{q.group_code}</b>
                          <small>{q.quota_code}</small>
                        </td>
                        <td>{q.category === "REAL_ESTATE" ? "Imóvel" : "Veículo"}</td>
                        <td>{brl.format(Number(q.credit_value))}</td>
                        <td>{brl.format(Number(q.entrada_final ?? q.premium_value ?? 0))}</td>
                        <td>
                          <span className={`pill pill-${q.status.toLowerCase()}`}>{q.status}</span>
                        </td>
                        <td>{q.nina_scan_status || "—"}</td>
                      </tr>
                    ))}
                    {!inventoryAudit.quotas.length && (
                      <tr>
                        <td colSpan={6}>
                          Nenhuma cota neste filtro
                          {inventorySupplier ? ` para ${inventorySupplier.name}.` : "."}
                          {inventoryFilter === "active" ? " Rode «Sincronizar» no fornecedor se acabou de apontar a URL." : ""}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      </section>

      <section className="panel operational-panel" style={{ marginTop: "1.25rem" }}>
        <div className="page-heading" style={{ marginBottom: "0.75rem" }}>
          <div>
            <span className="eyebrow dark">PEDIDOS</span>
            <h2 style={{ margin: 0, fontSize: "1.15rem" }}>Saques de fornecedores</h2>
            <p style={{ margin: "0.35rem 0 0" }}>
              Inter PIX automático no portal ou reenvio manual. &quot;Pago&quot; só se liquidou fora do Inter.
            </p>
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
                <th>Status</th>
                <th>Inter</th>
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
                  <td>{brl.format(Number(w.amount))}</td>
                  <td>
                    <code>{w.pix_key || "—"}</code>
                    {w.notes ? <small>{w.notes}</small> : null}
                  </td>
                  <td>
                    <span
                      className={`pill pill-${w.status === "PENDING" || w.status === "PROCESSING" ? "pending" : w.status === "PAID" ? "approved" : "rejected"}`}
                    >
                      {w.status_label || w.status}
                    </span>
                    {w.payment_error ? <small className="muted">{w.payment_error}</small> : null}
                  </td>
                  <td>
                    <small>
                      {w.inter_codigo_solicitacao ? `cod. ${w.inter_codigo_solicitacao.slice(0, 8)}…` : "—"}
                      {w.inter_end_to_end_id ? <br /> : null}
                      {w.inter_end_to_end_id ? `e2e ${w.inter_end_to_end_id.slice(0, 12)}…` : null}
                    </small>
                  </td>
                  <td>{w.created_at ? new Date(w.created_at).toLocaleString("pt-BR") : "—"}</td>
                  <td className="actions-cell">
                    {SUPPLIER_WITHDRAWAL_RETRY.has(w.status) && (
                      <button
                        type="button"
                        className="table-action"
                        disabled={busy}
                        onClick={() => void retrySupplierInter(w.id)}
                      >
                        Reenviar PIX
                      </button>
                    )}
                    {w.status === "PENDING" ? (
                      <>
                        <button
                          type="button"
                          className="table-action"
                          disabled={busy}
                          onClick={() => void processWithdrawal(w.id, "PAID")}
                        >
                          Pago manual
                        </button>
                        <button
                          type="button"
                          className="table-action"
                          disabled={busy}
                          onClick={() => void processWithdrawal(w.id, "CANCELLED")}
                        >
                          Cancelar
                        </button>
                      </>
                    ) : w.status === "FAILED" || w.status === "AWAITING_BALANCE" ? (
                      <button
                        type="button"
                        className="table-action"
                        disabled={busy}
                        onClick={() => void processWithdrawal(w.id, "CANCELLED")}
                      >
                        Cancelar
                      </button>
                    ) : (
                      <small className="muted">—</small>
                    )}
                  </td>
                </tr>
              ))}
              {!withdrawals.length && (
                <tr>
                  <td colSpan={7}>Nenhum saque em aberto.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <PartnerWithdrawalsAdminPanel
        onNotice={setNotice}
        onError={setError}
      />
    </>
  );
}
