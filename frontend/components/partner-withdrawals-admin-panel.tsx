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
  status_label?: string | null;
  pix_key: string;
  notes: string | null;
  inter_codigo_solicitacao?: string | null;
  inter_end_to_end_id?: string | null;
  payment_error?: string | null;
  created_at: string | null;
  processed_at: string | null;
  partner_name: string | null;
  partner_email: string | null;
};

type StatusFilter = "OPEN" | "PENDING" | "ALL";

const RETRY_STATUSES = new Set(["PENDING", "PROCESSING", "FAILED", "AWAITING_BALANCE"]);

export function PartnerWithdrawalsAdminPanel({
  onNotice,
  onError,
}: {
  onNotice?: (msg: string) => void;
  onError?: (msg: string) => void;
}) {
  const [rows, setRows] = useState<PartnerWithdrawalRow[]>([]);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("OPEN");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const qs =
      statusFilter === "PENDING"
        ? "?status=PENDING&limit=80"
        : statusFilter === "OPEN"
          ? "?limit=80"
          : "?limit=80";
    const data = await api<PartnerWithdrawalRow[]>(`/marketplace/partner-withdrawals${qs}`);
    const open = new Set(["PENDING", "PROCESSING", "AWAITING_BALANCE", "FAILED"]);
    setRows(statusFilter === "OPEN" ? data.filter((r) => open.has(r.status)) : data);
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
          ? "Saque marcado como pago (manual — sem Inter)."
          : "Saque cancelado — saldo volta a ficar disponível.",
      );
      await load();
    } catch (e) {
      onError?.(e instanceof Error ? e.message : "Falha ao processar saque");
    } finally {
      setBusy(false);
    }
  }

  async function retryInter(id: string) {
    setBusy(true);
    try {
      await api(`/marketplace/partner-withdrawals/${id}/retry-inter-payout`, { method: "POST", body: "{}" });
      onNotice?.("PIX reenviado via Banco Inter.");
      await load();
    } catch (e) {
      onError?.(e instanceof Error ? e.message : "Falha ao reenviar PIX");
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
            Inter PIX automático no saque ou reenvio manual. Use &quot;Pago&quot; só se liquidou fora do Inter.
          </p>
        </div>
        <div className="toolbar" style={{ gap: "0.5rem" }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            aria-label="Filtrar status"
          >
            <option value="OPEN">Abertos (pendente / Inter)</option>
            <option value="PENDING">Somente PENDING</option>
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
              <th>Inter</th>
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
                  <span
                    className={`pill pill-${w.status === "PENDING" || w.status === "PROCESSING" ? "pending" : w.status === "PAID" ? "approved" : "rejected"}`}
                  >
                    {w.status_label || w.status}
                  </span>
                  {w.payment_error ? <small className="muted">{w.payment_error}</small> : null}
                </td>
                <td>
                  <small>
                    {w.inter_codigo_solicitacao ? `cod. ${w.inter_codigo_solicitacao.slice(0, 8)}…` : "—"}
                    {w.inter_end_to_end_id ? <br /> : null}
                    {w.inter_end_to_end_id ? `e2e ${w.inter_end_to_end_id.slice(0, 12)}…` : null}
                  </small>
                </td>
                <td>{w.created_at ? new Date(w.created_at).toLocaleString("pt-BR") : "—"}</td>
                <td className="actions-cell">
                  {RETRY_STATUSES.has(w.status) && (
                    <button type="button" className="table-action" disabled={busy} onClick={() => void retryInter(w.id)}>
                      Reenviar PIX
                    </button>
                  )}
                  {w.status === "PENDING" ? (
                    <>
                      <button
                        type="button"
                        className="table-action"
                        disabled={busy}
                        onClick={() => void processWithdrawal(w.id, "PAID")}
                      >
                        Pago manual
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
                  ) : w.status === "PAID" ? (
                    <small className="muted">Liquidado</small>
                  ) : (
                    <small className="muted">—</small>
                  )}
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={7}>Nenhum saque neste filtro.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
