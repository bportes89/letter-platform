"use client";

import { LockKeyhole } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import "../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import { getToken, login } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("admin@letter.com.br");
  const [password, setPassword] = useState("Letter@123");
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getToken()) window.location.href = "/dashboard";
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password, otp);
      window.location.href = "/dashboard";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no acesso");
      setLoading(false);
    }
  }

  return (
    <div className="site-root">
      <SiteNav />

      <main className="site-login-main">
        <form className="site-login-card" onSubmit={submit}>
          <p className="site-kicker">Acesso restrito</p>
          <h1>Área do cliente</h1>
          <p>Entre com credenciais corporativas para acompanhar operações, documentos e pareceres.</p>

          <label>
            E-mail corporativo
            <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
          </label>
          <label>
            Senha
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              minLength={8}
              required
            />
          </label>
          <label>
            Código MFA
            <small>Preencha somente se estiver ativado</small>
            <input
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric"
              placeholder="000000"
            />
          </label>

          {error && <p className="site-error">{error}</p>}

          <button className="site-submit" type="submit" disabled={loading} style={{ width: "100%" }}>
            {loading ? "Autenticando…" : "Entrar na plataforma"}
          </button>

          <p className="site-login-note">
            <LockKeyhole size={14} aria-hidden />
            Ambiente protegido e monitorado
          </p>

          <Link href="/" className="site-login-back">
            ← Voltar ao site institucional
          </Link>
        </form>
      </main>
    </div>
  );
}
