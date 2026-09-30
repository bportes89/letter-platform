"use client";

import { Building2, CheckCircle2, Plus, RefreshCw, ShieldCheck } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, User } from "@/lib/api";

type Administrator = {
  id: string;
  code: string | null;
  name: string;
  document: string;
  authorization_status: string;
  rules: Record<string, unknown>;
  rules_version: number;
  bacen_rules_synced_at: string | null;
  homologated_at: string | null;
  homologation_notes: string | null;
};

type BacenStatus = {
  provider: string;
  configured: boolean;
  mode: string;
  message: string;
};

const date = (value: string | null) => (value ? new Date(value).toLocaleString("pt-BR") : "—");

export function AdministratorsModule() {
  const [items, setItems] = useState<Administrator[]>([]);
  const [bacen, setBacen] = useState<BacenStatus | null>(null);
  const [me, setMe] = useState<User | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Administrator | null>(null);
  const [rulesDraft, setRulesDraft] = useState("");
  const [profileAdmin, setProfileAdmin] = useState<Administrator | null>(null);
  const [isBank, setIsBank] = useState(false);
  const [requiresHolder, setRequiresHolder] = useState(false);
  const [acceptsDirty, setAcceptsDirty] = useState(false);
  const [profileAlienations, setProfileAlienations] = useState<
    { quota_category_id: string; max_vehicle_age_years: number | null }[]
  >([]);
  const [quotaCategories, setQuotaCategories] = useState<
    { id: string; name: string; legacy_type: number; parent_id: string | null; title_sub: string | null }[]
  >([]);

  const maxYearOptions = [
    { value: "", label: "(sem restrição)" },
    { value: "0", label: "Somente Zero KM" },
    ...Array.from({ length: 30 }, (_, i) => ({ value: String(i + 1), label: `Até ${i + 1} ano(s)` })),
  ];

  function categorySelectOptions() {
    const parents = quotaCategories.filter((c) => c.legacy_type === 0);
    const subs = quotaCategories.filter((c) => c.legacy_type === 1);
    const out: { id: string; label: string }[] = [];
    for (const p of parents) {
      out.push({ id: p.id, label: p.title_sub || p.name });
      for (const s of subs.filter((x) => x.parent_id === p.id)) {
        out.push({ id: s.id, label: `-- ${s.name}` });
      }
    }
    const known = new Set(out.map((o) => o.id));
    for (const row of profileAlienations) {
      if (row.quota_category_id && !known.has(row.quota_category_id)) {
        const c = quotaCategories.find((x) => x.id === row.quota_category_id);
        out.push({ id: row.quota_category_id, label: c?.name || row.quota_category_id });
      }
    }
    return out;
  }

  const load = useCallback(async () => {
    const [admins, status, user, categories] = await Promise.all([
      api<Administrator[]>("/administrators"),
      api<BacenStatus>("/integrations/bacen-scr/status"),
      api<User>("/auth/me"),
      api<{ id: string; name: string; legacy_type: number; parent_id: string | null; title_sub: string | null }[]>(
        "/marketplace/quota-categories",
      ).catch(() => []),
    ]);
    setQuotaCategories(categories);
    setItems(admins);
    setBacen(status);
    setMe(user);
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar administradoras"));
  }, [load]);

  const canAdmin = me?.role === "PLATFORM_ADMIN" || me?.role === "INTERNAL_STAFF";

  async function createAdmin(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canAdmin) return;
    const f = new FormData(e.currentTarget);
    await api("/administrators", {
      method: "POST",
      body: JSON.stringify({
        name: f.get("name"),
        document: f.get("document"),
        code: f.get("code") || undefined,
      }),
    });
    e.currentTarget.reset();
    setMessage("Administradora cadastrada para homologação.");
    await load();
  }

  async function saveRules(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selected || !canAdmin) return;
    const rules = JSON.parse(rulesDraft) as Record<string, unknown>;
    await api(`/administrators/${selected.id}/rules`, {
      method: "PATCH",
      body: JSON.stringify({ rules, bump_version: true }),
    });
    setMessage(`Regras v${selected.rules_version + 1} publicadas para ${selected.name}.`);
    setSelected(null);
    await load();
  }

  async function syncBacenRules() {
    if (!canAdmin) return;
    const result = await api<{ total: number; changed: number; mode: string }>("/administrators/sync-bacen-rules", {
      method: "POST",
    });
    setMessage(`Varredura Bacen concluída (${result.mode}): ${result.changed} administradora(s) atualizada(s).`);
    await load();
  }

  async function homologate(admin: Administrator, approved: boolean) {
    if (!canAdmin) return;
    const notes = approved
      ? "Homologada conforme regulamento LETTER e regras Bacen versionadas."
      : "Reprovada na esteira de homologação.";
    await api(`/administrators/${admin.id}/homologate`, {
      method: "POST",
      body: JSON.stringify({ approved, notes }),
    });
    setMessage(approved ? `${admin.name} homologada.` : `${admin.name} reprovada.`);
    await load();
  }

  function openRules(admin: Administrator) {
    setSelected(admin);
    setRulesDraft(JSON.stringify(admin.rules, null, 2));
    setProfileAdmin(null);
  }

  function openProfile(admin: Administrator) {
    setProfileAdmin(admin);
    setSelected(null);
    const r = admin.rules as Record<string, unknown>;
    setIsBank(Boolean(r.is_bank));
    setRequiresHolder(Boolean(r.requires_account_holder));
    setAcceptsDirty(Boolean(r.accepts_dirty_name));
    const raw = (r.alienations as { quota_category_id?: string; max_vehicle_age_years?: number | null }[]) || [];
    setProfileAlienations(
      raw.map((a) => ({
        quota_category_id: a.quota_category_id || "",
        max_vehicle_age_years:
          a.max_vehicle_age_years === undefined || a.max_vehicle_age_years === null
            ? null
            : Number(a.max_vehicle_age_years),
      })),
    );
  }

  function addAlienationRow() {
    setProfileAlienations((rows) => [...rows, { quota_category_id: "", max_vehicle_age_years: null }]);
  }

  function removeAlienationRow(index: number) {
    setProfileAlienations((rows) => rows.filter((_, i) => i !== index));
  }

  function updateAlienationRow(index: number, patch: Partial<{ quota_category_id: string; max_vehicle_age_years: number | null }>) {
    setProfileAlienations((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  async function saveProfile(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!profileAdmin || !canAdmin) return;
    const alienations = profileAlienations
      .filter((a) => a.quota_category_id)
      .map((a) => ({
        quota_category_id: a.quota_category_id,
        max_vehicle_age_years: a.max_vehicle_age_years,
      }));
    await api(`/administrators/${profileAdmin.id}/marketplace-profile`, {
      method: "PATCH",
      body: JSON.stringify({
        is_bank: isBank,
        requires_account_holder: requiresHolder,
        accepts_dirty_name: acceptsDirty,
        alienations,
      }),
    });
    setMessage(`Perfil marketplace de ${profileAdmin.name} atualizado.`);
    setProfileAdmin(null);
    await load();
  }

  function flagLabel(admin: Administrator, key: string) {
    const r = admin.rules as Record<string, unknown>;
    return r[key] ? "Sim" : "Não";
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">MÓDULO LETTER</span>
          <h1>Administradoras</h1>
          <p>Homologação, regras versionadas e varredura Nina no Bacen a cada 24h por administradora.</p>
        </div>
        <div className="operational-icon"><Building2 /></div>
      </div>

      {canAdmin && (
        <div className="notice">
          <RefreshCw />
          A Nina sincroniza o regulamento de cada administradora no Bacen/SCR a cada <b>24 horas</b>,
          alimentando aprovação (pré-análise) e utilização de crédito (marketplace/inventário).
          <button type="button" className="table-action" onClick={() => void syncBacenRules()}>Sincronizar agora</button>
        </div>
      )}

      {message && <div className="notice"><CheckCircle2 />{message}</div>}
      {error && <div className="error">{error}</div>}

      {bacen && (
        <div className="notice">
          <ShieldCheck />
          Bacen SCR/Registrato — modo <b>{bacen.mode}</b>
          {bacen.configured ? " (produtivo)" : " (sandbox)"}: {bacen.message}
        </div>
      )}

      {canAdmin && (
        <section className="panel">
          <h2><Plus /> Nova administradora</h2>
          <form className="stack-form" onSubmit={createAdmin}>
            <input name="name" placeholder="Nome" required />
            <input name="document" placeholder="CNPJ (14 dígitos)" required minLength={14} maxLength={20} />
            <input name="code" placeholder="Código (ex.: EMBRACON)" />
            <button type="submit">Cadastrar</button>
          </form>
        </section>
      )}

      <section className="panel identity-table">
        <h2>Administradoras homologadas e pendentes</h2>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Administradora</th>
                <th>Status</th>
                <th>Banco</th>
                <th>Correntista</th>
                <th>Nome sujo</th>
                <th>Regras</th>
                <th>Última varredura Bacen</th>
                <th>Homologação</th>
                {canAdmin && <th>Ações</th>}
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id}>
                  <td><b>{a.name}</b><small>{a.code} · {a.document}</small></td>
                  <td><span className={`pill pill-${a.authorization_status.toLowerCase()}`}>{a.authorization_status}</span></td>
                  <td>{flagLabel(a, "is_bank")}</td>
                  <td>{flagLabel(a, "requires_account_holder")}</td>
                  <td>{flagLabel(a, "accepts_dirty_name")}</td>
                  <td>v{a.rules_version}</td>
                  <td>{date(a.bacen_rules_synced_at)}</td>
                  <td>{date(a.homologated_at)}</td>
                  {canAdmin && (
                    <td className="actions-cell">
                      <button type="button" className="table-action" onClick={() => openProfile(a)}>Perfil</button>
                      <button type="button" className="table-action" onClick={() => openRules(a)}>Regras JSON</button>
                      {a.authorization_status !== "AUTHORIZED" && (
                        <button type="button" className="table-action" onClick={() => homologate(a, true)}>Homologar</button>
                      )}
                      {a.authorization_status === "AUTHORIZED" && (
                        <button type="button" className="table-action" onClick={() => homologate(a, false)}>Suspender</button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {profileAdmin && canAdmin && (
        <section className="panel">
          <h2>Perfil marketplace — {profileAdmin.name}</h2>
          <p className="muted">Espelho do legado: banco, correntista, nome sujo e alienações (categoria + ano máx. para veículos).</p>
          <form className="stack-form" onSubmit={saveProfile}>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input type="checkbox" checked={isBank} onChange={(e) => setIsBank(e.target.checked)} /> É banco (lista no chat)
            </label>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input type="checkbox" checked={requiresHolder} onChange={(e) => setRequiresHolder(e.target.checked)} /> Exige ser correntista
            </label>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input type="checkbox" checked={acceptsDirty} onChange={(e) => setAcceptsDirty(e.target.checked)} /> Aceita nome sujo (SPC/Serasa)
            </label>

            <div style={{ marginTop: 8 }}>
              <h3 style={{ fontSize: 13, marginBottom: 8 }}>Alienações</h3>
              <p className="muted" style={{ fontSize: 11, marginBottom: 10 }}>
                Tipos de bem que a administradora financia. Ano máximo vale para veículos; imóveis ignoram o ano.
              </p>
              {profileAlienations.length === 0 && (
                <p className="muted" style={{ fontSize: 11 }}>Nenhuma alienação — todas as categorias de cota podem aparecer (salvo outras regras).</p>
              )}
              {profileAlienations.map((row, index) => (
                <div key={index} style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "flex-end", marginBottom: 10 }}>
                  <label style={{ flex: "1 1 220px", fontSize: 11 }}>
                    Categoria / subcategoria
                    <select
                      value={row.quota_category_id}
                      onChange={(e) => updateAlienationRow(index, { quota_category_id: e.target.value })}
                      required
                    >
                      <option value="">Selecione…</option>
                      {categorySelectOptions().map((o) => (
                        <option key={o.id} value={o.id}>{o.label}</option>
                      ))}
                    </select>
                  </label>
                  <label style={{ flex: "1 1 180px", fontSize: 11 }}>
                    Ano máx. fabricação
                    <select
                      value={row.max_vehicle_age_years === null ? "" : String(row.max_vehicle_age_years)}
                      onChange={(e) => {
                        const v = e.target.value;
                        updateAlienationRow(index, {
                          max_vehicle_age_years: v === "" ? null : Number(v),
                        });
                      }}
                    >
                      {maxYearOptions.map((o) => (
                        <option key={o.value || "none"} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  </label>
                  <button type="button" className="table-action" onClick={() => removeAlienationRow(index)} title="Remover alienação">
                    Remover
                  </button>
                </div>
              ))}
              <button type="button" className="table-action" onClick={addAlienationRow}>+ Adicionar alienação</button>
            </div>

            <button type="submit">Salvar perfil</button>
            <button type="button" className="table-action" onClick={() => setProfileAdmin(null)}>Cancelar</button>
          </form>
        </section>
      )}

      {selected && canAdmin && (
        <section className="panel">
          <h2>Regras versionadas — {selected.name}</h2>
          <p className="muted">Parâmetros usados pela Nina, QuitCon e inventário (doc. 227 / Bacen).</p>
          <form className="stack-form" onSubmit={saveRules}>
            <textarea value={rulesDraft} onChange={(e) => setRulesDraft(e.target.value)} rows={12} required />
            <button type="submit">Publicar nova versão</button>
            <button type="button" className="table-action" onClick={() => setSelected(null)}>Cancelar</button>
          </form>
        </section>
      )}
    </>
  );
}
