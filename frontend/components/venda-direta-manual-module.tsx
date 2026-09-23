"use client";

import { CheckCircle2, FilePenLine, RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { CurrencyInput } from "@/components/currency-input";
import { lookupCep } from "@/lib/cep-lookup";
import { validationMessageForPerson } from "@/lib/br-validation";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function parseMoney(value: string): number {
  const n = Number(String(value || "").replace(",", "."));
  return Number.isFinite(n) && n > 0 ? n : 0;
}

const SEARCH_BAND = 0.05;

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
};

function withinSearchBand(actual: number, target: number): boolean {
  if (target <= 0) return true;
  return Math.abs(actual - target) / target <= SEARCH_BAND;
}

function cotaListLabel(c: CotaOption): string {
  if (c.label) return c.label;
  const parc = c.remaining_installments != null ? ` · ${c.remaining_installments} parcelas` : "";
  return `${c.group_code} · ${c.quota_code} · crédito ${brl.format(Number(c.credit_value))} · entrada ${brl.format(Number(c.entrada_final))} · parc. ${brl.format(Number(c.installment_value || 0))}${parc} · ${c.administrator_name ?? "Adm."}`;
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
};

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
  const [cotas, setCotas] = useState<CotaOption[]>([]);
  const [cadastros, setCadastros] = useState<CadastroOption[]>([]);
  const [partners, setPartners] = useState<PartnerOption[]>([]);
  const [quotaIds, setQuotaIds] = useState<string[]>([]);
  const [partnerId, setPartnerId] = useState("");
  const [existingId, setExistingId] = useState("");
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
  const [done, setDone] = useState<StoreResult | null>(null);

  const loadCotas = useCallback(async (cat: string) => {
    const rows = await api<CotaOption[]>(`/marketplace/venda-direta-manual/cotas?category=${encodeURIComponent(cat)}`);
    setCotas(rows);
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
    loadCotas(category).catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar cotas"));
  }, [category, loadCotas]);

  useEffect(() => {
    loadMeta().catch(() => undefined);
  }, [loadMeta]);

  function applyCadastro(id: string) {
    setExistingId(id);
    const row = cadastros.find((x) => x.lead_id === id);
    if (!row) return;
    setName(row.name || "");
    setEmail(row.email || "");
    setPhone(row.phone || "");
    setPersonType(row.person_type || "PF");
    setDocument(row.document || "");
    setZipcode(row.address?.zipcode || "");
    setStreet(row.address?.street || "");
    setNumber(row.address?.number || "");
    setNeighborhood(row.address?.neighborhood || "");
    setCity(row.address?.city || "");
    setUf(row.address?.uf || "");
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
      const data = await api<StoreResult>("/marketplace/venda-direta-manual/store", {
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
          asset_value: String(parseMoney(assetValue)),
          asset_year: category === "VEHICLE" && assetYear ? Number(assetYear) : new Date().getFullYear(),
          has_credit_restriction: dirty,
          asset_is_zero_km: zeroKm,
        }),
      });
      setDone(data);
      setNotice(data.message);
      setQuotaIds([]);
      await loadCotas(category);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao gravar venda");
    } finally {
      setBusy(false);
    }
  }

  const filteredCotas = useMemo(() => {
    const creditTarget = parseMoney(filterCredit);
    const entradaTarget = parseMoney(filterEntrada);
    return cotas.filter((c) => {
      const credit = Number(c.credit_value);
      const entrada = Number(c.entrada_final);
      return withinSearchBand(credit, creditTarget) && withinSearchBand(entrada, entradaTarget);
    });
  }, [cotas, filterCredit, filterEntrada]);

  const selectedList = cotas.filter((c) => quotaIds.includes(c.quota_id));

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
            <small className="marketplace-hint">Filtro com tolerância de ±5% quando você informa um valor.</small>
            <div className="marketplace-field marketplace-field-wide">
              <b>Cotas (multi-seleção){filteredCotas.length ? ` — ${filteredCotas.length} opção(ões)` : ""}</b>
              <div style={{ maxHeight: 220, overflowY: "auto", marginTop: 8 }}>
                {filteredCotas.length === 0 ? (
                  <small className="muted">Nenhuma cota neste filtro. Ajuste crédito/entrada ou a categoria.</small>
                ) : (
                  filteredCotas.map((c) => (
                    <label key={c.quota_id} style={{ display: "block", marginBottom: 6 }}>
                      <input
                        type="checkbox"
                        checked={quotaIds.includes(c.quota_id)}
                        onChange={(e) =>
                          setQuotaIds((ids) =>
                            e.target.checked ? [...ids, c.quota_id] : ids.filter((id) => id !== c.quota_id),
                          )
                        }
                      />
                      {cotaListLabel(c)}
                    </label>
                  ))
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
