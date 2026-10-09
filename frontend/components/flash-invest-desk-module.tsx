"use client";

import { CheckCircle2, ClipboardList, Landmark, RefreshCw, WalletCards } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  FundingOpportunity,
  InvestmentPosition,
  InvestmentReservation,
  MutuoContract,
  User,
} from "@/lib/api";
import { isInternalProductRole } from "@/lib/product-nav";
import { FundingModule } from "@/components/network-funding-modules";
import { FundOperationFlow, FundOperationFlowPanel } from "@/components/fund-operation-flow-panel";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type FundOfficeOperationRow = {
  id: string;
  contact_name: string;
  document: string | null;
  status: string;
  principal: string;
  asset_value: string;
  created_at: string | null;
  current_step_code: string | null;
  current_step_title: string | null;
  current_step_status: string | null;
};

type FundOfficeOperationDetail = {
  id: string;
  contact_name: string;
  document: string | null;
  status: string;
  status_label: string;
  principal: string;
  asset_value: string;
  term_months: number;
  interest_rate_monthly: string;
  net_payout: string;
  fund_operation_flow?: FundOperationFlow | null;
};

type CheckoutResult = {
  reservation: InvestmentReservation;
  mode: string;
  message: string;
};

export function FlashInvestDeskModule() {
  const [tab, setTab] = useState<"oportunidades" | "aportes" | "mutuo" | "cadastros">("oportunidades");
  const [user, setUser] = useState<User | null>(null);
  const [opps, setOpps] = useState<FundingOpportunity[]>([]);
  const [reservations, setReservations] = useState<InvestmentReservation[]>([]);
  const [positions, setPositions] = useState<InvestmentPosition[]>([]);
  const [mutuos, setMutuos] = useState<MutuoContract[]>([]);
  const [amountByOpp, setAmountByOpp] = useState<Record<string, string>>({});
  const [mutuoPrincipal, setMutuoPrincipal] = useState("10000");
  const [mutuoOption, setMutuoOption] = useState<"A" | "B">("A");
  const [checkout, setCheckout] = useState<CheckoutResult | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [fundOps, setFundOps] = useState<FundOfficeOperationRow[]>([]);
  const [selectedFundOpId, setSelectedFundOpId] = useState<string | null>(null);
  const [fundOpDetail, setFundOpDetail] = useState<FundOfficeOperationDetail | null>(null);

  const isInternal = isInternalProductRole(user?.role);
  const isInvestor = user?.role === "RETAIL_INVESTOR" || user?.role === "INSTITUTIONAL_FUND";
  const isFundOffice = user?.role === "INSTITUTIONAL_FUND";

  const load = useCallback(async () => {
    const me = await api<User>("/auth/me");
    setUser(me);
    const [o, r, p, m] = await Promise.all([
      api<FundingOpportunity[]>("/funding/opportunities"),
      api<InvestmentReservation[]>("/funding/reservations"),
      api<InvestmentPosition[]>("/funding/positions"),
      api<MutuoContract[]>("/funding/mutuo/contracts"),
    ]);
    setOpps(o);
    setReservations(r);
    setPositions(p);
    setMutuos(m);
  }, []);

  useEffect(() => {
    setLoading(true);
    load()
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar Flash Invest"))
      .finally(() => setLoading(false));
  }, [load]);

  const openOpps = useMemo(() => opps.filter((o) => o.status === "OPEN"), [opps]);
  const pendingReservations = useMemo(
    () => reservations.filter((r) => r.status === "RESERVED"),
    [reservations],
  );

  async function reserve(opp: FundingOpportunity) {
    setError("");
    setBusy(true);
    try {
      const amount = (amountByOpp[opp.id] || String(opp.min_investment || "100")).replace(/\./g, "").replace(",", ".");
      const reservation = await api<InvestmentReservation>(`/funding/opportunities/${opp.id}/reserve`, {
        method: "POST",
        body: JSON.stringify({ amount }),
      });
      const pay = await api<CheckoutResult>(`/funding/reservations/${reservation.id}/checkout`, {
        method: "POST",
      });
      setCheckout(pay);
      setNotice(pay.message);
      setTab("aportes");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha na reserva");
    } finally {
      setBusy(false);
    }
  }

  async function checkoutExisting(id: string) {
    setError("");
    setBusy(true);
    try {
      const pay = await api<CheckoutResult>(`/funding/reservations/${id}/checkout`, { method: "POST" });
      setCheckout(pay);
      setNotice(pay.message);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no checkout");
    } finally {
      setBusy(false);
    }
  }

  async function sandboxPay(id: string) {
    setError("");
    setBusy(true);
    try {
      const position = await api<InvestmentPosition>(`/funding/reservations/${id}/sandbox-pay`, {
        method: "POST",
      });
      setNotice(`Aporte confirmado — posição ${brl.format(Number(position.principal))}`);
      setCheckout(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao confirmar sandbox");
    } finally {
      setBusy(false);
    }
  }

  async function adminConfirm(id: string) {
    setError("");
    setBusy(true);
    try {
      await api(`/funding/reservations/${id}/mock-confirm`, { method: "POST" });
      setNotice("Aporte confirmado pela operação");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao confirmar");
    } finally {
      setBusy(false);
    }
  }

  async function createMutuo() {
    setError("");
    setBusy(true);
    try {
      const contract = await api<MutuoContract>("/funding/mutuo/contracts", {
        method: "POST",
        body: JSON.stringify({
          principal: mutuoPrincipal.replace(/\./g, "").replace(",", "."),
          settlement_option: mutuoOption,
        }),
      });
      setNotice(`Mútuo ${contract.id.slice(0, 8)} criado (${mutuoOption})`);
      setTab("mutuo");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao criar mútuo");
    } finally {
      setBusy(false);
    }
  }

  async function acceptSign(id: string) {
    setBusy(true);
    try {
      await api(`/funding/mutuo/contracts/${id}/accept-sign`, { method: "POST" });
      await api(`/funding/mutuo/contracts/${id}/mock-complete-signature`, { method: "POST" });
      setNotice("Assinatura concluída (sandbox ZapSign)");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha na assinatura");
    } finally {
      setBusy(false);
    }
  }

  async function settle(id: string) {
    setBusy(true);
    try {
      await api(`/funding/mutuo/contracts/${id}/settle`, { method: "POST" });
      setNotice("Mútuo liquidado / ACTIVE");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao liquidar");
    } finally {
      setBusy(false);
    }
  }

  async function postInterest(id: string) {
    setBusy(true);
    try {
      await api(`/funding/mutuo/contracts/${id}/post-interest`, { method: "POST" });
      setNotice("Juros do mês lançados");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha nos juros");
    } finally {
      setBusy(false);
    }
  }

  const loadFundOfficeOps = useCallback(async () => {
    const rows = await api<FundOfficeOperationRow[]>("/funding/fund-office/operations");
    setFundOps(rows);
    if (selectedFundOpId && !rows.some((r) => r.id === selectedFundOpId)) {
      setSelectedFundOpId(null);
      setFundOpDetail(null);
    }
  }, [selectedFundOpId]);

  async function openFundOfficeOp(id: string) {
    setError("");
    setBusy(true);
    try {
      const detail = await api<FundOfficeOperationDetail>(`/funding/fund-office/operations/${id}`);
      setSelectedFundOpId(id);
      setFundOpDetail(detail);
      setTab("cadastros");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao abrir cadastro");
    } finally {
      setBusy(false);
    }
  }

  async function completeFundFlowStep(stepCode: string) {
    if (!fundOpDetail) return;
    setError("");
    setBusy(true);
    try {
      const res = await api<{ fund_operation_flow: FundOperationFlow }>(
        `/flash/desk/solicitations/${fundOpDetail.id}/fund-operation-flow`,
        {
          method: "PATCH",
          body: JSON.stringify({ step_code: stepCode, status: "COMPLETED", advance_next: true }),
        },
      );
      setFundOpDetail({ ...fundOpDetail, fund_operation_flow: res.fund_operation_flow });
      setNotice("Etapa concluída — próximo passo em andamento.");
      await loadFundOfficeOps();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao atualizar etapa");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!isFundOffice) return;
    loadFundOfficeOps().catch((e) => setError(e instanceof Error ? e.message : "Falha ao listar operações"));
  }, [isFundOffice, loadFundOfficeOps]);

  async function requestRedeem(id: string) {
    setBusy(true);
    try {
      await api(`/funding/mutuo/contracts/${id}/request-redemption`, { method: "POST" });
      setNotice("Resgate solicitado");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no resgate");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="loading">Carregando Flash Invest…</div>;

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">INVESTIMENTOS · LETTER BANK</span>
          <h1>Flash Invest</h1>
          <p>
            Captação por token (≥ R$ 100) e mútuo (≥ R$ 10.000). Reserve → checkout Pix → posição.
            Juros do mútuo ACTIVE rodam via cron mensal.
          </p>
        </div>
        <div className="operational-icon"><Landmark /></div>
      </div>

      <section className="panel operational-panel">
        <div className="notice" style={{ margin: "0 18px 12px" }}>
          <WalletCards />
          <b>Painel operacional</b> —{" "}
          <button type="button" className="table-action" style={{ display: "inline" }} onClick={() => setTab("oportunidades")}>
            Oportunidades ({openOpps.length})
          </button>
          ·{" "}
          <button type="button" className="table-action" style={{ display: "inline" }} onClick={() => setTab("aportes")}>
            Reservas ({pendingReservations.length}/{reservations.length})
          </button>
          ·{" "}
          <button type="button" className="table-action" style={{ display: "inline" }} onClick={() => setTab("aportes")}>
            Posições ({positions.length})
          </button>
          <small style={{ display: "block", marginTop: 6 }}>
            APIs: /funding/opportunities · /funding/reservations · /funding/positions
          </small>
        </div>
        <div
          className="marketplace-tabs"
          style={{ gridTemplateColumns: isFundOffice ? "1fr 1fr 1fr 1.2fr" : "1fr 1fr 1fr" }}
        >
          <button type="button" className={`marketplace-tab${tab === "oportunidades" ? " active" : ""}`} onClick={() => setTab("oportunidades")}>
            Oportunidades
          </button>
          <button type="button" className={`marketplace-tab${tab === "aportes" ? " active" : ""}`} onClick={() => setTab("aportes")}>
            Meus aportes
          </button>
          <button type="button" className={`marketplace-tab${tab === "mutuo" ? " active" : ""}`} onClick={() => setTab("mutuo")}>
            Mútuo
          </button>
          {isFundOffice ? (
            <button
              type="button"
              className={`marketplace-tab${tab === "cadastros" ? " active" : ""}`}
              onClick={() => {
                setTab("cadastros");
                void loadFundOfficeOps().catch((e) => setError(e instanceof Error ? e.message : "Falha ao listar"));
              }}
            >
              Cadastros / operações
            </button>
          ) : null}
        </div>

        <div style={{ padding: "14px 18px", display: "flex", gap: 10 }}>
          <button type="button" className="table-action" onClick={() => void load().catch((e) => setError(e.message))}>
            <RefreshCw />Atualizar
          </button>
        </div>

        {notice && <div className="notice" style={{ margin: "0 18px 12px" }}><CheckCircle2 />{notice}</div>}
        {error && <div className="error" style={{ margin: "0 18px 12px" }}>{error}</div>}

        {checkout && (
          <div className="notice" style={{ margin: "0 18px 12px", display: "grid", gap: 8 }}>
            <b>Checkout Pix ({checkout.mode})</b>
            <small>{checkout.message}</small>
            {checkout.reservation.pix_copy_paste && (
              <code style={{ fontSize: 11, wordBreak: "break-all" }}>{checkout.reservation.pix_copy_paste}</code>
            )}
            {checkout.reservation.checkout_url && checkout.mode === "ASAAS" && (
              <a href={checkout.reservation.checkout_url} target="_blank" rel="noreferrer">Abrir fatura Asaas</a>
            )}
            {checkout.mode === "SANDBOX" && checkout.reservation.status === "RESERVED" && (
              <button type="button" className="admin-button" disabled={busy} onClick={() => void sandboxPay(checkout.reservation.id)}>
                Confirmar pagamento sandbox
              </button>
            )}
          </div>
        )}

        {tab === "oportunidades" && (
          <div style={{ padding: "0 18px 18px", overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Título</th>
                  <th>Instrumento</th>
                  <th>Meta / mínimo</th>
                  <th>Status</th>
                  <th>Aporte</th>
                </tr>
              </thead>
              <tbody>
                {openOpps.map((opp) => (
                  <tr key={opp.id}>
                    <td>
                      <b>{opp.title}</b>
                      <div className="muted" style={{ fontSize: 11 }}>{opp.property_ref || "Imóvel a vincular"}</div>
                    </td>
                    <td>{opp.instrument_type || "TOKEN"}</td>
                    <td>
                      {brl.format(Number(opp.target_amount))}
                      <div className="muted" style={{ fontSize: 11 }}>mín. {brl.format(Number(opp.min_investment || 100))}</div>
                    </td>
                    <td>{opp.status}</td>
                    <td style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      {isInvestor && (
                        <>
                          <input
                            style={{ width: 100, padding: 6, borderRadius: 8, border: "1px solid var(--line)" }}
                            placeholder="R$"
                            value={amountByOpp[opp.id] || ""}
                            onChange={(e) => setAmountByOpp((prev) => ({ ...prev, [opp.id]: e.target.value }))}
                          />
                          <button type="button" className="table-action" disabled={busy} onClick={() => void reserve(opp)}>
                            Reservar + Pix
                          </button>
                        </>
                      )}
                      {!isInvestor && <span className="muted">Login investidor para aportar</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!openOpps.length && <p className="muted">Nenhuma oportunidade OPEN. Ops publica em FinOps avançado abaixo.</p>}
          </div>
        )}

        {tab === "aportes" && (
          <div style={{ padding: "0 18px 18px" }}>
            <h3 style={{ fontSize: 14 }}>Reservas pendentes</h3>
            <table className="data-table">
              <thead>
                <tr><th>Valor</th><th>Status</th><th>Checkout</th><th>Ações</th></tr>
              </thead>
              <tbody>
                {pendingReservations.map((r) => (
                  <tr key={r.id}>
                    <td>{brl.format(Number(r.amount))}</td>
                    <td>{r.status}</td>
                    <td>{r.checkout_mode || "—"} / {r.checkout_status || "—"}</td>
                    <td style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <button type="button" className="table-action" disabled={busy} onClick={() => void checkoutExisting(r.id)}>Pix</button>
                      {(isInvestor || isInternal) && (
                        <button type="button" className="table-action" disabled={busy} onClick={() => void sandboxPay(r.id)}>Sandbox pay</button>
                      )}
                      {isInternal && (
                        <button type="button" className="table-action" disabled={busy} onClick={() => void adminConfirm(r.id)}>Admin confirm</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h3 style={{ fontSize: 14, marginTop: 16 }}>Posições</h3>
            <table className="data-table">
              <thead>
                <tr><th>Principal</th><th>Tokens</th><th>Rentab.</th><th>Fonte</th><th>Status</th></tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr key={p.id}>
                    <td>{brl.format(Number(p.principal))}</td>
                    <td>{p.tokens_qty ?? "—"}</td>
                    <td>{brl.format(Number(p.accrued_return || 0))}</td>
                    <td>{p.source}</td>
                    <td>{p.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab === "mutuo" && (
          <div style={{ padding: "0 18px 18px" }} className="stack-form">
            {isInvestor && (
              <div style={{ display: "grid", gap: 9, gridTemplateColumns: "1fr 1fr auto", maxWidth: 560 }}>
                <input value={mutuoPrincipal} onChange={(e) => setMutuoPrincipal(e.target.value)} placeholder="Principal (≥ 10000)" />
                <select value={mutuoOption} onChange={(e) => setMutuoOption(e.target.value as "A" | "B")}>
                  <option value="A">Opção A — juros mensais</option>
                  <option value="B">Opção B — bullet</option>
                </select>
                <button type="button" className="admin-button" disabled={busy} onClick={() => void createMutuo()}>
                  Criar mútuo
                </button>
              </div>
            )}
            <table className="data-table" style={{ marginTop: 12 }}>
              <thead>
                <tr><th>Principal</th><th>Opção</th><th>Status</th><th>Juros</th><th>Ações</th></tr>
              </thead>
              <tbody>
                {mutuos.map((c) => (
                  <tr key={c.id}>
                    <td>{brl.format(Number(c.principal))}</td>
                    <td>{c.settlement_option}</td>
                    <td>{c.status}</td>
                    <td>
                      A: {brl.format(Number(c.paid_interest_total || 0))} · B: {brl.format(Number(c.accrued_interest || 0))}
                      <div className="muted" style={{ fontSize: 11 }}>{c.interest_months_posted || 0}/36 meses</div>
                    </td>
                    <td style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {isInvestor && ["DRAFT", "AWAITING_SIGNATURE"].includes(c.status) && (
                        <button type="button" className="table-action" disabled={busy} onClick={() => void acceptSign(c.id)}>Assinar</button>
                      )}
                      {isInternal && c.status === "SIGNED" && (
                        <button type="button" className="table-action" disabled={busy} onClick={() => void settle(c.id)}>Liquidar</button>
                      )}
                      {isInternal && c.status === "ACTIVE" && (
                        <button type="button" className="table-action" disabled={busy} onClick={() => void postInterest(c.id)}>Juros mês</button>
                      )}
                      {isInvestor && c.status === "ACTIVE" && (
                        <button type="button" className="table-action" disabled={busy} onClick={() => void requestRedeem(c.id)}>Resgatar</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted" style={{ fontSize: 12 }}>
              Cron: <code>POST /api/v1/system/cron/flash-invest-mutuo-interest</code> lança juros de todos ACTIVE (idempotente por mês).
            </p>
          </div>
        )}

        {tab === "cadastros" && isFundOffice && (
          <div style={{ padding: "0 18px 18px" }}>
            <div className="notice" style={{ marginBottom: 12, display: "flex", gap: 8, alignItems: "center" }}>
              <ClipboardList size={18} />
              <span>
                Acompanhamento das propostas Flash com capital <b>institucional</b>. O fluxo inicia em <b>Term Sheet</b> (sem etapa Carta Paulo Letter).
              </span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cliente</th>
                  <th>Principal</th>
                  <th>Status Flash</th>
                  <th>Etapa atual</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {fundOps.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="muted">Nenhuma operação institucional cadastrada.</td>
                  </tr>
                ) : (
                  fundOps.map((row) => (
                    <tr key={row.id} style={{ background: selectedFundOpId === row.id ? "#f8fafc" : undefined }}>
                      <td>
                        <b>{row.contact_name}</b>
                        {row.document ? <div className="muted" style={{ fontSize: 11 }}>{row.document}</div> : null}
                      </td>
                      <td>{brl.format(Number(row.principal))}</td>
                      <td>{row.status}</td>
                      <td>
                        {row.current_step_title || "—"}
                        <div className="muted" style={{ fontSize: 10 }}>{row.current_step_status}</div>
                      </td>
                      <td>
                        <button type="button" className="table-action" disabled={busy} onClick={() => void openFundOfficeOp(row.id)}>
                          Abrir cadastro
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            {fundOpDetail ? (
              <div style={{ marginTop: 16 }}>
                <div className="notice" style={{ marginBottom: 10 }}>
                  <b>{fundOpDetail.contact_name}</b>
                  <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                    {fundOpDetail.status_label} · {brl.format(Number(fundOpDetail.principal))} · {fundOpDetail.term_months}m @{" "}
                    {fundOpDetail.interest_rate_monthly}%
                  </div>
                </div>
                <FundOperationFlowPanel
                  flow={fundOpDetail.fund_operation_flow}
                  canEdit
                  busy={busy}
                  onMarkCompleted={(code) => void completeFundFlowStep(code)}
                />
              </div>
            ) : null}
          </div>
        )}
      </section>

      {isInternal ? (
        <section className="panel operational-panel" style={{ marginTop: 16 }}>
          <div className="page-heading" style={{ marginBottom: 8 }}>
            <div>
              <span className="eyebrow dark">INTERNO</span>
              <h2 style={{ fontSize: 18, margin: "6px 0" }}>Ops avançado (publicar / manual)</h2>
            </div>
            <div className="operational-icon"><WalletCards /></div>
          </div>
          <FundingModule />
        </section>
      ) : null}
    </>
  );
}
