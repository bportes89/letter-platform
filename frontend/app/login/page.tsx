"use client";

import { LockKeyhole } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import "../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import { getToken, login, api, User } from "@/lib/api";
import { portalHomeForRole } from "@/lib/portal-routes";

function redirectAfterLogin(role: string, nextPath: string | null) {
  if (nextPath && nextPath.startsWith("/")) {
    window.location.href = nextPath;
    return;
  }
  window.location.href = portalHomeForRole(role);
}

function LoginForm() {
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next");
  const [email, setEmail] = useState("admin@letter.com.br");
  const [password, setPassword] = useState("Letter@123");
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!getToken()) return;
    api<User>("/auth/me")
      .then((user) => {
        redirectAfterLogin(user.role, nextPath);
      })
      .catch(() => {
        localStorage.removeItem("letter_access_token");
        localStorage.removeItem("letter_refresh_token");
      });
  }, [nextPath]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password, otp);
      const user = await api<User>("/auth/me");
      redirectAfterLogin(user.role, nextPath);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no acesso");
      setLoading(false);
    }
  }

  return (
    <form className="site-login-card" onSubmit={submit}>
      <p className="site-kicker">Acesso restrito</p>
      <h1>Área do cliente</h1>
      <p>Entre com credenciais corporativas para acompanhar operações, documentos e pareceres.</p>
      {nextPath && (
        <p className="site-login-note">Após o login você será direcionado para a biblioteca solicitada.</p>
      )}

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
      <Link href="/cadastro" className="site-login-back">
        Ainda não tem conta? Abra sua conta →
      </Link>
      <Link href="/recuperar-senha" className="site-login-back">
        Esqueci minha senha / Redefinir senha →
      </Link>
    </form>
  );
}

export default function LoginPage() {
  return (
    <div className="site-root">
      <SiteNav />

      <main className="site-login-main">
        <Suspense fallback={<div className="site-login-card">Carregando…</div>}>
          <LoginForm />
        </Suspense>
      </main>
    </div>
  );
}
