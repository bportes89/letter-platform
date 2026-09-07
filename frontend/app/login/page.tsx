"use client";

import { LockKeyhole } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import "../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import { getToken, login, api, User } from "@/lib/api";
import { portalHomeForRole } from "@/lib/portal-routes";
import {
  contractOnboardingPath,
  fetchContractStatus,
  shouldForceContractOnboarding,
} from "@/lib/contract-onboarding";
import {
  shouldForceWalletOnboarding,
  walletOnboardingPath,
  type WalletPeek,
} from "@/lib/wallet-onboarding";

async function redirectAfterLogin(user: User, nextPath: string | null) {
  const wallet = await api<WalletPeek>("/wallet/me");
  if (shouldForceWalletOnboarding(user.role, wallet)) {
    window.location.href = walletOnboardingPath();
    return;
  }
  const contract = await fetchContractStatus();
  if (shouldForceContractOnboarding(user.role, contract)) {
    window.location.href = contractOnboardingPath();
    return;
  }
  if (nextPath && nextPath.startsWith("/")) {
    window.location.href = nextPath;
    return;
  }
  window.location.href = portalHomeForRole(user.role);
}

function LoginForm() {
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next");
  const [email, setEmail] = useState("admin@letter.com.br");
  const [password, setPassword] = useState("Letter@123");
  const [otp, setOtp] = useState("");
  const [showMfa, setShowMfa] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!getToken()) return;
    api<User>("/auth/me")
      .then((user) => {
        redirectAfterLogin(user, nextPath);
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
      await login(email, password, showMfa ? otp : undefined);
      const user = await api<User>("/auth/me");
      await redirectAfterLogin(user, nextPath);
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
      <label className="site-login-mfa-toggle">
        <input
          type="checkbox"
          checked={showMfa}
          onChange={(e) => {
            setShowMfa(e.target.checked);
            if (!e.target.checked) setOtp("");
          }}
        />
        Já ativei a autenticação em duas etapas (código no celular)
      </label>
      {showMfa && (
        <label>
          Código do autenticador
          <small>Use o app Google Authenticator, Microsoft Authenticator ou similar</small>
          <input
            value={otp}
            onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            placeholder="6 dígitos"
            required
            autoComplete="one-time-code"
          />
        </label>
      )}

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
      <Link href="/recuperar-email" className="site-login-back">
        Não lembro meu e-mail →
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
