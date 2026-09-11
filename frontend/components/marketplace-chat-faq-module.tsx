"use client";

import { CheckCircle2, HelpCircle, Plus, RefreshCw } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type ChatFaq = {
  id: string;
  legacy_key: string | null;
  public_id: string;
  name: string;
  txt: string;
  active: boolean;
  sort_order: number;
};

export function MarketplaceChatFaqModule() {
  const [items, setItems] = useState<ChatFaq[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState<ChatFaq | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setItems(await api<ChatFaq[]>("/marketplace/chat-faq"));
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar FAQ"));
  }, [load]);

  async function ensureDefaults() {
    setError("");
    setBusy(true);
    try {
      const rows = await api<ChatFaq[]>("/marketplace/chat-faq/ensure-defaults", { method: "POST" });
      setItems(rows);
      setNotice("FAQ padrão (Paulo) garantida.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao garantir padrões");
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
      txt: String(fd.get("txt") || ""),
      legacy_key: String(fd.get("legacy_key") || "") || null,
      sort_order: Number(fd.get("sort_order") || 100),
      active: fd.get("active") === "1",
    };
    try {
      if (editing) {
        await api(`/marketplace/chat-faq/${editing.id}`, { method: "PATCH", body: JSON.stringify(body) });
        setNotice(`FAQ atualizada: ${body.name}`);
        setEditing(null);
      } else {
        await api("/marketplace/chat-faq", { method: "POST", body: JSON.stringify(body) });
        setNotice(`FAQ criada: ${body.name}`);
      }
      form.reset();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(item: ChatFaq) {
    setError("");
    try {
      await api(`/marketplace/chat-faq/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ active: !item.active }),
      });
      setNotice(`${item.name} ${item.active ? "ocultada do chat" : "ativa no chat"}.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao atualizar");
    }
  }

  async function remove(item: ChatFaq) {
    if (!window.confirm(`Excluir FAQ "${item.name}"?`)) return;
    setError("");
    setBusy(true);
    try {
      await api(`/marketplace/chat-faq/${item.id}`, { method: "DELETE" });
      setNotice("FAQ excluída.");
      if (editing?.id === item.id) setEditing(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao excluir");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">CHAT</span>
          <h1>FAQ do chat Marketplace</h1>
          <p>Perguntas do passo 10038–10040 no site. Só ativas aparecem no widget.</p>
        </div>
        <div className="operational-icon">
          <HelpCircle />
        </div>
      </div>

      <section className="panel operational-panel">
        <div className="notice">
          <HelpCircle />
          O chat usa <b>public_id</b> (= legacy_key Paulo ou UUID). Seed: ids 23, 24, 25, 40–42.
        </div>

        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1rem" }}>
          <button type="button" className="table-action" onClick={ensureDefaults} disabled={busy}>
            <RefreshCw /> Garantir FAQ Paulo
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
            <label className="marketplace-field marketplace-field-wide">
              Pergunta
              <input name="name" required minLength={3} defaultValue={editing?.name || ""} />
            </label>
            <label className="marketplace-field marketplace-field-wide">
              Resposta
              <textarea name="txt" required minLength={3} rows={4} defaultValue={editing?.txt || ""} />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Legacy key
              <input name="legacy_key" placeholder="23" defaultValue={editing?.legacy_key || ""} />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Ordem
              <input name="sort_order" type="number" defaultValue={editing?.sort_order ?? 100} />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Ativa
              <select name="active" defaultValue={editing ? (editing.active ? "1" : "0") : "1"}>
                <option value="1">Sim</option>
                <option value="0">Não</option>
              </select>
            </label>
            <button type="submit" className="marketplace-submit" disabled={busy}>
              <Plus />
              {editing ? "Salvar" : "Criar FAQ"}
            </button>
          </div>
        </form>

        <div className="table-wrap" style={{ marginTop: "1.25rem" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Ordem</th>
                <th>Pergunta</th>
                <th>ID chat</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.map((x) => (
                <tr key={x.id}>
                  <td>
                    <span className={`pill pill-${x.active ? "cleared" : "blocked"}`}>
                      {x.active ? "Ativa" : "Inativa"}
                    </span>
                  </td>
                  <td>{x.sort_order}</td>
                  <td>
                    <b>{x.name}</b>
                    <small>{x.txt.slice(0, 120)}{x.txt.length > 120 ? "…" : ""}</small>
                  </td>
                  <td>
                    <code>{x.public_id}</code>
                  </td>
                  <td className="actions-cell">
                    <button type="button" className="table-action" onClick={() => setEditing(x)}>
                      Editar
                    </button>
                    <button type="button" className="table-action" onClick={() => toggleActive(x)}>
                      {x.active ? "Ocultar" : "Ativar"}
                    </button>
                    <button type="button" className="table-action" onClick={() => remove(x)} disabled={busy}>
                      Excluir
                    </button>
                  </td>
                </tr>
              ))}
              {!items.length && (
                <tr>
                  <td colSpan={5}>Nenhuma FAQ — use &quot;Garantir FAQ Paulo&quot;.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
