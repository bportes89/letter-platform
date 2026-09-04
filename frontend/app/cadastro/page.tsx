"use client";

import Link from "next/link";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import "../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import {
  fetchPublicReferral,
  registerPublicClient,
  type PublicReferralPreview,
} from "@/lib/public-site-api";
import { api, getToken, type User } from "@/lib/api";
import { portalHomeForRole } from "@/lib/portal-routes";

function CadastroForm() {
  const searchParams = useSearchParams();
  const refFromUrl = searchParams.get("ref")?.trim() ?? "";

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [document, setDocument] = useState("");
  const [password, setPassword] = useState("");
  const [referralCode, setReferralCode] = useState(refFromUrl);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [referralPreview, setReferralPreview] = useState<PublicReferralPreview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!getToken()) return;
    api<User>("/auth/me")
      .then((user) => {
        window.location.href = portalHomeForRole(user.role);
      })
      .catch(() => {
        localStorage.removeItem("letter_access_token");
        localStorage.removeItem("letter_refresh_token");
      });
  }, []);

  useEffect(() => {
    setReferralCode(refFromUrl);
  }, [refFromUrl]);

  useEffect(() => {
    const code = referralCode.trim();
    if (code.length < 6) {
      setReferralPreview(null);
      return;
    }
    const timer = window.setTimeout(() => {
      fetchPublicReferral(code)
        .then(setReferralPreview)
        .catch(() => setReferralPreview(null));
    }, 400);
    return () => window.clearTimeout(timer);
  }, [referralCode]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await registerPublicClient({
        name,
        email,
        phone,
        password,
        document: document.trim() || undefined,
        referral_code: referralCode.trim() || undefined,
        terms_accepted: termsAccepted,
      });
      localStorage.setItem("letter_access_token", result.access_token);
      localStorage.setItem("letter_refresh_token", result.refresh_token);
      window.location.href = portalHomeForRole(result.user.role);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível concluir o cadastro");
      setLoading(false);
    }
  }

  return (
    <form className="site-login-card" onSubmit={submit}>
      <p className="site-kicker">Conta LETTER</p>
      <h1>Abra sua conta</h1>
      <p>
        Crie sua conta para acompanhar propostas, contratos e operações. Clientes novos e quem já tinha
        cadastro no sistema anterior podem usar este formulário — ao concluir, você entra automaticamente na
        área logada.
      </p>

      <label>
        Nome completo
        <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
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
          minLength={8}
        />
      </label>
      <label>
        CPF ou CNPJ
        <small>Opcional neste momento</small>
        <input value={document} onChange={(e) => setDocument(e.target.value)} />
      </label>
      <label>
        Senha
        <small>Mínimo de 10 caracteres</small>
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          type="password"
          minLength={10}
          required
        />
      </label>
      <label>
        Código do indicador
        <small>Opcional — preenchido automaticamente se você veio por link de indicação</small>
        <input
          value={referralCode}
          onChange={(e) => setReferralCode(e.target.value.toUpperCase())}
          placeholder="LTR-SAL-XXXXXXXXXX"
        />
      </label>
      {referralPreview?.valid && referralPreview.referrer_name && (
        <p className="site-referral-ok">Indicado por {referralPreview.referrer_name}</p>
      )}
      {referralPreview && !referralPreview.valid && referralCode.trim().length >= 6 && (
        <p className="site-error">{referralPreview.message ?? "Código de indicação não encontrado."}</p>
      )}

      <label className="site-checkbox-label">
        <input
          type="checkbox"
          checked={termsAccepted}
          onChange={(e) => setTermsAccepted(e.target.checked)}
          required
        />
        <span>Li e aceito os termos de uso e a política de privacidade da LETTER.</span>
      </label>

      {error && (
        <div className="site-error">
          <p>{error}</p>
          {error.toLowerCase().includes("faça login") && (
            <>
              <Link href="/login" className="site-login-back">
                Ir para o login →
              </Link>
              <Link href="/recuperar-senha" className="site-login-back">
                Redefinir senha →
              </Link>
            </>
          )}
        </div>
      )}

      <button className="site-submit" type="submit" disabled={loading} style={{ width: "100%" }}>
        {loading ? "Criando conta…" : "Criar minha conta"}
      </button>

      <p className="site-login-note">Já tem conta?</p>
      <Link href="/login" className="site-login-back">
        Entrar na plataforma →
      </Link>
      <Link href="/recuperar-senha" className="site-login-back">
        Esqueci minha senha / Redefinir senha →
      </Link>
      <Link href="/" className="site-login-back">
        ← Voltar ao site institucional
      </Link>
    </form>
  );
}

export default function CadastroPage() {
  return (
    <div className="site-root">
      <SiteNav />
      <main className="site-login-main">
        <Suspense fallback={<div className="site-login-card">Carregando…</div>}>
          <CadastroForm />
        </Suspense>
      </main>
    </div>
  );
}
