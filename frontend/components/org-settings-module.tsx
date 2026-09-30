"use client";

import { CheckCircle2, RefreshCw, Settings } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type SettingsPayload = {
  groups: Record<string, { key: string; label: string }[]>;
  values: Record<string, string>;
};

const GROUP_LABELS: Record<string, string> = {
  info: "Informações (menu 11)",
  payments: "Pagamentos (comissão / saque)",
  templates: "Contratos e textos de fluxo",
  meta: "Meta tags",
};

export function OrgSettingsModule() {
  const [data, setData] = useState<SettingsPayload | null>(null);
  const [tab, setTab] = useState("info");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const row = await api<SettingsPayload>("/admin/org-settings");
    setData(row);
    setDraft(row.values || {});
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar"));
  }, [load]);

  const fields = useMemo(() => data?.groups[tab] ?? [], [data, tab]);

  async function save() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const patch: Record<string, string> = {};
      for (const f of fields) {
        patch[f.key] = draft[f.key] ?? "";
      }
      const row = await api<SettingsPayload>("/admin/org-settings", {
        method: "PATCH",
        body: JSON.stringify({ values: patch }),
      });
      setData(row);
      setDraft(row.values);
      setNotice("Configurações salvas.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar");
    } finally {
      setBusy(false);
    }
  }

  async function importLegacy() {
    setBusy(true);
    setError("");
    try {
      const r = await api<{ created: number; updated: number }>("/admin/org-settings/import-legacy", {
        method: "POST",
      });
      setNotice(`Importação x_settings: ${r.created} criadas, ${r.updated} atualizadas.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Importação falhou");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">ADMIN</span>
          <h1>Configurações gerais</h1>
          <p>Legado x_settings: informações do site, comissão da plataforma e templates HTML (contrato marketplace, SDC, venda direta).</p>
        </div>
        <div className="operational-icon"><Settings /></div>
      </div>

      {notice && <div className="notice"><CheckCircle2 />{notice}</div>}
      {error && <div className="error">{error}</div>}

      <div className="marketplace-subtabs">
        {Object.keys(GROUP_LABELS).map((key) => (
          <button key={key} type="button" className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
            {GROUP_LABELS[key]}
          </button>
        ))}
        <button type="button" className="table-action" disabled={busy} onClick={() => void importLegacy()}>
          <RefreshCw /> Importar SQL legado
        </button>
      </div>

      <section className="panel">
        <form
          className="stack-form"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          {fields.map((f) => {
            const isLong = f.key.includes("html") || f.key.startsWith("txt_") || f.key.includes("meta_");
            return (
              <label key={f.key}>
                {f.label}
                {isLong ? (
                  <textarea
                    rows={10}
                    value={draft[f.key] ?? ""}
                    onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
                    style={{ fontFamily: f.key.includes("html") ? "monospace" : undefined, fontSize: 12 }}
                  />
                ) : (
                  <input
                    value={draft[f.key] ?? ""}
                    onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
                  />
                )}
              </label>
            );
          })}
          <button type="submit" disabled={busy || fields.length === 0}>Salvar bloco</button>
        </form>
      </section>
    </>
  );
}
