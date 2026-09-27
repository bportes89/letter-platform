"use client";

import { Eye, EyeOff, User as UserIcon } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { LetterLogo } from "@/components/brand/letter-logo";
import { getToken, login, api, type User, LoginChallengeError } from "@/lib/api";
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
import {
  type LoginPortalKey,
  LOGIN_PORTAL_PUBLIC_OPTIONS,
  loginPortalMismatchMessage,
  loginPortalOption,
  parseLoginPortalKey,
  portalKeyForRole,
  roleMatchesLoginPortal,
} from "@/lib/login-portals";

const REMEMBER_EMAIL_KEY = "letter_login_remember_email";

async function redirectAfterLogin(
  user: User,
  nextPath: string | null,
  chatLeadId: string | null,
  portalKey: LoginPortalKey,
) {
  if (loginPortalOption(portalKey).externalHref) {
    throw new Error("Fornecedores acessam pelo portal dedicado.");
  }
  if (!roleMatchesLoginPortal(user.role, portalKey)) {
    throw new Error(loginPortalMismatchMessage(user.role, portalKey));
  }

  if (user.role === "CLIENT" && chatLeadId) {
    try {
      await api("/marketplace/me/bind-chat-lead", {
        method: "POST",
        body: JSON.stringify({ chat_lead_id: chatLeadId }),
      });
      try {
        sessionStorage.removeItem("letter_chat_lead_id");
      } catch {
        /* ignore */
      }
    } catch {
      /* bind best-effort */
    }
  }
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
  if (user.role === "CLIENT" && chatLeadId) {
    window.location.href = "/modules/minhas-compras";
    return;
  }
  window.location.href = portalHomeForRole(user.role);
}

type Props = {
  operacaoOnly?: boolean;
};

export function LoginForm({ operacaoOnly = false }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next");
  const leadIdFromUrl = searchParams.get("lead_id")?.trim() || null;
  const portalFromUrl = parseLoginPortalKey(searchParams.get("portal"));

  const [portalKey, setPortalKey] = useState<LoginPortalKey>(operacaoOnly ? "operacao" : portalFromUrl);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(false);
  const [emailOtp, setEmailOtp] = useState("");
  const [mfaOtp, setMfaOtp] = useState("");
  const [step, setStep] = useState<"password" | "email_otp" | "mfa">("password");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  const portalOptions = operacaoOnly ? [loginPortalOption("operacao")] : LOGIN_PORTAL_PUBLIC_OPTIONS;

  useEffect(() => {
    if (operacaoOnly) return;
    setPortalKey(portalFromUrl);
  }, [portalFromUrl, operacaoOnly]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(REMEMBER_EMAIL_KEY);
      if (saved) {
        setEmail(saved);
        setRemember(true);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (leadIdFromUrl) {
      try {
        sessionStorage.setItem("letter_chat_lead_id", leadIdFromUrl);
      } catch {
        /* ignore */
      }
    }
  }, [leadIdFromUrl]);

  useEffect(() => {
    if (!getToken()) return;
    api<User>("/auth/me")
      .then((user) => {
        const key = roleMatchesLoginPortal(user.role, portalKey)
          ? portalKey
          : portalKeyForRole(user.role);
        const stored =
          leadIdFromUrl ||
          (typeof window !== "undefined" ? sessionStorage.getItem("letter_chat_lead_id") : null);
        return redirectAfterLogin(user, nextPath, stored, key);
      })
      .catch((e) => {
        if (e instanceof Error && e.message.includes("Área")) {
          setError(e.message);
          return;
        }
        localStorage.removeItem("letter_access_token");
        localStorage.removeItem("letter_refresh_token");
      });
  }, [nextPath, leadIdFromUrl, portalKey]);

  function syncPortalInUrl(key: LoginPortalKey) {
    if (operacaoOnly) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set("portal", key);
    router.replace(`/login?${params.toString()}`, { scroll: false });
  }

  function handlePortalChange(nextKey: LoginPortalKey) {
    const option = loginPortalOption(nextKey);
    if (option.externalHref) {
      window.location.href = option.externalHref;
      return;
    }
    setPortalKey(nextKey);
    syncPortalInUrl(nextKey);
  }

  function persistRememberEmail() {
    try {
      if (remember && email.trim()) {
        localStorage.setItem(REMEMBER_EMAIL_KEY, email.trim());
      } else {
        localStorage.removeItem(REMEMBER_EMAIL_KEY);
      }
    } catch {
      /* ignore */
    }
  }

  async function completeLogin() {
    const user = await api<User>("/auth/me");
    const stored =
      leadIdFromUrl ||
      (typeof window !== "undefined" ? sessionStorage.getItem("letter_chat_lead_id") : null);
    persistRememberEmail();
    await redirectAfterLogin(user, nextPath, stored, portalKey);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (loginPortalOption(portalKey).externalHref) return;
    setError("");
    setNotice("");
    setLoading(true);
    try {
      await login(email, password, {
        emailOtp: step === "email_otp" || step === "mfa" ? emailOtp : undefined,
        mfaOtp: step === "mfa" ? mfaOtp : undefined,
      });
      try {
        await completeLogin();
      } catch (inner) {
        localStorage.removeItem("letter_access_token");
        localStorage.removeItem("letter_refresh_token");
        throw inner;
      }
    } catch (e) {
      if (e instanceof LoginChallengeError) {
        if (e.kind === "email_otp") {
          setStep("email_otp");
          setNotice(e.message);
        } else {
          setStep("mfa");
          setError(e.message);
        }
      } else {
        setError(e instanceof Error ? e.message : "Falha no acesso");
      }
      setLoading(false);
    }
  }

  const passwordLocked = step !== "password";
  const operacaoTitle = operacaoOnly ? "Operação LETTER" : null;

  return (
    <form className="site-login-card site-login-card--portal" onSubmit={submit}>
      <div className="site-login-logo">
        <LetterLogo variant="official" theme="light" className="site-login-logo-img" priority />
      </div>

      {operacaoTitle && <h1 className="site-login-portal-title">{operacaoTitle}</h1>}

      <label className="site-login-area-label">
        Área: <span className="site-login-required">*</span>
        <select
          value={portalKey}
          disabled={operacaoOnly || passwordLocked}
          onChange={(e) => handlePortalChange(parseLoginPortalKey(e.target.value))}
          required
        >
          {portalOptions.map((opt) => (
            <option key={opt.key} value={opt.key}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>

      <label className="site-login-field-label">
        <span className="sr-only">E-mail</span>
        <div className="site-login-field-wrap">
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            name="email"
            placeholder="E-mail"
            autoComplete="username"
            required
            readOnly={passwordLocked}
          />
          <UserIcon className="site-login-field-icon" size={18} aria-hidden />
        </div>
      </label>

      <label className="site-login-field-label">
        <span className="sr-only">Senha</span>
        <div className="site-login-field-wrap">
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type={showPassword ? "text" : "password"}
            name="password"
            placeholder="Senha"
            autoComplete="current-password"
            minLength={8}
            required
            readOnly={passwordLocked}
          />
          <button
            type="button"
            className="site-login-field-toggle"
            onClick={() => setShowPassword((v) => !v)}
            aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
            tabIndex={-1}
          >
            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        </div>
      </label>

      {step === "email_otp" && (
        <label className="site-login-area-label">
          Código enviado por e-mail
          <small>Digite os 6 dígitos enviados para {email}</small>
          <input
            value={emailOtp}
            onChange={(e) => setEmailOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            placeholder="6 dígitos"
            required
            autoComplete="one-time-code"
            autoFocus
          />
        </label>
      )}

      {step === "mfa" && (
        <label className="site-login-area-label">
          Código do autenticador
          <small>App autenticador (6 dígitos)</small>
          <input
            value={mfaOtp}
            onChange={(e) => setMfaOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            placeholder="6 dígitos"
            required
            autoComplete="one-time-code"
            autoFocus
          />
        </label>
      )}

      {step === "password" && (
        <div className="site-login-row">
          <label className="site-login-remember">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
            Lembrar meus dados
          </label>
          <Link href="/recuperar-senha" className="site-login-recover">
            Recuperar senha
          </Link>
        </div>
      )}

      {notice && <p className="site-login-inline-note">{notice}</p>}
      {error && <p className="site-error">{error}</p>}
      {nextPath && step === "password" && (
        <p className="site-login-inline-note">Após entrar, você será direcionado à página solicitada.</p>
      )}

      <button className="site-submit site-submit--portal" type="submit" disabled={loading || !portalKey}>
        {loading
          ? "Autenticando…"
          : step === "password"
            ? "Entrar"
            : step === "email_otp"
              ? "Confirmar código do e-mail"
              : "Confirmar e entrar"}
      </button>

      {passwordLocked && (
        <button
          type="button"
          className="site-login-back site-login-back--portal"
          style={{ border: 0, background: "none", cursor: "pointer", width: "100%" }}
          onClick={() => {
            setStep("password");
            setEmailOtp("");
            setMfaOtp("");
            setNotice("");
            setError("");
          }}
        >
          ← Voltar e alterar e-mail ou senha
        </button>
      )}

      {!operacaoOnly && (
        <>
          <p className="site-login-signup">
            <Link href="/cadastro">Cadastre-se aqui</Link>
          </p>
          <Link href="/login/operacao" className="site-login-back site-login-back--portal">
            Acesso operação LETTER (admin) →
          </Link>
        </>
      )}
      {operacaoOnly && (
        <Link href="/login?portal=cliente" className="site-login-back site-login-back--portal">
          ← Voltar ao login geral
        </Link>
      )}
      <Link href="/" className="site-login-back site-login-back--portal">
        Voltar ao site institucional
      </Link>
    </form>
  );
}
