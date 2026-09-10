"use client";

import { CheckCircle2, Download, RefreshCw, SlidersHorizontal, Upload, WalletCards } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, apiForm, downloadApi } from "@/lib/api";

type QuotaOfferRange = {
  id: string;
  active: boolean;
  name: string;
  sort_order: number;
  tipo: string;
  prazo_init: number;
  prazo_final: number;
  pago_init: string;
  pago_final: string;
  porc: string;
};

type QuotaSellOffer = {
  id: string;
  status: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  document: string | null;
  person_type: string;
  tipo_consorcio: string;
  tipo_label: string;
  administrator_id: string | null;
  administrator_name: string | null;
  credit_value: string;
  paid_value: string;
  outstanding_balance: string;
  term_months: number;
  contemplated: boolean;
  paid_percent: string;
  offer_percent: string;
  offer_value: string;
  partner_referral_code: string | null;
  notes: string | null;
  statement_document_id: string | null;
  statement_filename: string | null;
  created_at: string | null;
};

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const STATUS_OPTIONS = [
  { value: "AWAITING_STATEMENT", label: "Aguardando extrato" },
  { value: "UNDER_REVIEW", label: "Em análise" },
  { value: "ACCEPTED", label: "Aceita" },
  { value: "REJECTED", label: "Recusada" },
  { value: "CLOSED", label: "Fechada" },
] as const;

const STATUS_LABEL: Record<string, string> = Object.fromEntries(STATUS_OPTIONS.map((s) => [s.value, s.label]));

export function VenderCotaAdminModule() {
  const [tab, setTab] = useState<"offers" | "ranges">("offers");
  const [offers, setOffers] = useState<QuotaSellOffer[]>([]);
  const [ranges, setRanges] = useState<QuotaOfferRange[]>([]);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Partial<QuotaOfferRange>>>({});
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const load = useCallback(async () => {
    const [o, r] = await Promise.all([
      api<QuotaSellOffer[]>("/funding/vender-cota/offers"),
      api<QuotaOfferRange[]>("/funding/vender-cota/ranges"),
    ]);
    setOffers(o);
    setRanges(r);
    setDrafts({});
  }, []);

  useEffect(() => {
    setLoading(true);
    load()
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar"))
      .finally(() => setLoading(false));
  }, [load]);

  const filteredOffers = useMemo(
    () => (statusFilter === "ALL" ? offers : offers.filter((o) => o.status === statusFilter)),
    [offers, statusFilter],
  );

  async function updateOfferStatus(offer: QuotaSellOffer, status: string) {
    setError("");
    setSavingId(offer.id);
    try {
      await api(`/funding/vender-cota/offers/${offer.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setNotice(`Oferta de ${offer.contact_name}: ${STATUS_LABEL[status] ?? status}.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao atualizar oferta");
    } finally {
      setSavingId(null);
    }
  }

  async function uploadStatement(offer: QuotaSellOffer, file: File) {
    setError("");
    setSavingId(offer.id);
    try {
      const body = new FormData();
      body.append("file", file);
      await apiForm(`/funding/vender-cota/offers/${offer.id}/statement`, body);
      setNotice(`Extrato anexado em ${offer.contact_name}.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no upload do extrato");
    } finally {
      setSavingId(null);
    }
  }

  async function downloadStatement(offer: QuotaSellOffer) {
    try {
      await downloadApi(
        `/funding/vender-cota/offers/${offer.id}/statement`,
        offer.statement_filename || `extrato-${offer.id}.pdf`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao baixar extrato");
    }
  }

  function draftFor(range: QuotaOfferRange): QuotaOfferRange {
    return { ...range, ...(drafts[range.id] || {}) } as QuotaOfferRange;
  }

  function patchDraft(id: string, patch: Partial<QuotaOfferRange>) {
    setDrafts((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));
  }

  async function saveRange(range: QuotaOfferRange) {
    const d = draftFor(range);
    setError("");
    setSavingId(range.id);
    try {
      await api(`/funding/vender-cota/ranges/${range.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          active: d.active,
          name: d.name,
          porc: d.porc,
          pago_init: d.pago_init,
          pago_final: d.pago_final,
          prazo_init: Number(d.prazo_init),
          prazo_final: Number(d.prazo_final),
          sort_order: Number(d.sort_order),
        }),
      });
      setNotice(`Faixa “${d.name}” atualizada.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar faixa");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">OPERAÇÃO ATIVA</span>
          <h1>Vender minha cota</h1>
          <p>Ofertas públicas do site e tabela editável do robô (tipo × prazo × % pago → % que a Letter paga).</p>
        </div>
        <div className="operational-icon"><WalletCards /></div>
      </div>

      <section className="panel operational-panel">
        <div className="marketplace-tabs" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <button type="button" className={`marketplace-tab${tab === "offers" ? " active" : ""}`} onClick={() => setTab("offers")}>
            Ofertas recebidas
          </button>
          <button type="button" className={`marketplace-tab${tab === "ranges" ? " active" : ""}`} onClick={() => setTab("ranges")}>
            <SlidersHorizontal style={{ width: 14, height: 14, marginRight: 6 }} />
            Faixas do robô
          </button>
        </div>

        <div style={{ padding: "14px 18px", display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <button type="button" className="table-action" onClick={() => void load().catch((e) => setError(e.message))}>
            <RefreshCw />Atualizar
          </button>
          {tab === "offers" && (
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, fontWeight: 700, color: "#52605a" }}>
              Status
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid var(--line)" }}>
                <option value="ALL">Todas</option>
                {STATUS_OPTIONS.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </label>
          )}
        </div>

        {notice && <div className="notice" style={{ margin: "0 18px 12px" }}><CheckCircle2 />{notice}</div>}
        {error && <div className="error" style={{ margin: "0 18px 12px" }}>{error}</div>}
        {loading && <div className="loading" style={{ padding: 24 }}>Carregando…</div>}

        {!loading && tab === "offers" && (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cliente</th>
                  <th>Cota</th>
                  <th>Oferta Letter</th>
                  <th>Extrato</th>
                  <th>Parceiro</th>
                  <th>Status</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {filteredOffers.length === 0 && (
                  <tr><td colSpan={7} style={{ padding: 24, color: "var(--muted)" }}>Nenhuma oferta neste filtro.</td></tr>
                )}
                {filteredOffers.map((o) => (
                  <tr key={o.id}>
                    <td>
                      <b>{o.contact_name}</b>
                      <small>{o.contact_email} · {o.contact_phone}</small>
                      {o.document ? <small>Doc. {o.document}</small> : null}
                    </td>
                    <td>
                      <b>{o.tipo_label || o.tipo_consorcio}</b>
                      <small>{o.administrator_name || "Sem administradora"} · {o.term_months} meses</small>
                      <small>Crédito {brl.format(Number(o.credit_value))} · pago {o.paid_percent}%</small>
                    </td>
                    <td>
                      <b>{brl.format(Number(o.offer_value))}</b>
                      <small>{o.offer_percent}% do crédito</small>
                      <small>{o.created_at ? new Date(o.created_at).toLocaleString("pt-BR") : "—"}</small>
                    </td>
                    <td>
                      {o.statement_document_id ? (
                        <button type="button" className="table-action" onClick={() => void downloadStatement(o)}>
                          <Download />{o.statement_filename || "Baixar"}
                        </button>
                      ) : (
                        <>
                          <input
                            ref={(el) => { fileRefs.current[o.id] = el; }}
                            type="file"
                            accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                            style={{ display: "none" }}
                            onChange={(e) => {
                              const f = e.target.files?.[0];
                              if (f) void uploadStatement(o, f);
                              e.target.value = "";
                            }}
                          />
                          <button
                            type="button"
                            className="table-action"
                            disabled={savingId === o.id}
                            onClick={() => fileRefs.current[o.id]?.click()}
                          >
                            <Upload />Anexar
                          </button>
                        </>
                      )}
                    </td>
                    <td><small>{o.partner_referral_code || "—"}</small></td>
                    <td><span className={`pill pill-${o.status.toLowerCase()}`}>{STATUS_LABEL[o.status] ?? o.status}</span></td>
                    <td className="actions-cell">
                      <select
                        value={o.status}
                        disabled={savingId === o.id}
                        onChange={(e) => void updateOfferStatus(o, e.target.value)}
                        style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid var(--line)", fontSize: 11 }}
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s.value} value={s.value}>{s.label}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && tab === "ranges" && (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ativa</th>
                  <th>Nome</th>
                  <th>Tipo</th>
                  <th>Prazo (meses)</th>
                  <th>% pago</th>
                  <th>% Letter paga</th>
                  <th>Ordem</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {ranges.map((r) => {
                  const d = draftFor(r);
                  const dirty = Boolean(drafts[r.id]);
                  return (
                    <tr key={r.id} style={{ opacity: d.active ? 1 : 0.55 }}>
                      <td>
                        <input
                          type="checkbox"
                          checked={Boolean(d.active)}
                          onChange={(e) => patchDraft(r.id, { active: e.target.checked })}
                        />
                      </td>
                      <td>
                        <input
                          value={d.name}
                          onChange={(e) => patchDraft(r.id, { name: e.target.value })}
                          style={{ width: "100%", minWidth: 160, padding: 8, borderRadius: 6, border: "1px solid var(--line)" }}
                        />
                      </td>
                      <td><small>{d.tipo === "imovel" ? "Imóvel" : "Veículo / demais"}</small></td>
                      <td style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <input
                          type="number"
                          value={d.prazo_init}
                          onChange={(e) => patchDraft(r.id, { prazo_init: Number(e.target.value) })}
                          style={{ width: 72, padding: 8, borderRadius: 6, border: "1px solid var(--line)" }}
                        />
                        <span>–</span>
                        <input
                          type="number"
                          value={d.prazo_final}
                          onChange={(e) => patchDraft(r.id, { prazo_final: Number(e.target.value) })}
                          style={{ width: 72, padding: 8, borderRadius: 6, border: "1px solid var(--line)" }}
                        />
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <input
                          value={d.pago_init}
                          onChange={(e) => patchDraft(r.id, { pago_init: e.target.value })}
                          style={{ width: 64, padding: 8, borderRadius: 6, border: "1px solid var(--line)" }}
                        />
                        {" – "}
                        <input
                          value={d.pago_final}
                          onChange={(e) => patchDraft(r.id, { pago_final: e.target.value })}
                          style={{ width: 64, padding: 8, borderRadius: 6, border: "1px solid var(--line)" }}
                        />
                      </td>
                      <td>
                        <input
                          value={d.porc}
                          onChange={(e) => patchDraft(r.id, { porc: e.target.value })}
                          style={{ width: 72, padding: 8, borderRadius: 6, border: "1px solid var(--line)", fontWeight: 700 }}
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          value={d.sort_order}
                          onChange={(e) => patchDraft(r.id, { sort_order: Number(e.target.value) })}
                          style={{ width: 64, padding: 8, borderRadius: 6, border: "1px solid var(--line)" }}
                        />
                      </td>
                      <td>
                        <button
                          type="button"
                          className="table-action"
                          disabled={!dirty || savingId === r.id}
                          onClick={() => void saveRange(r)}
                        >
                          Salvar
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p style={{ padding: "12px 18px", fontSize: 11, color: "var(--muted)" }}>
              Alterações valem na hora no cálculo público de /vender-minha-cota. Pago ≥ 35% continua recusa no robô.
            </p>
          </div>
        )}
      </section>
    </>
  );
}
