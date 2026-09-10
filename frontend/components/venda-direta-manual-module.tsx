"use client";

import { CheckCircle2, FilePenLine, RefreshCw } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { CurrencyInput } from "@/components/currency-input";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type CotaOption = {
  quota_id: string;
  label: string;
  credit_value: string;
  entrada_final: string;
  installment_value: string;
  nina_scan_status: string | null;
  administrator_name: string | null;
  supplier_source: string | null;
};

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
  const [cotas, setCotas] = useState<CotaOption[]>([]);
  const [cadastros, setCadastros] = useState<CadastroOption[]>([]);
  const [partners, setPartners] = useState<PartnerOption[]>([]);
  const [quotaId, setQuotaId] = useState("");
  const [partnerId, setPartnerId] = useState("");
  const [existingId, setExistingId] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [personType, setPersonType] = useState("PF");
  const [document, setDocument] = useState("");
  const [occupation, setOccupation] = useState("");
  const [income, setIncome] = useState("");
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
      const data = await api<StoreResult>("/marketplace/venda-direta-manual/store", {
        method: "POST",
        body: JSON.stringify({
          name,
          email,
          phone,
          person_type: personType,
          document,
          quota_id: quotaId,
          partner_user_id: partnerId || null,
          zipcode,
          street,
          number,
          neighborhood,
          city,
          uf,
          occupation: occupation || null,
          monthly_income: income || null,
        }),
      });
      setDone(data);
      setNotice(data.message);
      setQuotaId("");
      await loadCotas(category);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao gravar venda");
    } finally {
      setBusy(false);
    }
  }

  const selected = cotas.find((c) => c.quota_id === quotaId);

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">VENDAS</span>
          <h1>Venda Direta — Manual</h1>
          <p>
            Admin escolhe a cota no inventário e grava a venda no braço (WhatsApp, ligação, reunião). Sem robô — uma
            cota por vez. Entrada já considera markup/comissão do fornecedor.
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
                  setQuotaId("");
                }}
              >
                <option value="REAL_ESTATE">Imóvel</option>
                <option value="VEHICLE">Veículo</option>
              </select>
            </label>
            <label className="marketplace-field marketplace-field-wide">
              Cota
              <select value={quotaId} onChange={(e) => setQuotaId(e.target.value)} required>
                <option value="">Selecione a cota</option>
                {cotas.map((c) => (
                  <option key={c.quota_id} value={c.quota_id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            {selected && (
              <div className="notice" style={{ width: "100%" }}>
                Crédito {brl.format(Number(selected.credit_value))} · Entrada efetiva{" "}
                {brl.format(Number(selected.entrada_final))} · Parcela {brl.format(Number(selected.installment_value))} ·
                Nina {selected.nina_scan_status ?? "PENDENTE"}
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
              <CurrencyInput value={income} onChange={setIncome} />
            </label>
          </div>

          <div className="marketplace-form-row">
            <label className="marketplace-field marketplace-field-compact">
              CEP
              <input value={zipcode} onChange={(e) => setZipcode(e.target.value)} required minLength={8} />
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

          <button type="submit" className="marketplace-submit" disabled={busy || !quotaId}>
            <RefreshCw />
            {busy ? "Gravando…" : "Gravar venda"}
          </button>
        </form>
      </section>
    </>
  );
}
