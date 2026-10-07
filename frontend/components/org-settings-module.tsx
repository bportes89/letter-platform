"use client";

import Link from "next/link";
import { CheckCircle2, Info, RefreshCw, Settings } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type SettingField = { key: string; label: string; hint?: string };

type SettingsPayload = {
  groups: Record<string, SettingField[]>;
  values: Record<string, string>;
  group_meta?: Record<string, { title: string; summary: string }>;
};

const TAB_ORDER = ["info", "payments", "templates", "meta"] as const;

const FALLBACK_TAB_LABELS: Record<string, string> = {
  info: "Informações do site",
  payments: "Pagamentos e taxa Letter",
  templates: "Contratos e textos de fluxo",
  meta: "Meta tags (SEO)",
};

export function OrgSettingsModule() {
  const [data, setData] = useState<SettingsPayload | null>(null);
  const [tab, setTab] = useState<string>("info");
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

  const tabLabels = useMemo(() => {
    const meta = data?.group_meta ?? {};
    const labels: Record<string, string> = { ...FALLBACK_TAB_LABELS };
    for (const key of TAB_ORDER) {
      if (meta[key]?.title) labels[key] = meta[key].title;
    }
    return labels;
  }, [data?.group_meta]);

  const tabHelp = data?.group_meta?.[tab]?.summary ?? "";

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
          <p>
            Ajustes globais da organização: contato no site, taxa Letter no marketplace, templates HTML de contratos
            e meta tags para buscadores. Comissões da rede MMN e markup por fornecedor ficam em outros menus (veja a
            aba Pagamentos).
          </p>
        </div>
        <div className="operational-icon"><Settings /></div>
      </div>

      {notice && <div className="notice"><CheckCircle2 />{notice}</div>}
      {error && <div className="error">{error}</div>}

      <div className="marketplace-subtabs">
        {TAB_ORDER.filter((key) => data?.groups?.[key]).map((key) => (
          <button key={key} type="button" className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
            {tabLabels[key] ?? key}
          </button>
        ))}
        <button type="button" className="table-action" disabled={busy} onClick={() => void importLegacy()}>
          <RefreshCw /> Importar SQL legado
        </button>
      </div>

      {tabHelp ? (
        <div className="notice" style={{ marginBottom: 12 }}>
          <Info />
          <div>
            <b>{tabLabels[tab]}</b>
            <p style={{ margin: "6px 0 0", lineHeight: 1.45 }}>{tabHelp}</p>
            {tab === "payments" && (
              <p style={{ margin: "8px 0 0", fontSize: "0.9rem" }}>
                <Link href="/modules/mmn">Rede e comissões (MMN)</Link>
                {" · "}
                <Link href="/modules/fornecedores">Fornecedores (markup / % plataforma)</Link>
                {" · "}
                <Link href="/modules/cms-texts">Textos e e-mails</Link>
              </p>
            )}
            {tab === "templates" && (
              <p style={{ margin: "8px 0 0", fontSize: "0.9rem" }}>
                Contratos em Word devem ser convertidos para HTML antes de colar aqui. Use «Importar SQL legado» se já
                existirem no banco antigo.
              </p>
            )}
          </div>
        </div>
      ) : null}

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
                <span>{f.label}</span>
                {f.hint ? <small className="muted" style={{ display: "block", marginBottom: 6 }}>{f.hint}</small> : null}
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
