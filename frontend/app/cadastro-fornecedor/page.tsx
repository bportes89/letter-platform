"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import "../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import { registerPublicSupplier } from "@/lib/public-site-api";

export default function CadastroFornecedorPage() {
  const [personType, setPersonType] = useState<"PF" | "PJ">("PJ");
  const [name, setName] = useState("");
  const [tradeName, setTradeName] = useState("");
  const [document, setDocument] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await registerPublicSupplier({
        person_type: personType,
        name,
        trade_name: tradeName.trim() || undefined,
        document,
        email,
        phone,
        password,
        terms_accepted: termsAccepted,
      });
      localStorage.setItem("supplier_portal_token", result.portal_token);
      window.location.href = result.portal_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível concluir o cadastro");
      setLoading(false);
    }
  }

  return (
    <div className="site-root">
      <SiteNav />
      <main className="site-login-main">
        <form className="site-login-card" onSubmit={submit}>
          <p className="site-kicker">Marketplace · Fornecedor de cotas</p>
          <h1>Cadastre sua empresa</h1>
          <p>
            Abra o portal do fornecedor para confirmar transferências, acompanhar vendas e solicitar saques.
            Sua conta é ativada imediatamente após o cadastro.
          </p>

          <label>
            Tipo de pessoa
            <select value={personType} onChange={(e) => setPersonType(e.target.value as "PF" | "PJ")}>
              <option value="PJ">Pessoa jurídica (CNPJ)</option>
              <option value="PF">Pessoa física (CPF)</option>
            </select>
          </label>
          <label>
            {personType === "PJ" ? "Razão social" : "Nome completo"}
            <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
          </label>
          {personType === "PJ" && (
            <label>
              Nome fantasia
              <small>Opcional — usado para gerar o código interno do fornecedor</small>
              <input value={tradeName} onChange={(e) => setTradeName(e.target.value)} />
            </label>
          )}
          <label>
            {personType === "PJ" ? "CNPJ" : "CPF"}
            <input value={document} onChange={(e) => setDocument(e.target.value)} required minLength={11} />
          </label>
          <label>
            E-mail
            <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
          </label>
          <label>
            WhatsApp
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              type="tel"
              placeholder="(11) 99999-9999"
              required
              minLength={10}
            />
          </label>
          <label>
            Senha
            <small>Mínimo de 8 caracteres, com letras e números</small>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              minLength={8}
              required
            />
          </label>

          <label className="site-checkbox-label">
            <input
              type="checkbox"
              checked={termsAccepted}
              onChange={(e) => setTermsAccepted(e.target.checked)}
              required
            />
            <span>Li e aceito os termos de uso da LETTER para fornecedores do marketplace.</span>
          </label>

          {error && <div className="site-error"><p>{error}</p></div>}

          <button className="site-submit" type="submit" disabled={loading} style={{ width: "100%" }}>
            {loading ? "Criando conta…" : "Criar conta e entrar no portal"}
          </button>

          <p className="site-login-note">Já é fornecedor?</p>
          <Link href="/portal-fornecedor" className="site-login-back">
            Entrar no portal do fornecedor →
          </Link>
          <Link href="/" className="site-login-back">
            ← Voltar ao site institucional
          </Link>
        </form>
      </main>
    </div>
  );
}
