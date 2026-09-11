"use client";

import Link from "next/link";
import { CheckCircle2, RefreshCw, Truck } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { API_URL } from "@/lib/api";
import { loginPublicSupplier } from "@/lib/public-site-api";

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

type Me = {
  id: string;
  name: string;
  source_key: string;
  email: string | null;
  balance_available?: string;
  pix_key?: string | null;
};

type LedgerRow = {
  id: string;
  kind: string;
  amount: string;
  reference: string;
  description: string;
  created_at: string | null;
};

type Withdrawal = {
  id: string;
  amount: string;
  status: string;
  pix_key: string;
  created_at: string | null;
};

type AdminOption = { id: string; name: string; code?: string | null };

type SupplierQuota = {
  id: string;
  group_code: string;
  quota_code: string;
  category: string;
  credit_value: string;
  premium_value: string;
  installment_value: string;
  installment_due_date: string | null;
  remaining_installments: number | null;
  status: string;
  administrator_name?: string | null;
};

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
  const [loginMode, setLoginMode] = useState<"password" | "token">("password");
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [tab, setTab] = useState<"vendas" | "cotas">("vendas");
  const [rows, setRows] = useState<Transfer[]>([]);
  const [quotas, setQuotas] = useState<SupplierQuota[]>([]);
  const [admins, setAdmins] = useState<AdminOption[]>([]);
  const [ledger, setLedger] = useState<LedgerRow[]>([]);
  const [withdrawals, setWithdrawals] = useState<Withdrawal[]>([]);
  const [saqueAmount, setSaqueAmount] = useState("");
  const [saquePix, setSaquePix] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (auth: string) => {
    const profile = await portalFetch<Me>("/supplier-portal/me", auth);
    const transfers = await portalFetch<Transfer[]>("/supplier-portal/transfers?status=pending", auth);
    const extrato = await portalFetch<LedgerRow[]>("/supplier-portal/ledger?limit=30", auth);
    const saques = await portalFetch<Withdrawal[]>("/supplier-portal/withdrawals?limit=20", auth);
    const quotaRows = await portalFetch<SupplierQuota[]>("/supplier-portal/quotas", auth);
    const adminRows = await portalFetch<AdminOption[]>("/supplier-portal/administrators", auth);
    setMe(profile);
    setRows(transfers);
    setLedger(extrato);
    setWithdrawals(saques);
    setQuotas(quotaRows);
    setAdmins(adminRows);
    setSaquePix(profile.pix_key || "");
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

  async function submitQuota(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!token) return;
    const form = e.currentTarget;
    const fd = new FormData(form);
    setBusy(true);
    setError("");
    try {
      await portalFetch("/supplier-portal/quotas", token, {
        method: "POST",
        body: JSON.stringify({
          administrator_id: fd.get("administrator_id"),
          group_code: fd.get("group_code"),
          quota_code: fd.get("quota_code"),
          category: fd.get("category"),
          credit_value: fd.get("credit_value"),
          premium_value: fd.get("premium_value") || "0",
          installment_value: fd.get("installment_value") || "0",
          installment_due_date: fd.get("installment_due_date"),
          remaining_installments: fd.get("remaining_installments") ? Number(fd.get("remaining_installments")) : null,
        }),
      });
      setNotice("Cota enviada para análise da LETTER.");
      form.reset();
      await load(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao cadastrar cota");
    } finally {
      setBusy(false);
    }
  }

  async function requestSaque(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      await portalFetch("/supplier-portal/withdrawals", token, {
        method: "POST",
        body: JSON.stringify({
          amount: saqueAmount,
          pix_key: saquePix || undefined,
        }),
      });
      setNotice("Saque solicitado — aguardando pagamento pela LETTER.");
      setSaqueAmount("");
      await load(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao solicitar saque");
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
          <h1 style={{ margin: "0.25rem 0 0" }}>Portal do fornecedor</h1>
        </div>
      </div>

      {!me ? (
        <section style={{ borderTop: "1px solid #ccc", paddingTop: "1rem" }}>
          <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem" }}>
            <button type="button" onClick={() => setLoginMode("password")} disabled={loginMode === "password"}>
              E-mail e senha
            </button>
            <button type="button" onClick={() => setLoginMode("token")} disabled={loginMode === "token"}>
              Token do admin
            </button>
          </div>

          {loginMode === "password" ? (
            <>
              <p>Entre com o e-mail e a senha cadastrados no auto-cadastro de fornecedor.</p>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setBusy(true);
                  setError("");
                  loginPublicSupplier({ email: loginEmail.trim(), password: loginPassword })
                    .then((result) => {
                      localStorage.setItem("supplier_portal_token", result.portal_token);
                      setToken(result.portal_token);
                      setTokenInput(result.portal_token);
                    })
                    .catch((err) => setError(err instanceof Error ? err.message : "Falha ao entrar"))
                    .finally(() => setBusy(false));
                }}
                style={{ display: "grid", gap: "0.75rem", maxWidth: 420 }}
              >
                <input
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  type="email"
                  placeholder="E-mail"
                  required
                  style={{ padding: "0.6rem" }}
                />
                <input
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  type="password"
                  placeholder="Senha"
                  required
                  minLength={8}
                  style={{ padding: "0.6rem" }}
                />
                <button type="submit" disabled={busy}>Entrar</button>
              </form>
              <p style={{ marginTop: "1rem" }}>
                <Link href="/cadastro-fornecedor">Criar conta de fornecedor →</Link>
              </p>
            </>
          ) : (
            <>
              <p>Cole o token gerado no admin (Fornecedores) para ver vendas, saldo e saques.</p>
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
            </>
          )}
        </section>
      ) : (
        <section>
          <div style={{ marginBottom: "1rem" }}>
            <strong>{me.name}</strong> · {me.source_key}
            <span style={{ marginLeft: "1rem" }}>
              Saldo disponível:{" "}
              <strong>{brl.format(Number(me.balance_available || 0))}</strong>
            </span>
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

          <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1.5rem" }}>
            <button type="button" onClick={() => setTab("vendas")} disabled={tab === "vendas"}>Vendas e saques</button>
            <button type="button" onClick={() => setTab("cotas")} disabled={tab === "cotas"}>Minhas cotas</button>
          </div>

          {tab === "cotas" ? (
            <>
              <h2>Cadastrar cota</h2>
              <p style={{ marginTop: 0 }}>Nova cota entra em <strong>análise</strong> até a LETTER aprovar para o estoque.</p>
              <form onSubmit={(ev) => void submitQuota(ev)} style={{ display: "grid", gap: "0.75rem", maxWidth: 520, marginBottom: "2rem" }}>
                <select name="administrator_id" required style={{ padding: "0.6rem" }}>
                  <option value="">Administradora</option>
                  {admins.map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
                <input name="group_code" placeholder="Grupo" required style={{ padding: "0.6rem" }} />
                <input name="quota_code" placeholder="Cota" required style={{ padding: "0.6rem" }} />
                <select name="category" required style={{ padding: "0.6rem" }}>
                  <option value="REAL_ESTATE">Imóvel</option>
                  <option value="VEHICLE">Veículo</option>
                </select>
                <input name="credit_value" placeholder="Crédito (R$)" required style={{ padding: "0.6rem" }} />
                <input name="premium_value" placeholder="Entrada (R$)" style={{ padding: "0.6rem" }} />
                <input name="installment_value" placeholder="Parcela (R$)" style={{ padding: "0.6rem" }} />
                <input name="installment_due_date" type="date" required style={{ padding: "0.6rem" }} />
                <input name="remaining_installments" type="number" min="0" placeholder="Parcelas restantes" style={{ padding: "0.6rem" }} />
                <button type="submit" disabled={busy}>Enviar para análise</button>
              </form>
              <h2>Suas cotas</h2>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th align="left">Cota</th>
                    <th align="left">Crédito</th>
                    <th align="left">Entrada</th>
                    <th align="left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {quotas.map((q) => (
                    <tr key={q.id} style={{ borderTop: "1px solid #ddd" }}>
                      <td>{q.group_code}/{q.quota_code}<br /><small>{q.administrator_name || ""}</small></td>
                      <td>{brl.format(Number(q.credit_value))}</td>
                      <td>{brl.format(Number(q.premium_value))}</td>
                      <td>{q.status === "PENDING_REVIEW" ? "Em análise" : q.status}</td>
                    </tr>
                  ))}
                  {!quotas.length && (
                    <tr><td colSpan={4}>Nenhuma cota cadastrada.</td></tr>
                  )}
                </tbody>
              </table>
            </>
          ) : (
          <>
          <h2>Transferências pendentes</h2>
          <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: "2rem" }}>
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

          <h2>Pedir saque</h2>
          <form onSubmit={(ev) => void requestSaque(ev)} style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1.5rem" }}>
            <input
              value={saqueAmount}
              onChange={(e) => setSaqueAmount(e.target.value)}
              placeholder="Valor"
              required
              style={{ padding: "0.6rem", width: 140 }}
            />
            <input
              value={saquePix}
              onChange={(e) => setSaquePix(e.target.value)}
              placeholder="Chave PIX"
              style={{ padding: "0.6rem", flex: 1, minWidth: 200 }}
            />
            <button type="submit" disabled={busy}>
              Solicitar
            </button>
          </form>

          <h2>Extrato</h2>
          <ul>
            {ledger.map((row) => (
              <li key={row.id}>
                {row.kind} · {brl.format(Number(row.amount))} · {row.description}{" "}
                <small>{row.created_at || ""}</small>
              </li>
            ))}
            {!ledger.length && <li>Sem lançamentos ainda.</li>}
          </ul>

          <h2>Saques</h2>
          <ul>
            {withdrawals.map((w) => (
              <li key={w.id}>
                {brl.format(Number(w.amount))} · {w.status} · PIX {w.pix_key}
              </li>
            ))}
            {!withdrawals.length && <li>Nenhum saque.</li>}
          </ul>
          </>
          )}
        </section>
      )}
      {error && !me ? <p style={{ color: "#a00" }}>{error}</p> : null}
    </main>
  );
}
