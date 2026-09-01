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

  const load = useCallback(async () => {
    const [admins, status, user] = await Promise.all([
      api<Administrator[]>("/administrators"),
      api<BacenStatus>("/integrations/bacen-scr/status"),
      api<User>("/auth/me"),
    ]);
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
                  <td>v{a.rules_version}</td>
                  <td>{date(a.bacen_rules_synced_at)}</td>
                  <td>{date(a.homologated_at)}</td>
                  {canAdmin && (
                    <td className="actions-cell">
                      <button type="button" className="table-action" onClick={() => openRules(a)}>Regras</button>
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
