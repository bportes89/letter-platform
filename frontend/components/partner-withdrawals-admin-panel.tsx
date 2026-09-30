"use client";

import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export type PartnerWithdrawalRow = {
  id: string;
  user_id: string;
  amount: string;
  status: string;
  pix_key: string;
  notes: string | null;
  created_at: string | null;
  processed_at: string | null;
  partner_name: string | null;
  partner_email: string | null;
};

type StatusFilter = "PENDING" | "ALL";

export function PartnerWithdrawalsAdminPanel({
  onNotice,
  onError,
}: {
  onNotice?: (msg: string) => void;
  onError?: (msg: string) => void;
}) {
  const [rows, setRows] = useState<PartnerWithdrawalRow[]>([]);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("PENDING");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const qs = statusFilter === "PENDING" ? "?status=PENDING&limit=80" : "?limit=80";
    setRows(await api<PartnerWithdrawalRow[]>(`/marketplace/partner-withdrawals${qs}`));
  }, [statusFilter]);

  useEffect(() => {
    load().catch((e) => onError?.(e instanceof Error ? e.message : "Falha ao carregar saques de parceiros"));
  }, [load, onError]);

  async function processWithdrawal(id: string, action: "PAID" | "CANCELLED") {
    setBusy(true);
    try {
      await api(`/marketplace/partner-withdrawals/${id}/process`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      onNotice?.(
        action === "PAID"
          ? "Saque de parceiro marcado como pago (comissões AVAILABLE consumidas)."
          : "Saque cancelado — saldo volta a ficar disponível para novo pedido.",
      );
      await load();
    } catch (e) {
      onError?.(e instanceof Error ? e.message : "Falha ao processar saque");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel operational-panel" style={{ marginTop: "1.25rem" }}>
      <div className="page-heading" style={{ marginBottom: "0.75rem" }}>
        <div>
          <span className="eyebrow dark">PEDIDOS</span>
          <h2 style={{ margin: 0, fontSize: "1.15rem" }}>Saques de parceiros / franquia</h2>
          <p style={{ margin: "0.35rem 0 0" }}>
            Bank legado — marcar pago após PIX manual ou cancelar o pedido.
          </p>
        </div>
        <div className="toolbar" style={{ gap: "0.5rem" }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            aria-label="Filtrar status"
          >
            <option value="PENDING">Pendentes</option>
            <option value="ALL">Todos (recentes)</option>
          </select>
          <button type="button" className="table-action" onClick={() => void load()} disabled={busy}>
            <RefreshCw /> Atualizar
          </button>
        </div>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Parceiro</th>
              <th>Valor</th>
              <th>Pix</th>
              <th>Status</th>
              <th>Quando</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((w) => (
              <tr key={w.id}>
                <td>
                  <b>{w.partner_name || "—"}</b>
                  <small>{w.partner_email || w.user_id.slice(0, 8)}</small>
                </td>
                <td>{brl.format(Number(w.amount))}</td>
                <td>
                  <code>{w.pix_key || "—"}</code>
                  {w.notes ? <small>{w.notes}</small> : null}
                </td>
                <td>
                  <span className={`pill pill-${w.status === "PENDING" ? "pending" : w.status === "PAID" ? "approved" : "rejected"}`}>
                    {w.status}
                  </span>
                </td>
                <td>{w.created_at ? new Date(w.created_at).toLocaleString("pt-BR") : "—"}</td>
                <td className="actions-cell">
                  {w.status === "PENDING" ? (
                    <>
                      <button
                        type="button"
                        className="table-action"
                        disabled={busy}
                        onClick={() => void processWithdrawal(w.id, "PAID")}
                      >
                        Pago
                      </button>
                      <button
                        type="button"
                        className="table-action"
                        disabled={busy}
                        onClick={() => void processWithdrawal(w.id, "CANCELLED")}
                      >
                        Cancelar
                      </button>
                    </>
                  ) : (
                    <small className="muted">—</small>
                  )}
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={6}>Nenhum saque {statusFilter === "PENDING" ? "pendente" : "registrado"}.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
