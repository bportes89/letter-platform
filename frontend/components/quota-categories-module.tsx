"use client";

import { CheckCircle2, FolderTree, RefreshCw } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type QuotaCategory = {
  id: string;
  legacy_id: number | null;
  active: boolean;
  name: string;
  title_sub: string | null;
  legacy_type: number;
  parent_id: string | null;
  sort_order: number;
  asset_class: string | null;
};

const ASSET_LABELS: Record<string, string> = {
  REAL_ESTATE: "Imóvel",
  VEHICLE: "Veículo",
  OTHER: "Outros",
};

export function QuotaCategoriesModule() {
  const [items, setItems] = useState<QuotaCategory[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"parents" | "children">("parents");

  const load = useCallback(async () => {
    const rows = await api<QuotaCategory[]>("/marketplace/quota-categories");
    setItems(rows);
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar categorias"));
  }, [load]);

  const parents = useMemo(() => items.filter((x) => x.legacy_type === 0), [items]);
  const children = useMemo(() => items.filter((x) => x.legacy_type === 1), [items]);
  const parentName = useMemo(() => {
    const map = new Map(parents.map((p) => [p.id, p.title_sub || p.name]));
    return (id: string | null) => (id ? map.get(id) ?? "—" : "—");
  }, [parents]);

  async function importLegacy() {
    setError("");
    setNotice("");
    try {
      const r = await api<{ created: number; updated: number; total_legacy: number }>(
        "/marketplace/quota-categories/import-legacy",
        { method: "POST" },
      );
      setNotice(`Importação legado: ${r.created} criadas, ${r.updated} atualizadas (${r.total_legacy} no SQL).`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Importação falhou (verifique legacy/letter_banco_new.sql no servidor).");
    }
  }

  async function submitParent(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setError("");
    try {
      await api("/marketplace/quota-categories", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          title_sub: fd.get("title_sub") || null,
          legacy_type: 0,
          sort_order: Number(fd.get("sort_order") || 999),
          asset_class: fd.get("asset_class") || null,
          active: true,
        }),
      });
      e.currentTarget.reset();
      setNotice("Categoria criada.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar");
    }
  }

  async function submitChild(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setError("");
    try {
      await api("/marketplace/quota-categories", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          legacy_type: 1,
          parent_id: fd.get("parent_id"),
          sort_order: Number(fd.get("sort_order") || 999),
          active: true,
        }),
      });
      e.currentTarget.reset();
      setNotice("Subcategoria criada.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar");
    }
  }

  async function toggleActive(row: QuotaCategory) {
    setError("");
    try {
      await api(`/marketplace/quota-categories/${row.id}`, {
        method: "PATCH",
        body: JSON.stringify({ active: !row.active }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar");
    }
  }

  const displayed = tab === "parents" ? parents : children;

  return (
    <div className="module-shell">
      <div className="module-hero">
        <FolderTree />
        <div>
          <h1>Categorias de cotas</h1>
          <p>
            Grupos e subcategorias como no admin legado (<code>quotas_categories</code>). Use{" "}
            <b>Importar do legado</b> na máquina com <code>legacy/letter_banco_new.sql</code> ou cadastre manualmente.
          </p>
        </div>
      </div>

      <div className="panel">
        <div className="panel-title" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <button type="button" className={tab === "parents" ? "primary-button" : "table-action"} onClick={() => setTab("parents")}>
            Categorias ({parents.length})
          </button>
          <button type="button" className={tab === "children" ? "primary-button" : "table-action"} onClick={() => setTab("children")}>
            Subcategorias ({children.length})
          </button>
          <button type="button" className="table-action" onClick={() => void importLegacy()}>
            <RefreshCw /> Importar do legado
          </button>
        </div>

        {notice && (
          <div className="notice">
            <CheckCircle2 /> {notice}
          </div>
        )}
        {error && <div className="error">{error}</div>}

        {tab === "parents" ? (
          <form className="quick-form" onSubmit={submitParent} style={{ marginBottom: 16 }}>
            <input name="title_sub" placeholder="Título curto (ex. Imóvel)" />
            <input name="name" placeholder="Nome da categoria" required />
            <select name="asset_class" defaultValue="">
              <option value="">Classe (opcional)</option>
              <option value="REAL_ESTATE">Imóvel</option>
              <option value="VEHICLE">Veículo</option>
              <option value="OTHER">Outros</option>
            </select>
            <input name="sort_order" type="number" min={0} placeholder="Ordem" defaultValue={999} />
            <button type="submit" className="primary-button">Adicionar categoria</button>
          </form>
        ) : (
          <form className="quick-form" onSubmit={submitChild} style={{ marginBottom: 16 }}>
            <select name="parent_id" required>
              <option value="">Categoria pai</option>
              {parents.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title_sub || p.name}
                </option>
              ))}
            </select>
            <input name="name" placeholder="Nome da subcategoria" required />
            <input name="sort_order" type="number" min={0} placeholder="Ordem" defaultValue={999} />
            <button type="submit" className="primary-button">Adicionar subcategoria</button>
          </form>
        )}

        <table className="data-table">
          <thead>
            <tr>
              <th>Ordem</th>
              <th>Nome</th>
              {tab === "parents" ? <th>Título</th> : <th>Pai</th>}
              <th>Classe</th>
              <th>Legado ID</th>
              <th>Ativo</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {displayed.map((row) => (
              <tr key={row.id}>
                <td>{row.sort_order}</td>
                <td>{row.name}</td>
                {tab === "parents" ? <td>{row.title_sub || "—"}</td> : <td>{parentName(row.parent_id)}</td>}
                <td>{row.asset_class ? ASSET_LABELS[row.asset_class] ?? row.asset_class : "—"}</td>
                <td>{row.legacy_id ?? "—"}</td>
                <td>{row.active ? "Sim" : "Não"}</td>
                <td>
                  <button type="button" className="table-action" onClick={() => void toggleActive(row)}>
                    {row.active ? "Desativar" : "Ativar"}
                  </button>
                </td>
              </tr>
            ))}
            {displayed.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  Nenhum registro. Importe do legado ou cadastre acima.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
