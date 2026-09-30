"use client";

import { CheckCircle2, RefreshCw, Wallet } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { CurrencyInput } from "@/components/currency-input";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type PendingWithdrawal = {
  id: string;
  amount: string;
  status: string;
  status_label?: string | null;
  pix_key: string;
  created_at: string | null;
};

type Summary = {
  mode: string;
  total_earned?: string;
  withdrawn_total?: string;
  available_total: string;
  pending_fiscal_total: string;
  pending_receipt_total?: string;
  held_commission_total?: string;
  withdrawable: string;
  reserved_pending_withdrawal: string;
  min_withdrawal_amount: string;
  can_withdraw?: boolean;
  withdrawal_blocked_reason?: string | null;
  pending_withdrawal?: PendingWithdrawal | null;
};

type StatementRow = {
  id: string;
  kind: string;
  direction: string;
  amount: string;
  status: string | null;
  status_label?: string | null;
  label: string;
  created_at: string | null;
};

type StatementFilter = "all" | "commission" | "withdrawal";

export function PartnerLegacyBankModule() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [statement, setStatement] = useState<StatementRow[]>([]);
  const [pixKey, setPixKey] = useState("");
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [successNotice, setSuccessNotice] = useState("");
  const [errorNotice, setErrorNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [statementFilter, setStatementFilter] = useState<StatementFilter>("all");
  const pixPrefilledRef = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErrorNotice("");
    try {
      const [s, st, profile, withdrawals] = await Promise.all([
        api<Summary>("/wallet/me/legacy-earnings"),
        api<StatementRow[]>("/wallet/me/legacy-statement?limit=80"),
        api<{ document?: string | null }>("/auth/me/profile").catch(() => null),
        api<PendingWithdrawal[]>("/wallet/me/legacy-withdrawals?limit=5").catch(() => []),
      ]);
      setSummary(s);
      setStatement(st);
      if (!pixPrefilledRef.current) {
        const lastPix = withdrawals.find((w) => w.pix_key)?.pix_key;
        const doc = profile?.document?.trim();
        if (lastPix) setPixKey(lastPix);
        else if (doc && doc.length >= 11) setPixKey(doc);
        pixPrefilledRef.current = true;
      }
    } catch (e) {
      setErrorNotice(e instanceof Error ? e.message : "Falha ao carregar ganhos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredStatement = useMemo(() => {
    if (statementFilter === "all") return statement;
    return statement.filter((row) => row.kind === statementFilter);
  }, [statement, statementFilter]);

  function fillMaxWithdraw() {
    if (!summary) return;
    setWithdrawAmount(String(summary.withdrawable).replace(".", ","));
  }

  async function onWithdraw(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSuccessNotice("");
    setErrorNotice("");
    try {
      await api("/wallet/me/legacy-withdrawals", {
        method: "POST",
        body: JSON.stringify({
          amount: withdrawAmount.replace(",", "."),
          pix_key: pixKey.trim(),
        }),
      });
      setSuccessNotice("Saque solicitado. Você receberá o PIX após a conferência da plataforma.");
      setWithdrawAmount("");
      await load();
    } catch (err) {
      setErrorNotice(err instanceof Error ? err.message : "Não foi possível solicitar o saque.");
    }
  }

  const hasPendingWithdrawal = Boolean(summary?.pending_withdrawal);

  return (
    <section className="module-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">BANK</span>
          <h1>Meus ganhos</h1>
          <p>
            Acompanhe comissões, extrato e solicite saque por PIX. Liberação após validação fiscal (NF-e) quando
            aplicável.
          </p>
        </div>
        <div className="operational-icon">
          <Wallet />
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
        <button type="button" onClick={() => void load()} disabled={loading}>
          <RefreshCw /> Atualizar
        </button>
      </div>

      {successNotice && (
        <div className="notice">
          <CheckCircle2 /> {successNotice}
        </div>
      )}
      {errorNotice && (
        <div className="notice" role="alert" style={{ borderColor: "#e8a0a0", background: "#fff5f5" }}>
          {errorNotice}
        </div>
      )}

      {summary && (
        <div className="stat-grid">
          <div className="stat-card">
            <small>Disponível para saque</small>
            <strong>{brl.format(Number(summary.withdrawable))}</strong>
          </div>
          <div className="stat-card">
            <small>Total acumulado (comissões)</small>
            <strong>{brl.format(Number(summary.total_earned || 0))}</strong>
          </div>
          <div className="stat-card">
            <small>Já sacado (pago)</small>
            <strong>{brl.format(Number(summary.withdrawn_total || 0))}</strong>
          </div>
          <div className="stat-card">
            <small>Liberadas (sem hold fiscal)</small>
            <strong>{brl.format(Number(summary.available_total))}</strong>
          </div>
          <div className="stat-card">
            <small>Aguardando NF-e (SEFAZ)</small>
            <strong>{brl.format(Number(summary.pending_fiscal_total))}</strong>
          </div>
          {Number(summary.pending_receipt_total || 0) > 0 && (
            <div className="stat-card">
              <small>Aguardando comprovante</small>
              <strong>{brl.format(Number(summary.pending_receipt_total))}</strong>
            </div>
          )}
          {Number(summary.reserved_pending_withdrawal) > 0 && (
            <div className="stat-card">
              <small>Reservado (saque em análise)</small>
              <strong>{brl.format(Number(summary.reserved_pending_withdrawal))}</strong>
            </div>
          )}
        </div>
      )}

      {summary?.pending_withdrawal && (
        <div className="panel stack" role="status">
          <h2 className="subheading">Saque em análise</h2>
          <p className="muted">
            {brl.format(Number(summary.pending_withdrawal.amount))} ·{" "}
            {summary.pending_withdrawal.status_label || "Em análise"} · PIX{" "}
            {summary.pending_withdrawal.pix_key}
            {summary.pending_withdrawal.created_at
              ? ` · ${new Date(summary.pending_withdrawal.created_at).toLocaleString("pt-BR")}`
              : ""}
          </p>
        </div>
      )}

      {summary?.withdrawal_blocked_reason && !hasPendingWithdrawal && (
        <div className="notice" role="status">
          {summary.withdrawal_blocked_reason}{" "}
          <Link href="/modules/mmn">Ir para Rede e comissões (liberação fiscal)</Link>
        </div>
      )}

      <form className="panel stack" onSubmit={onWithdraw}>
        <h2 className="subheading">Solicitar saque</h2>
        <p className="muted">
          Mínimo: {summary ? brl.format(Number(summary.min_withdrawal_amount)) : "—"}. Use a chave PIX de destino
          (CPF/CNPJ, e-mail, telefone ou aleatória).
        </p>
        <label>
          Valor (R$)
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <CurrencyInput value={withdrawAmount} onChange={setWithdrawAmount} />
            <button type="button" onClick={fillMaxWithdraw} disabled={!summary || Number(summary.withdrawable) <= 0}>
              Sacar tudo
            </button>
          </div>
        </label>
        <label>
          Chave PIX
          <input
            value={pixKey}
            onChange={(e) => setPixKey(e.target.value)}
            placeholder="CPF, e-mail, telefone ou aleatória"
            autoComplete="off"
          />
        </label>
        <button
          type="submit"
          className="primary"
          disabled={loading || summary?.can_withdraw === false || hasPendingWithdrawal}
        >
          {hasPendingWithdrawal ? "Aguardando saque em análise" : "Solicitar saque"}
        </button>
      </form>

      <section className="panel">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", marginBottom: 12 }}>
          <h2 className="subheading" style={{ margin: 0, flex: "1 1 auto" }}>Extrato</h2>
          <select
            value={statementFilter}
            onChange={(e) => setStatementFilter(e.target.value as StatementFilter)}
            aria-label="Filtrar extrato"
          >
            <option value="all">Todos</option>
            <option value="commission">Comissões</option>
            <option value="withdrawal">Saques</option>
          </select>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Data</th>
                <th>Descrição</th>
                <th>Valor</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredStatement.length === 0 ? (
                <tr>
                  <td colSpan={4}>
                    <small className="muted">Nenhum lançamento ainda.</small>
                  </td>
                </tr>
              ) : (
                filteredStatement.map((row) => (
                  <tr key={`${row.kind}-${row.id}`}>
                    <td>{row.created_at ? new Date(row.created_at).toLocaleString("pt-BR") : "—"}</td>
                    <td>{row.label}</td>
                    <td>
                      {row.direction === "CREDIT" ? "+" : "−"}
                      {brl.format(Number(row.amount))}
                    </td>
                    <td>{row.status_label || row.status || "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
