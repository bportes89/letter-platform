"use client";

import { ArrowDown, ArrowUp, CheckCircle2, FolderTree, RefreshCw } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { MAX_VEHICLE_AGE_OPTIONS, maxVehicleAgeLabel } from "@/lib/quota-alienation-options";

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

type Administrator = {
  id: string;
  name: string;
  rules: Record<string, unknown>;
};

type AlienationRow = { quota_category_id: string; max_vehicle_age_years: number | null };

const ASSET_LABELS: Record<string, string> = {
  REAL_ESTATE: "Imóvel",
  VEHICLE: "Veículo",
  OTHER: "Outros",
};

function parseAlienations(rules: Record<string, unknown>): AlienationRow[] {
  const raw = (rules.alienations as { quota_category_id?: string; max_vehicle_age_years?: number | null }[]) || [];
  return raw.map((a) => ({
    quota_category_id: a.quota_category_id || "",
    max_vehicle_age_years:
      a.max_vehicle_age_years === undefined || a.max_vehicle_age_years === null
        ? null
        : Number(a.max_vehicle_age_years),
  }));
}

export type QuotaCategoriesModuleProps = {
  /** Rota dedicada: categorias ou subcategorias (menu legado em dois itens). */
  defaultTab?: "parents" | "children";
};

export function QuotaCategoriesModule({ defaultTab = "parents" }: QuotaCategoriesModuleProps) {
  const [items, setItems] = useState<QuotaCategory[]>([]);
  const [admins, setAdmins] = useState<Administrator[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"parents" | "children">(defaultTab);
  const [movingId, setMovingId] = useState<string | null>(null);
  const [selectedChildId, setSelectedChildId] = useState<string | null>(null);
  const [alienationDraft, setAlienationDraft] = useState<Record<string, { enabled: boolean; maxYears: string }>>({});
  const [savingAdminId, setSavingAdminId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const rows = await api<QuotaCategory[]>("/marketplace/quota-categories");
    setItems(rows);
  }, []);

  const loadAdmins = useCallback(async () => {
    try {
      const rows = await api<Administrator[]>("/administrators");
      setAdmins(rows);
    } catch {
      setAdmins([]);
    }
  }, []);

  useEffect(() => {
    setTab(defaultTab);
  }, [defaultTab]);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar categorias"));
  }, [load]);

  useEffect(() => {
    if (tab === "children") void loadAdmins();
  }, [tab, loadAdmins]);

  const sortRows = (rows: QuotaCategory[]) =>
    [...rows].sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name, "pt-BR"));

  const parents = useMemo(() => sortRows(items.filter((x) => x.legacy_type === 0)), [items]);
  const parentName = useMemo(() => {
    const map = new Map(parents.map((p) => [p.id, p.title_sub || p.name]));
    return (id: string | null) => (id ? map.get(id) ?? "—" : "—");
  }, [parents]);
  const parentById = useMemo(() => new Map(parents.map((p) => [p.id, p])), [parents]);
  const children = useMemo(() => {
    const parentOrder = new Map(parents.map((p, i) => [p.id, i]));
    const rows = items.filter((x) => x.legacy_type === 1);
    return sortRows(rows).sort((a, b) => {
      const oa = parentOrder.get(a.parent_id ?? "") ?? 999;
      const ob = parentOrder.get(b.parent_id ?? "") ?? 999;
      if (oa !== ob) return oa - ob;
      return a.sort_order - b.sort_order || a.name.localeCompare(b.name, "pt-BR");
    });
  }, [items, parents]);

  const selectedChild = useMemo(
    () => children.find((c) => c.id === selectedChildId) ?? null,
    [children, selectedChildId],
  );

  const parentNeedsYear = useMemo(() => {
    if (!selectedChild?.parent_id) return false;
    const parent = parentById.get(selectedChild.parent_id);
    return parent?.asset_class === "VEHICLE";
  }, [selectedChild, parentById]);

  useEffect(() => {
    if (!selectedChild) {
      setAlienationDraft({});
      return;
    }
    const draft: Record<string, { enabled: boolean; maxYears: string }> = {};
    for (const admin of admins) {
      const rows = parseAlienations(admin.rules);
      const hit = rows.find((r) => r.quota_category_id === selectedChild.id);
      draft[admin.id] = {
        enabled: Boolean(hit),
        maxYears:
          hit?.max_vehicle_age_years === null || hit?.max_vehicle_age_years === undefined
            ? ""
            : String(hit.max_vehicle_age_years),
      };
    }
    setAlienationDraft(draft);
  }, [selectedChild, admins]);

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

  function siblingIndex(row: QuotaCategory, list: QuotaCategory[]) {
    return list.findIndex((x) => x.id === row.id);
  }

  async function moveRow(row: QuotaCategory, direction: "up" | "down", list: QuotaCategory[]) {
    const idx = siblingIndex(row, list);
    if (direction === "up" && idx <= 0) return;
    if (direction === "down" && (idx < 0 || idx >= list.length - 1)) return;
    setError("");
    setMovingId(row.id);
    try {
      await api(`/marketplace/quota-categories/${row.id}/move`, {
        method: "POST",
        body: JSON.stringify({ direction }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível reordenar.");
    } finally {
      setMovingId(null);
    }
  }

  function canMoveUp(row: QuotaCategory, list: QuotaCategory[]) {
    if (tab === "children") {
      const idx = siblingIndex(row, list);
      if (idx <= 0) return false;
      return list[idx - 1]?.parent_id === row.parent_id;
    }
    return siblingIndex(row, list) > 0;
  }

  function canMoveDown(row: QuotaCategory, list: QuotaCategory[]) {
    const idx = siblingIndex(row, list);
    if (idx < 0 || idx >= list.length - 1) return false;
    if (tab === "children") {
      return list[idx + 1]?.parent_id === row.parent_id;
    }
    return true;
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

  function updateAlienationDraft(adminId: string, patch: Partial<{ enabled: boolean; maxYears: string }>) {
    setAlienationDraft((prev) => ({
      ...prev,
      [adminId]: { ...prev[adminId], enabled: prev[adminId]?.enabled ?? false, maxYears: prev[adminId]?.maxYears ?? "", ...patch },
    }));
  }

  async function saveAdminAlienation(admin: Administrator) {
    if (!selectedChild) return;
    const draft = alienationDraft[admin.id];
    if (!draft) return;
    setSavingAdminId(admin.id);
    setError("");
    try {
      const r = admin.rules;
      let alienations = parseAlienations(r).filter((a) => a.quota_category_id !== selectedChild.id);
      if (draft.enabled) {
        alienations.push({
          quota_category_id: selectedChild.id,
          max_vehicle_age_years: draft.maxYears === "" ? null : Number(draft.maxYears),
        });
      }
      await api(`/administrators/${admin.id}/marketplace-profile`, {
        method: "PATCH",
        body: JSON.stringify({
          is_bank: Boolean(r.is_bank),
          requires_account_holder: Boolean(r.requires_account_holder),
          accepts_dirty_name: Boolean(r.accepts_dirty_name),
          alienations: alienations.filter((a) => a.quota_category_id).map((a) => ({
            quota_category_id: a.quota_category_id,
            max_vehicle_age_years: a.max_vehicle_age_years,
          })),
        }),
      });
      setNotice(`Alienação de ${admin.name} atualizada para "${selectedChild.name}".`);
      await loadAdmins();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar alienação");
    } finally {
      setSavingAdminId(null);
    }
  }

  const displayed = tab === "parents" ? parents : children;
  const isSubRoute = defaultTab === "children";

  return (
    <div className="module-shell">
      <div className="module-hero">
        <FolderTree />
        <div>
          <h1>{isSubRoute ? "Subcategorias de cotas" : "Categorias de cotas"}</h1>
          <p>
            {isSubRoute
              ? "Tipos de bem (Carro, Casa, Caminhão…) e regras de alienação por administradora e ano máximo — como no admin legado (menu Subcategorias + matriz admins×categorias)."
              : "Grupos principais (Imóvel, Veículo, SDC…) como no legado. Subcategorias e alienações ficam no menu Subcategorias de cotas."}
          </p>
        </div>
      </div>

      <div className="panel">
        <div className="marketplace-tabs" style={{ margin: "0 0 1rem" }}>
          <Link
            href="/modules/quota-categories"
            className={`marketplace-tab${tab === "parents" ? " active" : ""}`}
            onClick={() => setTab("parents")}
          >
            Categorias ({parents.length})
          </Link>
          <Link
            href="/modules/quota-subcategories"
            className={`marketplace-tab${tab === "children" ? " active" : ""}`}
            onClick={() => setTab("children")}
          >
            Subcategorias ({children.length})
          </Link>
        </div>

        <div className="panel-title" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 12 }}>
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
            <button type="submit" className="primary-button">Adicionar subcategoria</button>
          </form>
        )}

        <table className="data-table">
          <thead>
            <tr>
              <th>Posição</th>
              <th>Nome</th>
              {tab === "parents" ? <th>Título</th> : <th>Pai</th>}
              <th>Classe</th>
              <th>Legado ID</th>
              <th>Ativo</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {displayed.map((row, index) => (
              <tr
                key={row.id}
                style={
                  tab === "children" && selectedChildId === row.id
                    ? { background: "rgba(12, 42, 30, 0.06)", outline: "1px solid var(--green)" }
                    : undefined
                }
                onClick={tab === "children" ? () => setSelectedChildId(row.id) : undefined}
              >
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span className="muted" style={{ minWidth: 18 }}>{index + 1}</span>
                    <button
                      type="button"
                      className="table-action"
                      title="Subir"
                      disabled={movingId === row.id || !canMoveUp(row, displayed)}
                      onClick={(e) => {
                        e.stopPropagation();
                        void moveRow(row, "up", displayed);
                      }}
                    >
                      <ArrowUp size={14} />
                    </button>
                    <button
                      type="button"
                      className="table-action"
                      title="Descer"
                      disabled={movingId === row.id || !canMoveDown(row, displayed)}
                      onClick={(e) => {
                        e.stopPropagation();
                        void moveRow(row, "down", displayed);
                      }}
                    >
                      <ArrowDown size={14} />
                    </button>
                  </div>
                </td>
                <td>{row.name}</td>
                {tab === "parents" ? <td>{row.title_sub || "—"}</td> : <td>{parentName(row.parent_id)}</td>}
                <td>{row.asset_class ? ASSET_LABELS[row.asset_class] ?? row.asset_class : "—"}</td>
                <td>{row.legacy_id ?? "—"}</td>
                <td>{row.active ? "Sim" : "Não"}</td>
                <td>
                  <button
                    type="button"
                    className="table-action"
                    onClick={(e) => {
                      e.stopPropagation();
                      void toggleActive(row);
                    }}
                  >
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

        {tab === "children" && (
          <section style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
            <h2 style={{ fontSize: 15, marginBottom: 6 }}>Alienações por administradora</h2>
            <p className="muted" style={{ fontSize: 11, marginBottom: 14, lineHeight: 1.45 }}>
              Selecione uma subcategoria na tabela acima. Para cada administradora, marque se ela financia esse bem e o{" "}
              <b>ano máximo de fabricação</b> (veículos / máquinas / náuticos). Regras na categoria-pai continuam válidas no
              robô — aqui você configura a combinação específica da subcategoria. Também disponível em{" "}
              <Link href="/modules/administrators">Administradoras → Perfil</Link>.
            </p>
            {!selectedChild && (
              <p className="muted" style={{ fontSize: 12 }}>Clique em uma linha da tabela para configurar as alienações.</p>
            )}
            {selectedChild && (
              <>
                <p style={{ fontSize: 12, marginBottom: 12 }}>
                  Subcategoria: <b>{selectedChild.name}</b> ({parentName(selectedChild.parent_id)})
                  {parentNeedsYear ? "" : " — ano máximo ignorado para imóveis e bens sem idade."}
                </p>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Administradora</th>
                      <th>Financia este bem</th>
                      <th>Ano máx. fabricação</th>
                      <th>Atual</th>
                      <th>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {admins.map((admin) => {
                      const existing = parseAlienations(admin.rules).find(
                        (r) => r.quota_category_id === selectedChild.id,
                      );
                      const draft = alienationDraft[admin.id] ?? {
                        enabled: Boolean(existing),
                        maxYears:
                          existing?.max_vehicle_age_years === null || existing?.max_vehicle_age_years === undefined
                            ? ""
                            : String(existing.max_vehicle_age_years),
                      };
                      return (
                        <tr key={admin.id}>
                          <td>{admin.name}</td>
                          <td>
                            <input
                              type="checkbox"
                              checked={draft.enabled}
                              onChange={(e) => updateAlienationDraft(admin.id, { enabled: e.target.checked })}
                            />
                          </td>
                          <td>
                            <select
                              value={draft.maxYears}
                              disabled={!draft.enabled || !parentNeedsYear}
                              onChange={(e) => updateAlienationDraft(admin.id, { maxYears: e.target.value })}
                              style={{ minWidth: 160 }}
                            >
                              {MAX_VEHICLE_AGE_OPTIONS.map((o) => (
                                <option key={o.value || "none"} value={o.value}>{o.label}</option>
                              ))}
                            </select>
                          </td>
                          <td className="muted" style={{ fontSize: 11 }}>
                            {existing ? maxVehicleAgeLabel(existing.max_vehicle_age_years) : "—"}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="table-action"
                              disabled={savingAdminId === admin.id}
                              onClick={() => void saveAdminAlienation(admin)}
                            >
                              {savingAdminId === admin.id ? "Salvando…" : "Salvar"}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                    {admins.length === 0 && (
                      <tr>
                        <td colSpan={5} className="muted">Nenhuma administradora cadastrada.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
