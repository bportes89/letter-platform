"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import "../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import { lookupAccountEmail } from "@/lib/public-site-api";

export default function RecuperarEmailPage() {
  const [document, setDocument] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ found: boolean; maskedEmail: string | null; message: string } | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const response = await lookupAccountEmail(document.trim(), phone.trim());
      setResult({
        found: response.found,
        maskedEmail: response.masked_email,
        message: response.message,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível consultar os dados");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="site-root">
      <SiteNav />
      <main className="site-login-main">
        {result?.found ? (
          <div className="site-login-card">
            <p className="site-kicker">Conta LETTER</p>
            <h1>E-mail localizado</h1>
            <p>{result.message}</p>
            <p className="site-referral-ok" style={{ fontSize: "1.15rem", fontWeight: 600 }}>
              {result.maskedEmail}
            </p>
            <p>Use esse e-mail para entrar na plataforma ou redefinir sua senha.</p>
            <Link href="/login" className="site-submit" style={{ display: "block", textAlign: "center", textDecoration: "none" }}>
              Ir para o login
            </Link>
            <Link href="/recuperar-senha" className="site-login-back">
              Redefinir senha →
            </Link>
            <button
              type="button"
              className="site-login-back"
              style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
              onClick={() => {
                setResult(null);
                setDocument("");
                setPhone("");
              }}
            >
              ← Consultar outro CPF
            </button>
          </div>
        ) : (
          <form className="site-login-card" onSubmit={submit}>
            <p className="site-kicker">Conta LETTER</p>
            <h1>Recuperar e-mail</h1>
            <p>
              Informe o CPF e o celular cadastrados na sua conta. Se os dados coincidirem, mostramos o e-mail mascarado
              para você entrar ou redefinir a senha.
            </p>

            <label>
              CPF
              <input
                value={document}
                onChange={(e) => setDocument(e.target.value)}
                type="text"
                inputMode="numeric"
                autoComplete="off"
                placeholder="000.000.000-00"
                required
              />
            </label>
            <label>
              Celular cadastrado
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                placeholder="(11) 90000-0000"
                required
              />
            </label>

            {result && !result.found && <p className="site-error">{result.message}</p>}
            {error && <p className="site-error">{error}</p>}

            <button className="site-submit" type="submit" disabled={loading} style={{ width: "100%" }}>
              {loading ? "Consultando…" : "Localizar e-mail"}
            </button>

            <Link href="/login" className="site-login-back">
              Já sei meu e-mail — entrar →
            </Link>
            <Link href="/recuperar-senha" className="site-login-back">
              Esqueci minha senha →
            </Link>
            <Link href="/cadastro" className="site-login-back">
              Abrir conta →
            </Link>
            <Link href="/" className="site-login-back">
              ← Voltar ao site institucional
            </Link>
          </form>
        )}
      </main>
    </div>
  );
}
