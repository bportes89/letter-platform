"use client";

import { CheckCircle2, FilePenLine, RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { CurrencyInput } from "@/components/currency-input";
import { lookupCep } from "@/lib/cep-lookup";
import { formatDocumentDigits, validationMessageForPerson } from "@/lib/br-validation";
import { commercialQuotaDisplay } from "@/lib/commercial-quota-label";
import { subcategoriesForAssetClass } from "@/lib/quota-subcategories";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function parseMoney(value: string): number {
  const n = Number(String(value || "").replace(",", "."));
  return Number.isFinite(n) && n > 0 ? n : 0;
}

const SEARCH_BAND = 0.1;

type CotaOption = {
  quota_id: string;
  group_code: string;
  quota_code: string;
  label: string;
  credit_value: string;
  entrada_final: string;
  installment_value: string;
  remaining_installments?: number | null;
  administrator_id: string;
  nina_scan_status: string | null;
  administrator_name: string | null;
  supplier_source: string | null;
  installment_due_date?: string | null;
  status?: string;
};

function withinSearchBand(actual: number, target: number): boolean {
  if (target <= 0) return true;
  return Math.abs(actual - target) / target <= SEARCH_BAND;
}

function cotaListLabel(c: CotaOption): string {
  return commercialQuotaDisplay(c);
}

type CadastroOption = {
  lead_id: string;
  name: string;
  document: string | null;
  phone: string;
  email: string | null;
  person_type: string;
  address: Record<string, string>;
  label: string;
  monthly_income?: string | null;
  asset_value?: string | null;
  asset_year?: number | null;
  target_amount?: string | null;
  target_entrada?: string | null;
  category?: string | null;
  has_credit_restriction?: boolean | null;
  asset_is_zero_km?: boolean | null;
  occupation?: string | null;
};

type CadastroDetail = CadastroOption & {
  credit_value?: string | null;
  entrada_value?: string | null;
  occupation?: string | null;
};

function quotaReadyForSale(c: CotaOption): boolean {
  return (c.status ?? "AVAILABLE") === "AVAILABLE" && !!c.installment_due_date;
}

type PartnerOption = { id: string; name: string; role: string; email: string | null };

type StoreResult = {
  lead_id: string;
  proposal_id: string;
  quota_id: string;
  reservation_id: string;
  requested_amount: string;
  entrada_final: string;
  message: string;
};

export function VendaDiretaManualModule() {
  const [category, setCategory] = useState("REAL_ESTATE");
  const [filterCredit, setFilterCredit] = useState("");
  const [filterEntrada, setFilterEntrada] = useState("");
  const [filterAdministratorId, setFilterAdministratorId] = useState("");
  const [showIncompleteQuotas, setShowIncompleteQuotas] = useState(false);
  const [cotas, setCotas] = useState<CotaOption[]>([]);
  const [cadastros, setCadastros] = useState<CadastroOption[]>([]);
  const [partners, setPartners] = useState<PartnerOption[]>([]);
  const [quotaIds, setQuotaIds] = useState<string[]>([]);
  const [partnerId, setPartnerId] = useState("");
  const [existingId, setExistingId] = useState("");
  const [quotaCategoryId, setQuotaCategoryId] = useState("");
  const [quotaCategories, setQuotaCategories] = useState<
    { id: string; name: string; legacy_type: number; parent_id: string | null; title_sub: string | null }[]
  >([]);
  type BankAdministrator = { id: string; name: string; rules: { is_bank?: boolean } };
  const [bankAdministrators, setBankAdministrators] = useState<BankAdministrator[]>([]);
  const [clientBankAdministratorIds, setClientBankAdministratorIds] = useState<string[]>([]);
  const [clientProblemBankAdministratorIds, setClientProblemBankAdministratorIds] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [personType, setPersonType] = useState("PF");
  const [document, setDocument] = useState("");
  const [occupation, setOccupation] = useState("");
  const [income, setIncome] = useState("");
  const [assetValue, setAssetValue] = useState("");
  const [assetYear, setAssetYear] = useState("");
  const [dirty, setDirty] = useState(false);
  const [zeroKm, setZeroKm] = useState(false);
  const [zipcode, setZipcode] = useState("");
  const [street, setStreet] = useState("");
  const [number, setNumber] = useState("");
  const [neighborhood, setNeighborhood] = useState("");
  const [city, setCity] = useState("");
  const [uf, setUf] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [cotasLoading, setCotasLoading] = useState(false);
  const [done, setDone] = useState<StoreResult | null>(null);

  const loadCotas = useCallback(async (cat: string, administratorId?: string) => {
    const params = new URLSearchParams({ category: cat, limit: "400" });
    if (administratorId) params.set("administrator_id", administratorId);
    setCotasLoading(true);
    try {
      const rows = await api<CotaOption[]>(`/marketplace/venda-direta-manual/cotas?${params.toString()}`);
      setCotas(rows);
    } finally {
      setCotasLoading(false);
    }
  }, []);

  const loadMeta = useCallback(async () => {
    const [c, p] = await Promise.all([
      api<CadastroOption[]>("/marketplace/venda-direta-manual/cadastros"),
      api<PartnerOption[]>("/marketplace/venda-direta-manual/partners"),
    ]);
    setCadastros(c);
    setPartners(p);
  }, []);

  useEffect(() => {
    void loadCotas(category, filterAdministratorId || undefined).catch((e) =>
      setError(e instanceof Error ? e.message : "Falha ao carregar cotas"),
    );
  }, [category, filterAdministratorId, loadCotas]);

  useEffect(() => {
    loadMeta().catch(() => undefined);
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
    api<BankAdministrator[]>("/administrators")
      .then((rows) => setBankAdministrators(rows.filter((a) => Boolean(a.rules?.is_bank))))
      .catch(() => setBankAdministrators([]));
  }, [loadMeta]);

  const subcategories = subcategoriesForAssetClass(quotaCategories, category as "REAL_ESTATE" | "VEHICLE");
  useEffect(() => {
    setQuotaCategoryId("");
  }, [category]);

  function toggleBankId(list: string[], id: string, checked: boolean, setter: (v: string[]) => void) {
    setter(checked ? [...list, id] : list.filter((x) => x !== id));
  }

  function fillCadastroFromRow(row: CadastroOption | CadastroDetail) {
    setName(row.name || "");
    setEmail(row.email || "");
    setPhone(row.phone || "");
    const pt = row.person_type || "PF";
    setPersonType(pt);
    setDocument(formatDocumentDigits(row.document, pt));
    if (row.occupation) setOccupation(String(row.occupation));
    const addr = row.address || {};
    setZipcode(addr.zipcode || "");
    setStreet(addr.street || "");
    setNumber(addr.number || "");
    setNeighborhood(addr.neighborhood || "");
    setCity(addr.city || "");
    setUf(addr.uf || "");
    if (row.monthly_income) setIncome(String(row.monthly_income));
    if (row.asset_value) setAssetValue(String(row.asset_value));
    if (row.asset_year) setAssetYear(String(row.asset_year));
    if (row.has_credit_restriction != null) setDirty(!!row.has_credit_restriction);
    if (row.asset_is_zero_km != null) setZeroKm(!!row.asset_is_zero_km);
    if (row.category) setCategory(row.category);
    const detail = row as CadastroDetail;
    const credit = detail.credit_value || row.target_amount;
    const entrada = detail.entrada_value || row.target_entrada;
    if (credit) setFilterCredit(String(credit));
    if (entrada) setFilterEntrada(String(entrada));
  }

  function applyCadastro(id: string) {
    setExistingId(id);
    if (!id) return;
    setError("");
    const row = cadastros.find((x) => x.lead_id === id);
    if (!row) {
      setError("Cadastro não encontrado na lista. Atualize a página.");
      return;
    }
    fillCadastroFromRow(row);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    setDone(null);
    try {
      const invalid = validationMessageForPerson(document, email, phone);
      if (invalid) {
        setError(invalid);
        setBusy(false);
        return;
      }
      if (!quotaIds.length) {
        setError("Selecione ao menos uma cota.");
        setBusy(false);
        return;
      }
      const blocked = quotaIds.filter((id) => {
        const c = cotas.find((x) => x.quota_id === id);
        return c && !quotaReadyForSale(c);
      });
      if (blocked.length) {
        setError(
          "Uma ou mais cotas estão incompletas (falta vencimento da parcela no Inventário). O admin deve completar antes da venda.",
        );
        setBusy(false);
        return;
      }
      if (!parseMoney(income) || !parseMoney(assetValue)) {
        setError("Informe renda e valor do bem.");
        setBusy(false);
        return;
      }
      if (category === "VEHICLE" && !String(assetYear || "").trim()) {
        setError("Informe o ano do bem (veículo).");
        setBusy(false);
        return;
      }
      const data = await api<StoreResult>(
        "/marketplace/venda-direta-manual/store",
        {
          method: "POST",
          body: JSON.stringify({
          name,
          email,
          phone,
          person_type: personType,
          document,
          quota_ids: quotaIds,
          quota_id: quotaIds[0],
          partner_user_id: partnerId || null,
          zipcode,
          street,
          number,
          neighborhood,
          city,
          uf,
          occupation: occupation || null,
          monthly_income: String(parseMoney(income)),
          monthly_commitment: "0",
          asset_value: String(parseMoney(assetValue)),
          asset_year: category === "VEHICLE" && assetYear ? Number(assetYear) : new Date().getFullYear(),
          has_credit_restriction: dirty,
          asset_is_zero_km: zeroKm,
          quota_category_id: quotaCategoryId || null,
          client_bank_administrator_ids: clientBankAdministratorIds,
          client_problem_bank_administrator_ids: clientProblemBankAdministratorIds,
          }),
        },
        { interactive: true },
      );
      setDone(data);
      setNotice(data.message);
      setQuotaIds([]);
      void loadCotas(category, filterAdministratorId || undefined).catch(() => undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao gravar venda");
    } finally {
      setBusy(false);
    }
  }

  const administratorOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of cotas) {
      if (c.administrator_id) {
        map.set(c.administrator_id, c.administrator_name || "Administradora");
      }
    }
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1], "pt-BR"));
  }, [cotas]);

  const filteredCotas = useMemo(() => {
    const creditTarget = parseMoney(filterCredit);
    const entradaTarget = parseMoney(filterEntrada);
    return cotas.filter((c) => {
      if (!showIncompleteQuotas && !quotaReadyForSale(c)) return false;
      if (filterAdministratorId && c.administrator_id !== filterAdministratorId) return false;
      const credit = Number(c.credit_value);
      const entrada = Number(c.entrada_final);
      return withinSearchBand(credit, creditTarget) && withinSearchBand(entrada, entradaTarget);
    });
  }, [cotas, filterCredit, filterEntrada, filterAdministratorId, showIncompleteQuotas]);

  const selectedList = cotas.filter((c) => quotaIds.includes(c.quota_id));

  function toggleQuota(c: CotaOption, checked: boolean) {
    if (checked && !quotaReadyForSale(c)) {
      setError("Cota sem vencimento de parcela — o admin deve completar no Inventário antes de vender.");
      return;
    }
    if (!checked) {
      setQuotaIds((ids) => ids.filter((id) => id !== c.quota_id));
      return;
    }
    if (quotaIds.length > 0) {
      const anchor = cotas.find((x) => x.quota_id === quotaIds[0]);
      if (anchor && anchor.administrator_id !== c.administrator_id) {
        setError("Junção manual só permite cotas da mesma administradora.");
        return;
      }
    }
    setError("");
    setQuotaIds((ids) => [...ids, c.quota_id]);
  }

  async function onCepBlur() {
    const addr = await lookupCep(zipcode);
    if (!addr) return;
    setStreet(addr.street);
    setNeighborhood(addr.neighborhood);
    setCity(addr.city);
    setUf(addr.uf);
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">VENDAS</span>
          <h1>Venda Direta — Manual</h1>
          <p>
            Admin escolhe a(s) cota(s) no inventário e grava a venda (WhatsApp, ligação, reunião). Mesmas regras Bacen
            da Venda Direta Robô (renda × parcela, SCR, idade do bem, lastro). Entrada já considera markup do fornecedor.
          </p>
        </div>
        <div className="operational-icon">
          <FilePenLine />
        </div>
      </div>

      <section className="panel operational-panel">
        <div className="notice">
          <FilePenLine />
          Para combinação automática use{" "}
          <Link href="/modules/venda-direta-robo">Venda Direta Robô</Link>. Após gravar, finalize em{" "}
          <Link href="/modules/proposals">Propostas</Link>.
        </div>

        {notice && (
          <div className="notice">
            <CheckCircle2 />
            {notice}
          </div>
        )}
        {error && <div className="error">{error}</div>}

        {done && (
          <div className="notice" style={{ marginBottom: "1rem" }}>
            Proposta <code>{done.proposal_id}</code> · crédito {brl.format(Number(done.requested_amount))} · entrada{" "}
            {brl.format(Number(done.entrada_final))} ·{" "}
            <Link href="/modules/proposals">Ir para Propostas</Link>
          </div>
        )}

        <form className="marketplace-form" onSubmit={submit}>
          <div className="marketplace-form-row">
            <label className="marketplace-field">
              Parceiro / franquia (opcional)
              <select value={partnerId} onChange={(e) => setPartnerId(e.target.value)}>
                <option value="">Sem vínculo</option>
                {partners.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.role})
                  </option>
                ))}
              </select>
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Categoria
              <select
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value);
                  setQuotaIds([]);
                  setFilterCredit("");
                  setFilterEntrada("");
                  setFilterAdministratorId("");
                }}
              >
                <option value="REAL_ESTATE">Imóvel</option>
                <option value="VEHICLE">Veículo</option>
              </select>
            </label>
            <label className="marketplace-field">
              <span className="marketplace-field-label">
                <Search size={14} />
                Buscar por crédito (R$)
              </span>
              <CurrencyInput value={filterCredit} onChange={setFilterCredit} placeholder="Ex.: 250.000" />
            </label>
            <label className="marketplace-field">
              <span className="marketplace-field-label">
                <Search size={14} />
                Buscar por entrada (R$)
              </span>
              <CurrencyInput value={filterEntrada} onChange={setFilterEntrada} placeholder="Ex.: 80.000" />
            </label>
            <label className="marketplace-field">
              Administradora
              <select
                value={filterAdministratorId}
                onChange={(e) => setFilterAdministratorId(e.target.value)}
              >
                <option value="">Todas</option>
                {administratorOptions.map(([id, name]) => (
                  <option key={id} value={id}>
                    {name}
                  </option>
                ))}
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
            <small className="marketplace-hint">
              Refino local ±10% crédito/entrada. Lista já respeita alienações admin×categoria, nome sujo e bancos (como
              Robô/chat). Só cotas com vencimento de parcela podem ser vendidas.
            </small>
            {bankAdministrators.length > 0 && (
              <div className="marketplace-form-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
                <small className="muted">Bancos administradores (correntista / problema)</small>
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
                        Banco problema
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <label className="marketplace-field marketplace-field-compact" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={showIncompleteQuotas}
                onChange={(e) => setShowIncompleteQuotas(e.target.checked)}
              />
              Mostrar cotas incompletas (admin)
            </label>
            <div className="marketplace-field marketplace-field-wide quota-pick-list">
              <b>Cotas (multi-seleção){filteredCotas.length ? ` — ${filteredCotas.length} opção(ões)` : ""}</b>
              <div className="quota-pick-scroll">
                {cotasLoading ? (
                  <small className="muted">
                    <RefreshCw className="spin" style={{ marginRight: 6, verticalAlign: "middle" }} />
                    Carregando cotas…
                  </small>
                ) : filteredCotas.length === 0 ? (
                  <small className="muted">
                    Nenhuma cota neste filtro. Ajuste crédito, entrada, administradora ou a categoria.
                  </small>
                ) : (
                  filteredCotas.map((c) => {
                    const ready = quotaReadyForSale(c);
                    return (
                      <label key={c.quota_id} className="quota-pick-row" style={{ opacity: ready ? 1 : 0.7 }}>
                        <input
                          type="checkbox"
                          disabled={!ready}
                          checked={quotaIds.includes(c.quota_id)}
                          onChange={(e) => toggleQuota(c, e.target.checked)}
                        />
                        <span>
                          {cotaListLabel(c)}
                          {!ready ? <small className="muted"> — incompleta (vencimento no Inventário)</small> : null}
                        </span>
                      </label>
                    );
                  })
                )}
              </div>
            </div>
            {selectedList.length > 0 && (
              <div className="notice" style={{ width: "100%" }}>
                {selectedList.length} cota(s) selecionada(s) · crédito total{" "}
                {brl.format(selectedList.reduce((s, c) => s + Number(c.credit_value), 0))}
              </div>
            )}
          </div>

          <div className="marketplace-form-row">
            <label className="marketplace-field marketplace-field-wide">
              Cadastro existente (atalho)
              <select value={existingId} onChange={(e) => applyCadastro(e.target.value)}>
                <option value="">Novo cliente</option>
                {cadastros.map((c) => (
                  <option key={c.lead_id} value={c.lead_id}>
                    {c.label}
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
              <input value={document} onChange={(e) => setDocument(e.target.value)} required />
            </label>
            <label className="marketplace-field">
              {personType === "PJ" ? "Ramo / atividade" : "Profissão"}
              <input value={occupation} onChange={(e) => setOccupation(e.target.value)} />
            </label>
            <label className="marketplace-field">
              Renda / faturamento (R$)
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

          <div className="marketplace-form-row">
            <label className="marketplace-field marketplace-field-compact">
              CEP
              <input value={zipcode} onChange={(e) => setZipcode(e.target.value)} onBlur={() => void onCepBlur()} required minLength={8} />
            </label>
            <label className="marketplace-field">
              Endereço
              <input value={street} onChange={(e) => setStreet(e.target.value)} required />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              Número
              <input value={number} onChange={(e) => setNumber(e.target.value)} required />
            </label>
            <label className="marketplace-field">
              Bairro
              <input value={neighborhood} onChange={(e) => setNeighborhood(e.target.value)} required />
            </label>
            <label className="marketplace-field">
              Cidade
              <input value={city} onChange={(e) => setCity(e.target.value)} required />
            </label>
            <label className="marketplace-field marketplace-field-compact">
              UF
              <input value={uf} onChange={(e) => setUf(e.target.value.toUpperCase())} required maxLength={2} minLength={2} />
            </label>
          </div>

          <button type="submit" className="marketplace-submit" disabled={busy || quotaIds.length === 0}>
            <RefreshCw />
            {busy ? "Gravando…" : "Gravar venda"}
          </button>
        </form>
      </section>
    </>
  );
}
