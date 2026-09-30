"use client";

import { RefreshCw, Wallet } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { CurrencyInput } from "@/components/currency-input";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type Summary = {
  mode: string;
  available_total: string;
  pending_fiscal_total: string;
  withdrawable: string;
  reserved_pending_withdrawal: string;
  min_withdrawal_amount: string;
};

type StatementRow = {
  id: string;
  kind: string;
  direction: string;
  amount: string;
  status: string | null;
  label: string;
  created_at: string | null;
};

export function PartnerLegacyBankModule() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [statement, setStatement] = useState<StatementRow[]>([]);
  const [pixKey, setPixKey] = useState("");
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, st] = await Promise.all([
        api<Summary>("/wallet/me/legacy-earnings"),
        api<StatementRow[]>("/wallet/me/legacy-statement?limit=80"),
      ]);
      setSummary(s);
      setStatement(st);
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "Falha ao carregar ganhos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onWithdraw(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setNotice("");
    try {
      await api("/wallet/me/legacy-withdrawals", {
        method: "POST",
        body: JSON.stringify({
          amount: withdrawAmount.replace(",", "."),
          pix_key: pixKey.trim(),
        }),
      });
      setNotice("Saque solicitado. A plataforma processará via PIX após conferência.");
      setWithdrawAmount("");
      await load();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Não foi possível solicitar o saque.");
    }
  }

  return (
    <section className="module-page">
      <header className="module-header">
        <Wallet />
        <div>
          <h1>Bank — Meus ganhos</h1>
          <p className="muted">Modo legado: comissões liberadas após NF e saque por PIX (sem conta Asaas).</p>
        </div>
        <button type="button" onClick={() => void load()} disabled={loading}>
          <RefreshCw /> Atualizar
        </button>
      </header>

      {notice && <p className="notice">{notice}</p>}

      {summary && (
        <div className="stat-grid">
          <div className="stat-card">
            <small>Disponível para saque</small>
            <strong>{brl.format(Number(summary.withdrawable))}</strong>
          </div>
          <div className="stat-card">
            <small>Comissões liberadas (AVAILABLE)</small>
            <strong>{brl.format(Number(summary.available_total))}</strong>
          </div>
          <div className="stat-card">
            <small>Aguardando NF / fiscal</small>
            <strong>{brl.format(Number(summary.pending_fiscal_total))}</strong>
          </div>
          <div className="stat-card">
            <small>Reservado (saque pendente)</small>
            <strong>{brl.format(Number(summary.reserved_pending_withdrawal))}</strong>
          </div>
        </div>
      )}

      <form className="panel stack" onSubmit={onWithdraw}>
        <h2 className="subheading">Solicitar saque</h2>
        <p className="muted">
          Mínimo: {summary ? brl.format(Number(summary.min_withdrawal_amount)) : "—"}. Informe a chave PIX de destino.
        </p>
        <label>
          Valor (R$)
          <CurrencyInput value={withdrawAmount} onChange={setWithdrawAmount} />
        </label>
        <label>
          Chave PIX
          <input value={pixKey} onChange={(e) => setPixKey(e.target.value)} placeholder="CPF, e-mail, telefone ou aleatória" />
        </label>
        <button type="submit" className="primary" disabled={loading}>
          Solicitar saque
        </button>
      </form>

      <section className="panel">
        <h2 className="subheading">Extrato</h2>
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
              {statement.length === 0 ? (
                <tr>
                  <td colSpan={4}>
                    <small className="muted">Nenhum lançamento ainda.</small>
                  </td>
                </tr>
              ) : (
                statement.map((row) => (
                  <tr key={`${row.kind}-${row.id}`}>
                    <td>{row.created_at ? new Date(row.created_at).toLocaleString("pt-BR") : "—"}</td>
                    <td>{row.label}</td>
                    <td>
                      {row.direction === "CREDIT" ? "+" : "-"}
                      {brl.format(Number(row.amount))}
                    </td>
                    <td>{row.status ?? "—"}</td>
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
