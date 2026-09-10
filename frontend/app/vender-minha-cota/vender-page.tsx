"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import "../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import { SiteFooter } from "@/components/public-site/site-footer";
import { CurrencyFormField } from "@/components/currency-input";
import {
  calculateVenderCota,
  fetchVenderCotaBootstrap,
  storeVenderCota,
  type VenderCotaBootstrap,
  type VenderCotaResult,
} from "@/lib/public-site-api";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export default function VenderMinhaCotaPage() {
  const searchParams = useSearchParams();
  const refCode = searchParams.get("ref")?.trim() ?? "";
  const [boot, setBoot] = useState<VenderCotaBootstrap | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VenderCotaResult | null>(null);
  const [done, setDone] = useState<{ message: string; offer_value: string } | null>(null);

  useEffect(() => {
    fetchVenderCotaBootstrap()
      .then(setBoot)
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar"));
  }, []);

  function formPayload(fd: FormData) {
    return {
      tipo_consorcio: String(fd.get("tipo_consorcio") || ""),
      administrator_id: String(fd.get("administrator_id") || "") || null,
      credit_value: fd.get("credit_value"),
      paid_value: fd.get("paid_value") || "0",
      outstanding_balance: fd.get("outstanding_balance") || "0",
      term_months: Number(fd.get("term_months") || 0),
      contemplated: fd.get("contemplated") === "1",
      contact_name: String(fd.get("contact_name") || ""),
      contact_email: String(fd.get("contact_email") || ""),
      contact_phone: String(fd.get("contact_phone") || ""),
      document: String(fd.get("document") || "") || null,
      person_type: String(fd.get("person_type") || "PF"),
      partner_referral_code: refCode || null,
    };
  }

  async function onCalculate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setNotice("");
    setDone(null);
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    try {
      const calc = await calculateVenderCota(formPayload(fd));
      setResult(calc.result);
      if (!calc.result.viable) {
        setError(calc.result.motivos.join(" ") || "Oferta inviável.");
        return;
      }
      setNotice(
        `Prévia: Letter pagaria ${brl.format(Number(calc.result.offer_value))} (${calc.result.offer_percent}% do crédito).`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no cálculo");
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    try {
      const stored = await storeVenderCota(formPayload(fd));
      setDone({ message: stored.message, offer_value: stored.offer_value });
      setResult(null);
      setNotice("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao enviar oferta");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="site-root">
      <main>
        <SiteNav />
        <section className="site-light-panel">
          <p className="eyebrow"><span /> Marketplace · compra de cota</p>
          <h1 style={{ fontSize: 34, margin: "8px 0 10px" }}>Venda sua cota contemplada</h1>
          <p className="site-light-muted" style={{ marginTop: 0 }}>
            Preencha os dados e veja na hora quanto a Letter pagaria. Só cotas contempladas; percentual sobre o crédito; pago acima de 35% → recusa.
          </p>
          {boot?.rules_summary && <p className="site-light-muted" style={{ fontSize: 13 }}>{boot.rules_summary}</p>}
          {error && <div className="error" style={{ marginBottom: 12 }}>{error}</div>}
          {notice && <div className="notice" style={{ marginBottom: 12 }}>{notice}</div>}

          {done ? (
            <div style={{ textAlign: "center", padding: "28px 12px" }}>
              <h2 style={{ color: "#008f5f" }}>Oferta enviada</h2>
              <p>Valor congelado pelo robô: <strong>{brl.format(Number(done.offer_value))}</strong></p>
              <p className="site-light-muted">{done.message}</p>
              <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 18 }}>
                <Link className="button" href="/login">Ir para o escritório</Link>
                <Link className="text-link" href="/">Voltar ao site</Link>
              </div>
            </div>
          ) : (
            <form className="stack-form" onSubmit={result?.viable ? onSubmit : onCalculate}>
              <label>
                Administradora
                <select name="administrator_id" required>
                  <option value="">Selecione</option>
                  {(boot?.administrators || []).map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              </label>
              <label>
                Tipo do consórcio
                <select name="tipo_consorcio" required>
                  <option value="">Selecione</option>
                  {(boot?.tipos || []).map((t) => (
                    <option key={t.id} value={t.id}>{t.label}</option>
                  ))}
                </select>
              </label>
              <label>
                Valor atual do crédito (R$)
                <CurrencyFormField name="credit_value" placeholder="Ex.: R$ 100.000,00" required />
              </label>
              <label>
                Total já pago em parcelas (R$)
                <CurrencyFormField name="paid_value" placeholder="Ex.: R$ 25.000,00" required />
              </label>
              <label>
                Saldo devedor total (R$)
                <CurrencyFormField name="outstanding_balance" placeholder="Ex.: R$ 75.000,00" />
              </label>
              <label>
                Prazo contratado (meses)
                <input name="term_months" type="number" min={1} max={9999} required placeholder="Ex.: 120" />
              </label>
              <label>
                Cota contemplada?
                <select name="contemplated" required defaultValue="1">
                  <option value="1">Sim</option>
                  <option value="0">Não</option>
                </select>
              </label>
              <hr />
              <label>Nome<input name="contact_name" required minLength={2} placeholder="Nome completo" /></label>
              <label>E-mail<input name="contact_email" type="email" required placeholder="voce@email.com" /></label>
              <label>Telefone / WhatsApp<input name="contact_phone" required placeholder="DDD + número" /></label>
              <label>
                Pessoa
                <select name="person_type" defaultValue="PF">
                  <option value="PF">Pessoa física</option>
                  <option value="PJ">Pessoa jurídica</option>
                </select>
              </label>
              <label>CPF/CNPJ<input name="document" placeholder="Opcional" /></label>

              {result?.viable && (
                <div className="notice">
                  Oferta prévia: <strong>{brl.format(Number(result.offer_value))}</strong>
                  {" "}({result.offer_percent}% do crédito · pago {result.paid_percent}%)
                  {result.range_name ? ` · ${result.range_name}` : ""}
                </div>
              )}

              <button type="submit" className="button" disabled={loading || !boot}>
                {loading ? "Processando…" : result?.viable ? "Enviar oferta" : "Calcular quanto a Letter paga"}
              </button>
              {result?.viable && (
                <button type="button" className="text-link" onClick={() => { setResult(null); setNotice(""); }}>
                  Recalcular
                </button>
              )}
            </form>
          )}
        </section>
        <SiteFooter />
      </main>
    </div>
  );
}
