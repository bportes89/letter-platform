"use client";

import { CheckCircle2, RefreshCw, Truck } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { API_URL } from "@/lib/api";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type Transfer = {
  lead_id: string;
  proposal_id: string;
  name: string;
  situation: string;
  credit_value: string | null;
  entrada_value: string | null;
  quota_codes: string[];
  supplier_sources: string[];
  supplier_transfer_confirmed: boolean;
  paid_at: string | null;
};

type Me = { id: string; name: string; source_key: string; email: string | null };

function portalFetch<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  return fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
  }).then(async (res) => {
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : `Erro ${res.status}`;
      throw new Error(detail);
    }
    return data as T;
  });
}

export default function PortalFornecedorPage() {
  const initialToken = useMemo(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("token") || localStorage.getItem("supplier_portal_token") || "";
  }, []);
  const [token, setToken] = useState(initialToken);
  const [tokenInput, setTokenInput] = useState(initialToken);
  const [me, setMe] = useState<Me | null>(null);
  const [rows, setRows] = useState<Transfer[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (auth: string) => {
    const profile = await portalFetch<Me>("/supplier-portal/me", auth);
    const transfers = await portalFetch<Transfer[]>("/supplier-portal/transfers?status=pending", auth);
    setMe(profile);
    setRows(transfers);
  }, []);

  useEffect(() => {
    if (!token) return;
    localStorage.setItem("supplier_portal_token", token);
    load(token).catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar portal"));
  }, [token, load]);

  async function confirm(leadId: string) {
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      await portalFetch(`/supplier-portal/transfers/${leadId}/confirm`, token, { method: "POST" });
      setNotice("Transferência confirmada.");
      await load(token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao confirmar");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 960, margin: "2rem auto", padding: "0 1rem", fontFamily: "Georgia, serif" }}>
      <div style={{ display: "flex", gap: "1rem", alignItems: "center", marginBottom: "1.5rem" }}>
        <Truck />
        <div>
          <p style={{ margin: 0, letterSpacing: "0.08em", fontSize: "0.75rem" }}>LETTER · FORNECEDOR</p>
          <h1 style={{ margin: "0.25rem 0 0" }}>Portal de transferências</h1>
        </div>
      </div>

      {!me ? (
        <section style={{ borderTop: "1px solid #ccc", paddingTop: "1rem" }}>
          <p>Cole o token gerado no admin (Fornecedores) para ver vendas Pagou aguardando confirmação.</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setToken(tokenInput.trim());
            }}
            style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}
          >
            <input
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder="SUP-…"
              style={{ flex: 1, minWidth: 240, padding: "0.6rem" }}
            />
            <button type="submit">Entrar</button>
          </form>
        </section>
      ) : (
        <section>
          <div style={{ marginBottom: "1rem" }}>
            <strong>{me.name}</strong> · {me.source_key}
            <button
              type="button"
              style={{ marginLeft: "1rem" }}
              onClick={() => {
                localStorage.removeItem("supplier_portal_token");
                setMe(null);
                setToken("");
                setRows([]);
              }}
            >
              Sair
            </button>
            <button type="button" style={{ marginLeft: "0.5rem" }} onClick={() => load(token).catch(() => undefined)} disabled={busy}>
              <RefreshCw size={14} /> Atualizar
            </button>
          </div>
          {notice && (
            <p>
              <CheckCircle2 size={14} /> {notice}
            </p>
          )}
          {error && <p style={{ color: "#a00" }}>{error}</p>}
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th align="left">Cliente</th>
                <th align="left">Crédito</th>
                <th align="left">Entrada</th>
                <th align="left">Cotas</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.lead_id} style={{ borderTop: "1px solid #ddd" }}>
                  <td>{row.name}</td>
                  <td>{row.credit_value ? brl.format(Number(row.credit_value)) : "—"}</td>
                  <td>{row.entrada_value ? brl.format(Number(row.entrada_value)) : "—"}</td>
                  <td>{(row.quota_codes || []).join(", ") || "—"}</td>
                  <td>
                    <button type="button" disabled={busy} onClick={() => confirm(row.lead_id)}>
                      Confirmar transferência
                    </button>
                  </td>
                </tr>
              ))}
              {!rows.length && (
                <tr>
                  <td colSpan={5}>Nenhuma transferência pendente.</td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      )}
      {error && !me ? <p style={{ color: "#a00" }}>{error}</p> : null}
    </main>
  );
}
