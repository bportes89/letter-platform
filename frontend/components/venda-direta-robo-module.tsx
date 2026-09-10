"use client";

import { Bot, CheckCircle2, RefreshCw, WalletCards } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { CurrencyInput } from "@/components/currency-input";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type MatchQuota = {
  quota_id: string;
  group_code: string;
  quota_code: string;
  credit_value: string;
  premium_value: string;
  entrada_final?: string | null;
  installment_value?: string;
  supplier_source?: string | null;
  markup_percent?: string | null;
  rollover_applied?: boolean;
  administrator_name?: string | null;
  status: string;
  nina_scan_status?: string | null;
};

type MarketplaceMatch = {
  quota_ids: string[];
  total_credit: string;
  total_entrada?: string | null;
  deviation_percent: string;
  entrada_deviation_percent?: string | null;
  score: number;
  explanation: string;
  message?: string | null;
  lane?: string | null;
  rollover_applied?: boolean;
  markup_amount?: string | null;
  quotas: MatchQuota[];
};

type SearchResult = {
  lead_id: string;
  client_name: string;
  esteira: string;
  eligible: boolean;
  blockers: string[];
  matches: MarketplaceMatch[];
  credit_matches?: MarketplaceMatch[];
  entrada_matches?: MarketplaceMatch[];
  band_percent?: string;
  message: string;
};

type ConfirmResult = {
  lead_id: string;
  proposal_id: string;
  quota_ids: string[];
  reservation_ids: string[];
  requested_amount: string;
  message: string;
};

export function VendaDiretaRoboModule() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [confirmed, setConfirmed] = useState<ConfirmResult | null>(null);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [personType, setPersonType] = useState("PF");
  const [document, setDocument] = useState("");
  const [targetAmount, setTargetAmount] = useState("400000");
  const [targetEntrada, setTargetEntrada] = useState("80000");
  const [category, setCategory] = useState("REAL_ESTATE");
  const [income, setIncome] = useState("30000");
  const [commitment, setCommitment] = useState("0");
  const [assetValue, setAssetValue] = useState("600000");
  const [assetYear, setAssetYear] = useState("2020");
  const [dirty, setDirty] = useState(false);
  const [zeroKm, setZeroKm] = useState(false);
  const [zipcode, setZipcode] = useState("");
  const [street, setStreet] = useState("");
  const [number, setNumber] = useState("");
  const [neighborhood, setNeighborhood] = useState("");
  const [city, setCity] = useState("");
  const [uf, setUf] = useState("");

  async function search(e: FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    setConfirmed(null);
    try {
      const data = await api<SearchResult>("/marketplace/venda-direta-robo/search", {
        method: "POST",
        body: JSON.stringify({
          name,
          email,
          phone,
          person_type: personType,
          document,
          target_amount: targetAmount,
          target_entrada: targetEntrada,
          category,
          monthly_income: income,
          monthly_commitment: commitment || "0",
          asset_value: assetValue,
          asset_year: Number(assetYear),
          has_credit_restriction: dirty,
          asset_is_zero_km: zeroKm,
          zipcode: zipcode || null,
          street: street || null,
          number: number || null,
          neighborhood: neighborhood || null,
          city: city || null,
          uf: uf || null,
        }),
      });
      setResult(data);
      setNotice(data.message);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha na busca do robô");
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  async function confirm(match: MarketplaceMatch) {
    if (!result) return;
    setError("");
    setBusy(true);
    try {
      for (const q of match.quotas) {
        if (q.nina_scan_status !== "CLEARED") {
          await api(`/quotas/${q.quota_id}/nina-scan`, { method: "POST" });
        }
      }
      const data = await api<ConfirmResult>("/marketplace/venda-direta-robo/confirm", {
        method: "POST",
        body: JSON.stringify({
          lead_id: result.lead_id,
          quota_ids: match.quota_ids,
          match_lane: match.lane || null,
        }),
      });
      setConfirmed(data);
      setNotice(data.message);
      setStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao confirmar cota");
    } finally {
      setBusy(false);
    }
  }

  function resetWizard() {
    setStep(1);
    setResult(null);
    setConfirmed(null);
    setError("");
    setNotice("");
  }

  const creditMatches = result?.credit_matches?.length ? result.credit_matches : result?.matches || [];
  const entradaMatches = result?.entrada_matches || [];

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">VENDAS</span>
          <h1>Venda Direta — Robô</h1>
          <p>
            Preencha cliente e filtros; o robô Esteira 2 (régua 5%, lanes crédito/entrada, rollover e markup)
            sugere cotas. Confirme para gravar lead + proposta e travar 60 minutos.
          </p>
        </div>
        <div className="operational-icon">
          <Bot />
        </div>
      </div>

      <section className="panel operational-panel">
        <div className="notice">
          <WalletCards />
          Mesmo motor do Marketplace Esteira 2. Cadastre cotas em{" "}
          <Link href="/modules/inventory">Inventário</Link>. Após confirmar, finalize em{" "}
          <Link href="/modules/proposals">Propostas</Link>.
        </div>

        <div className="marketplace-tabs" style={{ marginBottom: "1rem" }}>
          <button type="button" className={`marketplace-tab${step === 1 ? " active" : ""}`} onClick={() => step > 1 && setStep(1)} disabled={step === 3}>
            1 · Dados e filtros
          </button>
          <button type="button" className={`marketplace-tab${step === 2 ? " active" : ""}`} disabled={step < 2 || step === 3}>
            2 · Escolher cota
          </button>
          <button type="button" className={`marketplace-tab${step === 3 ? " active" : ""}`} disabled={step < 3}>
            3 · Gravado
          </button>
        </div>

        {notice && (
          <div className="notice">
            <CheckCircle2 />
            {notice}
          </div>
        )}
        {error && <div className="error">{error}</div>}

        {step === 1 && (
          <form className="marketplace-form" onSubmit={search}>
            <div className="marketplace-form-row">
              <label className="marketplace-field">
                Nome
                <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
              </label>
              <label className="marketplace-field">
                E-mail
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </label>
              <label className="marketplace-field">
                Telefone / WhatsApp
                <input value={phone} onChange={(e) => setPhone(e.target.value)} required minLength={8} />
              </label>
              <label className="marketplace-field marketplace-field-compact">
                Tipo
                <select value={personType} onChange={(e) => setPersonType(e.target.value)}>
                  <option value="PF">Pessoa física</option>
                  <option value="PJ">Pessoa jurídica</option>
                </select>
              </label>
              <label className="marketplace-field">
                {personType === "PJ" ? "CNPJ" : "CPF"}
                <input value={document} onChange={(e) => setDocument(e.target.value)} required placeholder={personType === "PJ" ? "00.000.000/0000-00" : "000.000.000-00"} />
              </label>
            </div>

            <div className="marketplace-form-row">
              <label className="marketplace-field">
                Crédito desejado (R$)
                <CurrencyInput value={targetAmount} onChange={setTargetAmount} required />
              </label>
              <label className="marketplace-field">
                Entrada desejada (R$)
                <CurrencyInput value={targetEntrada} onChange={setTargetEntrada} required />
              </label>
              <label className="marketplace-field marketplace-field-compact">
                Categoria
                <select value={category} onChange={(e) => setCategory(e.target.value)}>
                  <option value="REAL_ESTATE">Imóvel</option>
                  <option value="VEHICLE">Veículo</option>
                </select>
              </label>
              <label className="marketplace-field">
                Renda mensal (R$)
                <CurrencyInput value={income} onChange={setIncome} required />
              </label>
              <label className="marketplace-field">
                Comprometimento (R$)
                <CurrencyInput value={commitment} onChange={setCommitment} />
              </label>
              <label className="marketplace-field">
                Valor do bem (R$)
                <CurrencyInput value={assetValue} onChange={setAssetValue} required />
              </label>
              <label className="marketplace-field marketplace-field-compact">
                Ano do bem
                <input type="number" min={1980} max={2100} value={assetYear} onChange={(e) => setAssetYear(e.target.value)} required />
              </label>
              <label className="marketplace-field marketplace-field-compact" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" checked={dirty} onChange={(e) => setDirty(e.target.checked)} />
                Nome sujo / SPC
              </label>
              <label className="marketplace-field marketplace-field-compact" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" checked={zeroKm} onChange={(e) => setZeroKm(e.target.checked)} />
                Bem zero km
              </label>
            </div>

            <div className="marketplace-form-row">
              <label className="marketplace-field marketplace-field-compact">
                CEP
                <input value={zipcode} onChange={(e) => setZipcode(e.target.value)} />
              </label>
              <label className="marketplace-field">
                Endereço
                <input value={street} onChange={(e) => setStreet(e.target.value)} />
              </label>
              <label className="marketplace-field marketplace-field-compact">
                Número
                <input value={number} onChange={(e) => setNumber(e.target.value)} />
              </label>
              <label className="marketplace-field">
                Bairro
                <input value={neighborhood} onChange={(e) => setNeighborhood(e.target.value)} />
              </label>
              <label className="marketplace-field">
                Cidade
                <input value={city} onChange={(e) => setCity(e.target.value)} />
              </label>
              <label className="marketplace-field marketplace-field-compact">
                UF
                <input value={uf} onChange={(e) => setUf(e.target.value.toUpperCase())} maxLength={2} />
              </label>
            </div>

            <button type="submit" className="marketplace-submit" disabled={busy}>
              <RefreshCw />
              {busy ? "Buscando…" : "Buscar cotas"}
            </button>
          </form>
        )}

        {step === 2 && result && (
          <div>
            <p>
              Pré-cadastro <b>{result.client_name}</b> · régua {result.band_percent ?? "5"}% · lead{" "}
              <code>{result.lead_id.slice(0, 8)}…</code>
            </p>
            {result.blockers.map((b) => (
              <div className="error" key={b}>
                {b}
              </div>
            ))}
            {creditMatches.length > 0 && <h3>Lane crédito</h3>}
            {creditMatches.map((m) => (
              <MatchCard key={`c-${m.quota_ids.join("-")}`} match={m} busy={busy} onConfirm={confirm} />
            ))}
            {entradaMatches.length > 0 && <h3>Lane entrada</h3>}
            {entradaMatches.map((m) => (
              <MatchCard key={`e-${m.quota_ids.join("-")}`} match={m} busy={busy} onConfirm={confirm} />
            ))}
            <button type="button" className="table-action" style={{ marginTop: "1rem" }} onClick={resetWizard} disabled={busy}>
              Voltar e ajustar filtros
            </button>
          </div>
        )}

        {step === 3 && confirmed && (
          <div>
            <div className="notice">
              <CheckCircle2 />
              {confirmed.message}
            </div>
            <p>
              Proposta <code>{confirmed.proposal_id}</code> · crédito{" "}
              {brl.format(Number(confirmed.requested_amount))} · {confirmed.quota_ids.length} cota(s) travada(s).
            </p>
            <p>
              <Link href="/modules/proposals">Ir para Propostas</Link>
              {" · "}
              <button type="button" className="table-action" onClick={resetWizard}>
                Nova venda robô
              </button>
            </p>
          </div>
        )}
      </section>
    </>
  );
}

function MatchCard({
  match,
  busy,
  onConfirm,
}: {
  match: MarketplaceMatch;
  busy: boolean;
  onConfirm: (m: MarketplaceMatch) => void;
}) {
  return (
    <article className="backlog-item">
      <div>
        <strong>
          {match.quotas[0]?.administrator_name ?? "Administradora"} · crédito {brl.format(Number(match.total_credit))}
          {match.total_entrada ? ` · entrada ${brl.format(Number(match.total_entrada))}` : ""}
        </strong>
        <p>
          {match.explanation}
          {match.message ? ` — ${match.message}` : ""}
        </p>
        <small>
          Lane {match.lane ?? "—"} · Score {match.score} · Desvio crédito {match.deviation_percent}%
          {match.entrada_deviation_percent != null ? ` · Desvio entrada ${match.entrada_deviation_percent}%` : ""}
          {match.rollover_applied ? " · Rollover 7d" : ""}
          {match.markup_amount ? ` · Markup ${brl.format(Number(match.markup_amount))}` : ""}
        </small>
        <div>
          {match.quotas.map((q) => (
            <div key={q.quota_id} style={{ marginTop: "0.35rem" }}>
              {q.group_code}/{q.quota_code} · crédito {brl.format(Number(q.credit_value))} · entrada{" "}
              {brl.format(Number(q.entrada_final ?? q.premium_value))}
              {q.supplier_source ? ` · ${q.supplier_source}` : ""}
              {q.markup_percent && Number(q.markup_percent) > 0 ? ` (+${q.markup_percent}%)` : ""} · Nina{" "}
              {q.nina_scan_status ?? "PENDENTE"}
            </div>
          ))}
        </div>
        <button type="button" className="marketplace-submit" style={{ marginTop: "0.75rem" }} disabled={busy} onClick={() => onConfirm(match)}>
          Confirmar esta opção
        </button>
      </div>
    </article>
  );
}
