"use client";

import { CheckCircle2, FileText, Mail, RefreshCw } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type CmsText = {
  id: string;
  legacy_id: number | null;
  active: boolean;
  kind: string;
  name_main: string;
  subject: string | null;
  slug: string | null;
  body_html: string;
  whatsapp: string | null;
  sms: string | null;
  footer_place: number;
  sort_order: number;
};

export function CmsTextsModule() {
  const [items, setItems] = useState<CmsText[]>([]);
  const [tab, setTab] = useState<"PAGE" | "EMAIL">("EMAIL");
  const [selected, setSelected] = useState<CmsText | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const rows = await api<CmsText[]>("/cms/texts");
    setItems(rows);
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar textos"));
  }, [load]);

  const filtered = useMemo(() => items.filter((x) => x.kind === tab), [items, tab]);

  async function importLegacy() {
    setError("");
    setNotice("");
    try {
      const r = await api<{ created: number; updated: number; total_legacy: number; marketplace_slug_sync?: number }>(
        "/cms/texts/import-legacy",
        { method: "POST" },
      );
      const slugNote =
        r.marketplace_slug_sync != null && r.marketplace_slug_sync > 0
          ? ` · ${r.marketplace_slug_sync} e-mails marketplace com slug canônico.`
          : "";
      setNotice(`Importação legado: ${r.created} criados, ${r.updated} atualizados (${r.total_legacy} no SQL).${slugNote}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Importação falhou");
    }
  }

  async function saveEdit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selected) return;
    const fd = new FormData(e.currentTarget);
    setError("");
    try {
      await api(`/cms/texts/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name_main: fd.get("name_main"),
          subject: fd.get("subject") || null,
          slug: fd.get("slug") || null,
          body_html: fd.get("body_html"),
          whatsapp: fd.get("whatsapp") || null,
          sms: fd.get("sms") || null,
          footer_place: Number(fd.get("footer_place") || 0),
          sort_order: Number(fd.get("sort_order") || 999),
          active: fd.get("active") === "on",
        }),
      });
      setNotice("Texto atualizado.");
      setSelected(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar");
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">CADASTRO</span>
          <h1>Textos e e-mails</h1>
          <p>
            Páginas institucionais e templates de comunicação (legado texts + corpo HTML).
            E-mails marketplace: slugs email-marketplace-* (boleto, pagamento, boas-vindas, documento, conclusão). Import legado mapeia texts 1001+.
          </p>
        </div>
        <div className="operational-icon">{tab === "EMAIL" ? <Mail /> : <FileText />}</div>
      </div>

      {notice && <div className="notice"><CheckCircle2 />{notice}</div>}
      {error && <div className="error">{error}</div>}

      <div className="marketplace-subtabs">
        <button type="button" className={tab === "EMAIL" ? "active" : ""} onClick={() => setTab("EMAIL")}>E-mails</button>
        <button type="button" className={tab === "PAGE" ? "active" : ""} onClick={() => setTab("PAGE")}>Páginas</button>
        <button type="button" className="table-action" onClick={() => void importLegacy()}>
          <RefreshCw /> Importar SQL legado
        </button>
      </div>

      <section className="panel identity-table">
        <table className="data-table">
          <thead>
            <tr>
              <th>Nome</th>
              <th>Assunto / slug</th>
              <th>Legado</th>
              <th>Ativo</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.id}>
                <td><b>{row.name_main}</b></td>
                <td><small>{row.subject || row.slug || "—"}</small></td>
                <td>{row.legacy_id ?? "—"}</td>
                <td>{row.active ? "Sim" : "Não"}</td>
                <td>
                  <button type="button" className="table-action" onClick={() => setSelected(row)}>Editar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {selected && (
        <section className="panel">
          <h2>Editar — {selected.name_main}</h2>
          <form className="stack-form" onSubmit={saveEdit}>
            <input name="name_main" value={selected.name_main} onChange={(e) => setSelected({ ...selected, name_main: e.target.value })} required />
            <input name="subject" placeholder="Assunto (e-mail) ou título" value={selected.subject || ""} onChange={(e) => setSelected({ ...selected, subject: e.target.value })} />
            <input name="slug" placeholder="Slug público (páginas)" value={selected.slug || ""} onChange={(e) => setSelected({ ...selected, slug: e.target.value })} />
            <textarea name="body_html" rows={14} value={selected.body_html} onChange={(e) => setSelected({ ...selected, body_html: e.target.value })} required />
            <textarea name="whatsapp" rows={3} placeholder="WhatsApp" value={selected.whatsapp || ""} onChange={(e) => setSelected({ ...selected, whatsapp: e.target.value })} />
            <textarea name="sms" rows={2} placeholder="SMS" value={selected.sms || ""} onChange={(e) => setSelected({ ...selected, sms: e.target.value })} />
            <input name="footer_place" type="number" min={0} max={2} value={selected.footer_place} onChange={(e) => setSelected({ ...selected, footer_place: Number(e.target.value) })} />
            <input name="sort_order" type="number" value={selected.sort_order} onChange={(e) => setSelected({ ...selected, sort_order: Number(e.target.value) })} />
            <label><input type="checkbox" name="active" checked={selected.active} onChange={(e) => setSelected({ ...selected, active: e.target.checked })} /> Ativo</label>
            <button type="submit">Salvar</button>
            <button type="button" className="table-action" onClick={() => setSelected(null)}>Cancelar</button>
          </form>
        </section>
      )}
    </>
  );
}
