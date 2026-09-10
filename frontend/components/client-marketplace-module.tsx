"use client";

import { CheckCircle2, ShoppingBag } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, API_URL, apiForm } from "@/lib/api";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type CompraRow = {
  lead_id: string;
  created_at: string | null;
  name: string;
  situation: string;
  situation_label: string;
  credit_value: string | null;
  entrada_value: string | null;
  source: string;
  quota_codes: string[];
  supplier_transfer_confirmed?: boolean;
  can_conclude?: boolean;
};

type CompraDetail = CompraRow & {
  purchase_readonly: Record<string, unknown>;
  can_conclude?: boolean;
  boleto?: {
    provider?: string;
    amount?: string;
    download_token?: string | null;
    due_date?: string | null;
  } | null;
};

type DocRow = {
  id: string;
  kind: string;
  filename: string;
  status: string;
  created_at?: string;
};

function money(value: string | null | undefined) {
  if (value == null || value === "") return "—";
  const n = Number(value);
  return Number.isFinite(n) ? brl.format(n) : value;
}

export function ClientMarketplaceModule() {
  const [rows, setRows] = useState<CompraRow[]>([]);
  const [selected, setSelected] = useState<CompraDetail | null>(null);
  const [docs, setDocs] = useState<DocRow[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setRows(await api<CompraRow[]>("/marketplace/me/compras"));
  }, []);

  useEffect(() => {
    const leadId =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("lead_id") ||
          sessionStorage.getItem("letter_chat_lead_id")
        : null;
    const run = async () => {
      if (leadId) {
        try {
          await api("/marketplace/me/bind-chat-lead", {
            method: "POST",
            body: JSON.stringify({ chat_lead_id: leadId }),
          });
          sessionStorage.removeItem("letter_chat_lead_id");
        } catch {
          /* bind best-effort */
        }
      }
      await load();
    };
    run().catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar compras"));
  }, [load]);

  async function openDetail(leadId: string) {
    setError("");
    setNotice("");
    try {
      const detail = await api<CompraDetail>(`/marketplace/me/compras/${leadId}`);
      setSelected(detail);
      setDocs(await api<DocRow[]>(`/marketplace/me/compras/${leadId}/documents`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao abrir compra");
    }
  }

  async function issueBoleto() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ boleto: CompraDetail["boleto"]; created: boolean }>(
        `/marketplace/me/compras/${selected.lead_id}/boleto`,
        { method: "POST" },
      );
      setSelected({ ...selected, boleto: result.boleto });
      setNotice(result.created ? "Boleto emitido." : "Boleto reutilizado.");
      const token = result.boleto?.download_token;
      if (token) {
        window.open(`${API_URL}/marketplace/cadastros/${selected.lead_id}/boleto/${token}`, "_blank");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao emitir boleto");
    } finally {
      setBusy(false);
    }
  }

  async function finalize() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api<CompraDetail>(`/marketplace/me/compras/${selected.lead_id}/finalize`, {
        method: "POST",
      });
      setSelected(updated);
      setNotice("Venda marcada como finalizada.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível finalizar");
    } finally {
      setBusy(false);
    }
  }

  async function uploadDoc(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selected) return;
    const fd = new FormData(e.currentTarget);
    const file = fd.get("file");
    if (!(file instanceof File) || !file.size) {
      setError("Selecione um arquivo.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("kind", String(fd.get("kind") || "OTHER"));
      body.append("file", file);
      await apiForm(`/marketplace/me/compras/${selected.lead_id}/documents`, body);
      setDocs(await api<DocRow[]>(`/marketplace/me/compras/${selected.lead_id}/documents`));
      setNotice("Documento enviado.");
      e.currentTarget.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no upload");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">ESCRITÓRIO</span>
          <h1>Minhas compras — Marketplace</h1>
          <p>Acompanhe boleto da entrada, envie documentos e finalize a venda após a transferência da cota.</p>
        </div>
        <div className="operational-icon">
          <ShoppingBag />
        </div>
      </div>

      {error ? <p className="form-error">{error}</p> : null}
      {notice ? (
        <p className="form-success">
          <CheckCircle2 size={16} /> {notice}
        </p>
      ) : null}

      <div className="panel-grid two">
        <section className="panel">
          <h2>Suas compras</h2>
          {rows.length === 0 ? (
            <p className="muted">Nenhuma compra Marketplace vinculada à sua conta ainda.</p>
          ) : (
            <ul className="list-plain">
              {rows.map((row) => (
                <li key={row.lead_id}>
                  <button type="button" className="list-row-btn" onClick={() => void openDetail(row.lead_id)}>
                    <strong>{row.quota_codes?.join(", ") || "Cota"}</strong>
                    <span>
                      {money(row.credit_value)} · entrada {money(row.entrada_value)}
                    </span>
                    <em>{row.situation_label}</em>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          {!selected ? (
            <p className="muted">Selecione uma compra para ver boleto, documentos e finalização.</p>
          ) : (
            <>
              <h2>Detalhe</h2>
              <p>
                Situação: <strong>{selected.situation_label}</strong>
                {selected.supplier_transfer_confirmed ? " · Fornecedor confirmou transferência" : ""}
              </p>
              <p>
                Crédito {money(selected.credit_value)} · Entrada {money(selected.entrada_value)}
              </p>
              <div className="actions-row">
                <button type="button" disabled={busy} onClick={() => void issueBoleto()}>
                  Baixar boleto
                </button>
                <button
                  type="button"
                  className="primary"
                  disabled={busy || selected.situation === "CONCLUIDO" || !selected.can_conclude}
                  onClick={() => void finalize()}
                  title={
                    !selected.can_conclude
                      ? "Aguarde o fornecedor confirmar a transferência da cota"
                      : undefined
                  }
                >
                  Marcar venda como finalizada
                </button>
              </div>

              <h3>Documentos</h3>
              <ul className="list-plain">
                {docs.map((d) => (
                  <li key={d.id}>
                    {d.kind} — {d.filename} ({d.status})
                  </li>
                ))}
              </ul>
              <form className="quick-form" onSubmit={(ev) => void uploadDoc(ev)}>
                <select name="kind" defaultValue="IDENTITY">
                  <option value="IDENTITY">Identidade</option>
                  <option value="ADDRESS">Comprovante de endereço</option>
                  <option value="INCOME">Renda</option>
                  <option value="PAYMENT_PROOF">Comprovante de pagamento</option>
                  <option value="CONTRACT">Contrato</option>
                  <option value="OTHER">Outro</option>
                </select>
                <input name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,.docx" required />
                <button type="submit" disabled={busy}>
                  Enviar documento
                </button>
              </form>
            </>
          )}
        </section>
      </div>
    </>
  );
}
