"use client";

import { Bot, CheckCircle2, RefreshCw, WalletCards } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, downloadApi } from "@/lib/api";
import { CurrencyInput } from "@/components/currency-input";
import { MarketplaceQuotaFields } from "@/components/marketplace-quota-fields";
import { lookupCep } from "@/lib/cep-lookup";
import { formatDocumentDigits, validationMessageForPerson } from "@/lib/br-validation";
import { subcategoriesForAssetClass } from "@/lib/quota-subcategories";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function parseMoney(value: string): number {
  const n = Number(String(value || "").replace(",", "."));
  return Number.isFinite(n) && n > 0 ? n : 0;
}

type MatchQuota = {
  quota_id: string;
  group_code: string;
  quota_code: string;
  credit_value: string;
  premium_value: string;
  entrada_final?: string | null;
  installment_value?: string;
  installment_due_date?: string | null;
  remaining_installments?: number | null;
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
  administrator_name?: string | null;
  explanation: string;
  message?: string | null;
  lane?: string | null;
  rollover_applied?: boolean;
  markup_amount?: string | null;
  parcela_legacy?: string | null;
  tipo_credito?: string | null;
  vencimento_dia?: string | null;
  vencimento_proxima?: string | null;
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
  credit_band_percent?: string;
  entrada_band_percent?: string;
  combo_band_percent?: string;
  message: string;
};

type ConfirmResult = {
  lead_id: string;
  proposal_id: string;
  quota_ids: string[];
  reservation_ids: string[];
  requested_amount: string;
  entrada_final?: string | null;
  message: string;
  boleto?: { amount?: string; download_token?: string } | null;
  boleto_created?: boolean;
  contract_available?: boolean;
  cadastro_path?: string | null;
  boleto_download_path?: string | null;
  contract_pdf_path?: string | null;
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
  const [targetAmount, setTargetAmount] = useState("");
  const [targetEntrada, setTargetEntrada] = useState("");
  const [category, setCategory] = useState("REAL_ESTATE");
  const [quotaCategoryId, setQuotaCategoryId] = useState("");
  const [quotaCategories, setQuotaCategories] = useState<
    { id: string; name: string; legacy_type: number; parent_id: string | null; title_sub: string | null }[]
  >([]);
  type BankAdministrator = { id: string; name: string; rules: { is_bank?: boolean } };
  const [bankAdministrators, setBankAdministrators] = useState<BankAdministrator[]>([]);
  const [clientBankAdministratorIds, setClientBankAdministratorIds] = useState<string[]>([]);
  const [clientProblemBankAdministratorIds, setClientProblemBankAdministratorIds] = useState<string[]>([]);
  const [income, setIncome] = useState("");
  const [assetValue, setAssetValue] = useState("");
  const [assetYear, setAssetYear] = useState("");
  type CadastroShortcut = {
    lead_id: string;
    label: string;
    name: string;
    email: string | null;
    phone: string;
    document: string | null;
    person_type: string;
    address: Record<string, string>;
    monthly_income?: string | null;
    asset_value?: string | null;
    asset_year?: number | null;
    target_amount?: string | null;
    target_entrada?: string | null;
    category?: string | null;
    has_credit_restriction?: boolean | null;
    asset_is_zero_km?: boolean | null;
  };
  const [cadastros, setCadastros] = useState<CadastroShortcut[]>([]);
  const [existingId, setExistingId] = useState("");
  type PartnerOption = { id: string; name: string; role: string; email: string | null };
  const [partners, setPartners] = useState<PartnerOption[]>([]);
  const [partnerId, setPartnerId] = useState("");
  const [roboVideoUrl, setRoboVideoUrl] = useState("");

  useEffect(() => {
    api<{ values?: Record<string, string> }>("/admin/org-settings")
      .then((row) => setRoboVideoUrl((row.values?.chat_robo_video_url || "").trim()))
      .catch(() => setRoboVideoUrl(""));
  }, []);

  useEffect(() => {
    api<
      {
        id: string;
        name: string;
        legacy_type: number;
        parent_id: string | null;
        title_sub: string | null;
        asset_class?: string | null;
        active?: boolean;
      }[]
    >("/marketplace/quota-categories?marketplace=true")
      .then(setQuotaCategories)
      .catch(() => setQuotaCategories([]));
    api<{ id: string; name: string; rules: { is_bank?: boolean } }[]>("/administrators")
      .then((rows) => setBankAdministrators(rows.filter((a) => Boolean(a.rules?.is_bank))))
      .catch(() => setBankAdministrators([]));
  }, []);

  function toggleBankId(list: string[], id: string, checked: boolean, setter: (v: string[]) => void) {
    setter(checked ? [...list, id] : list.filter((x) => x !== id));
  }

  const subcategories = subcategoriesForAssetClass(quotaCategories, category as "REAL_ESTATE" | "VEHICLE");
  useEffect(() => {
    setQuotaCategoryId("");
  }, [category]);

  const loadCadastros = useCallback(async () => {
    try {
      const [c, p] = await Promise.all([
        api<CadastroShortcut[]>("/marketplace/venda-direta-manual/cadastros"),
        api<PartnerOption[]>("/marketplace/venda-direta-manual/partners"),
      ]);
      setCadastros(c);
      setPartners(p);
    } catch {
      setCadastros([]);
      setPartners([]);
    }
  }, []);

  useEffect(() => {
    void loadCadastros();
  }, [loadCadastros]);

  function applyCadastro(id: string) {
    setExistingId(id);
    if (!id) return;
    const row = cadastros.find((x) => x.lead_id === id);
    if (!row) return;
    setError("");
    setName(row.name || "");
    setEmail(row.email || "");
    setPhone(row.phone || "");
    const pt = row.person_type || "PF";
    setPersonType(pt);
    setDocument(formatDocumentDigits(row.document, pt));
    setZipcode(row.address?.zipcode || "");
    setStreet(row.address?.street || "");
    setNumber(row.address?.number || "");
    setNeighborhood(row.address?.neighborhood || "");
    setCity(row.address?.city || "");
    setUf(row.address?.uf || "");
    if (row.target_amount) setTargetAmount(String(row.target_amount));
    if (row.target_entrada) setTargetEntrada(String(row.target_entrada));
    if (row.monthly_income) setIncome(String(row.monthly_income));
    if (row.asset_value) setAssetValue(String(row.asset_value));
    if (row.asset_year) setAssetYear(String(row.asset_year));
    if (row.category) setCategory(row.category);
    if (row.has_credit_restriction != null) setDirty(!!row.has_credit_restriction);
    if (row.asset_is_zero_km != null) setZeroKm(!!row.asset_is_zero_km);
  }

  async function onCepBlur() {
    const addr = await lookupCep(zipcode);
    if (!addr) return;
    setStreet(addr.street);
    setNeighborhood(addr.neighborhood);
    setCity(addr.city);
    setUf(addr.uf);
  }
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
      const invalid = validationMessageForPerson(document, email, phone);
      if (invalid) {
        setError(invalid);
        setBusy(false);
        return;
      }
      if (!parseMoney(targetAmount)) {
        setError("Informe o crédito desejado.");
        setBusy(false);
        return;
      }
      if (!parseMoney(targetEntrada)) {
        setError("Informe a entrada desejada.");
        setBusy(false);
        return;
      }
      if (!parseMoney(income)) {
        setError("Informe a renda mensal.");
        setBusy(false);
        return;
      }
      if (!parseMoney(assetValue)) {
        setError("Informe o valor do bem.");
        setBusy(false);
        return;
      }
      if (parseMoney(targetAmount) > parseMoney(assetValue)) {
        setError(
          `Crédito desejado (${brl.format(parseMoney(targetAmount))}) não pode ser maior que o valor do bem (${brl.format(parseMoney(assetValue))}).`,
        );
        setBusy(false);
        return;
      }
      if (category === "VEHICLE" && !String(assetYear || "").trim()) {
        setError("Informe o ano do bem (veículo).");
        setBusy(false);
        return;
      }
      const data = await api<SearchResult>(
        "/marketplace/venda-direta-robo/search",
        {
        method: "POST",
        body: JSON.stringify({
          name,
          email,
          phone,
          person_type: personType,
          document,
          target_amount: String(parseMoney(targetAmount)),
          target_entrada: String(parseMoney(targetEntrada)),
          category,
          quota_category_id: quotaCategoryId || null,
          client_bank_administrator_ids: clientBankAdministratorIds,
          client_problem_bank_administrator_ids: clientProblemBankAdministratorIds,
          partner_user_id: partnerId || null,
          monthly_income: String(parseMoney(income)),
          monthly_commitment: "0",
          asset_value: String(parseMoney(assetValue)),
          asset_year: category === "VEHICLE" && assetYear ? Number(assetYear) : new Date().getFullYear(),
          has_credit_restriction: dirty,
          asset_is_zero_km: zeroKm,
          zipcode: zipcode || null,
          street: street || null,
          number: number || null,
          neighborhood: neighborhood || null,
          city: city || null,
          uf: uf || null,
        }),
      },
        { interactive: true },
      );
      if (!data.eligible) {
        setResult(null);
        setError(data.blockers?.join(" ") || data.message || "Nenhuma cota encontrada para esses filtros.");
        setNotice("");
        return;
      }
      setResult(data);
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

  const creditMatches = result?.credit_matches ?? [];
  const entradaMatches = result?.entrada_matches ?? [];
  const fallbackMatches =
    result && creditMatches.length === 0 && entradaMatches.length === 0 ? result.matches ?? [] : [];

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">VENDAS</span>
          <h1>Venda Direta — Robô</h1>
          <p>
            Preencha cliente e filtros; o robô sugere até 2 opções por crédito e 2 por entrada (com junção automática
            quando necessário). Ao confirmar, geramos contrato e boleto da entrada; a assinatura digital segue após o
            pagamento.
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
              <label className="marketplace-field marketplace-field-wide">
                Cadastro existente (atalho)
                <select value={existingId} onChange={(e) => applyCadastro(e.target.value)}>
                  <option value="">Novo cliente</option>
                  {cadastros.map((c) => (
                    <option key={c.lead_id} value={c.lead_id}>{c.label}</option>
                  ))}
                </select>
              </label>
              <label className="marketplace-field marketplace-field-wide">
                Parceiro / franquia (opcional)
                <select value={partnerId} onChange={(e) => setPartnerId(e.target.value)}>
                  <option value="">Sem parceiro</option>
                  {partners.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.role})
                    </option>
                  ))}
                </select>
              </label>
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
              <label className="marketplace-field marketplace-field-compact">
                Subcategoria
                <select value={quotaCategoryId} onChange={(e) => setQuotaCategoryId(e.target.value)}>
                  <option value="">Todas</option>
                  {subcategories.map((s) => {
                    const p = quotaCategories.find((x) => x.id === s.parent_id);
                    return (
                      <option key={s.id} value={s.id}>
                        {p ? `${p.title_sub || p.name} — ` : ""}
                        {s.name}
                      </option>
                    );
                  })}
                </select>
              </label>
              <label className="marketplace-field">
                Renda mensal (R$)
                <CurrencyInput value={income} onChange={setIncome} required />
              </label>
              <label className="marketplace-field">
                Valor do bem (R$)
                <CurrencyInput value={assetValue} onChange={setAssetValue} required />
              </label>
              {category === "VEHICLE" && (
                <label className="marketplace-field marketplace-field-compact">
                  Ano do bem
                  <input type="number" min={1980} max={2100} value={assetYear} onChange={(e) => setAssetYear(e.target.value)} required />
                </label>
              )}
              <label className="marketplace-field marketplace-field-compact" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" checked={dirty} onChange={(e) => setDirty(e.target.checked)} />
                Nome sujo / SPC
              </label>
              <label className="marketplace-field marketplace-field-compact" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" checked={zeroKm} onChange={(e) => setZeroKm(e.target.checked)} />
                Bem zero km
              </label>
            </div>

            {bankAdministrators.length > 0 && (
              <div className="marketplace-form-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 10 }}>
                <small className="muted">
                  Bancos administradores (legado): marque onde o cliente é correntista ou tem restrição com a administradora.
                </small>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "12px 20px" }}>
                  {bankAdministrators.map((adm) => (
                    <div key={adm.id} style={{ minWidth: 200 }}>
                      <b style={{ fontSize: 11 }}>{adm.name}</b>
                      <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, marginTop: 4 }}>
                        <input
                          type="checkbox"
                          checked={clientBankAdministratorIds.includes(adm.id)}
                          onChange={(e) =>
                            toggleBankId(clientBankAdministratorIds, adm.id, e.target.checked, setClientBankAdministratorIds)
                          }
                        />
                        Cliente correntista
                      </label>
                      <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, marginTop: 2 }}>
                        <input
                          type="checkbox"
                          checked={clientProblemBankAdministratorIds.includes(adm.id)}
                          onChange={(e) =>
                            toggleBankId(
                              clientProblemBankAdministratorIds,
                              adm.id,
                              e.target.checked,
                              setClientProblemBankAdministratorIds,
                            )
                          }
                        />
                        Restrição / inadimplência
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="marketplace-form-row">
              <label className="marketplace-field marketplace-field-compact">
                CEP
                <input value={zipcode} onChange={(e) => setZipcode(e.target.value)} onBlur={() => void onCepBlur()} />
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
              <RefreshCw className={busy ? "spin" : undefined} />
              {busy ? "Buscando…" : "Buscar cotas"}
            </button>
          </form>
        )}

        {step === 2 && result && (
          <div>
            {roboVideoUrl ? (
              <div className="notice" style={{ marginBottom: "1rem" }}>
                <p style={{ margin: "0 0 0.5rem" }}>
                  Vídeo explicativo (mesmo do chat público — configure em Configurações gerais):
                </p>
                <a className="text-link" href={roboVideoUrl} target="_blank" rel="noreferrer">
                  Abrir vídeo
                </a>
              </div>
            ) : null}
            <p>
              Pré-cadastro <b>{result.client_name}</b> · lead <code>{result.lead_id.slice(0, 8)}…</code>
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
            {fallbackMatches.map((m) => (
              <MatchCard key={m.quota_ids.join("-")} match={m} busy={busy} onConfirm={confirm} />
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
              {brl.format(Number(confirmed.requested_amount))}
              {confirmed.entrada_final ? ` · entrada ${brl.format(Number(confirmed.entrada_final))}` : ""} ·{" "}
              {confirmed.quota_ids.length} cota(s) travada(s).
            </p>
            <p className="muted" style={{ marginTop: 8 }}>
              Contrato disponível; ZapSign só após confirmação do pagamento da entrada.
            </p>
            <p style={{ marginTop: 12 }}>
              {confirmed.cadastro_path ? (
                <Link href={confirmed.cadastro_path}>Abrir cadastro Marketplace</Link>
              ) : (
                <Link href={`/modules/cadastros?lead_id=${encodeURIComponent(confirmed.lead_id)}`}>
                  Abrir cadastro Marketplace
                </Link>
              )}
              {" · "}
              <Link href={`/modules/proposals?proposal_id=${encodeURIComponent(confirmed.proposal_id)}`}>
                Propostas
              </Link>
              {confirmed.contract_pdf_path ? (
                <>
                  {" · "}
                  <button
                    type="button"
                    className="table-action"
                    onClick={() =>
                      void downloadApi(
                        confirmed.contract_pdf_path!,
                        `contrato-${confirmed.lead_id.slice(0, 8)}.pdf`,
                      ).catch((e) => setError(e instanceof Error ? e.message : "Falha ao baixar contrato"))
                    }
                  >
                    Contrato (PDF)
                  </button>
                </>
              ) : null}
              {confirmed.boleto_download_path && confirmed.boleto?.amount ? (
                <>
                  {" · "}
                  <button
                    type="button"
                    className="table-action"
                    onClick={() =>
                      void downloadApi(
                        confirmed.boleto_download_path!,
                        `boleto-${confirmed.lead_id.slice(0, 8)}.pdf`,
                      ).catch((e) => setError(e instanceof Error ? e.message : "Falha ao baixar boleto"))
                    }
                  >
                    Boleto entrada ({brl.format(Number(confirmed.boleto.amount))})
                  </button>
                </>
              ) : null}
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
  const combo = match.quota_ids.length > 1;
  return (
    <article className="marketplace-match-card">
      {match.lane === "CREDIT" ? <h4>Opção crédito{combo ? " (junção)" : ""}</h4> : null}
      {match.lane === "ENTRADA" ? <h4>Opção entrada{combo ? " (junção)" : ""}</h4> : null}
      {match.parcela_legacy ? (
        <p>
          <b>Parcelas:</b> {match.parcela_legacy}
          {match.vencimento_proxima ? ` · venc. ${match.vencimento_proxima}` : ""}
        </p>
      ) : null}
      {match.quotas.map((q) => (
        <div className="marketplace-match-quota" key={q.quota_id}>
          <MarketplaceQuotaFields quota={q} administratorFallback={match.administrator_name} />
        </div>
      ))}
      <button
        type="button"
        className="marketplace-submit"
        style={{ marginTop: "0.75rem" }}
        disabled={busy}
        onClick={() => void onConfirm(match)}
      >
        Confirmar{combo ? ` (${match.quota_ids.length} cotas)` : ""}
      </button>
    </article>
  );
}
