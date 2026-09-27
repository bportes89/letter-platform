"use client";

import { LockKeyhole } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { getToken, login, api, User, LoginChallengeError } from "@/lib/api";
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
  loginHeadingForPortal,
  loginPortalMismatchMessage,
  loginPortalOption,
  parseLoginPortalKey,
  portalKeyForRole,
  roleMatchesLoginPortal,
} from "@/lib/login-portals";

async function redirectAfterLogin(
  user: User,
  nextPath: string | null,
  chatLeadId: string | null,
  portalKey: LoginPortalKey,
) {
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
  /** Tela dedicada /login/operacao */
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
  const [emailOtp, setEmailOtp] = useState("");
  const [mfaOtp, setMfaOtp] = useState("");
  const [step, setStep] = useState<"password" | "email_otp" | "mfa">("password");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  const heading = useMemo(() => loginHeadingForPortal(portalKey), [portalKey]);
  const portalOptions = operacaoOnly ? [loginPortalOption("operacao")] : LOGIN_PORTAL_PUBLIC_OPTIONS;

  useEffect(() => {
    if (operacaoOnly) return;
    setPortalKey(portalFromUrl);
  }, [portalFromUrl, operacaoOnly]);

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
        if (e instanceof Error && e.message.includes("cadastrado como")) {
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

  async function completeLogin() {
    const user = await api<User>("/auth/me");
    const stored =
      leadIdFromUrl ||
      (typeof window !== "undefined" ? sessionStorage.getItem("letter_chat_lead_id") : null);
    await redirectAfterLogin(user, nextPath, stored, portalKey);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
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

  return (
    <form className="site-login-card" onSubmit={submit}>
      <p className="site-kicker">Acesso restrito</p>
      <h1>{heading.title}</h1>
      <p>{heading.subtitle}</p>
      {nextPath && (
        <p className="site-login-note">Após o login você será direcionado para a página solicitada.</p>
      )}

      <label>
        Como você acessa a LETTER?
        <select
          value={portalKey}
          disabled={operacaoOnly || passwordLocked}
          onChange={(e) => {
            const key = parseLoginPortalKey(e.target.value);
            setPortalKey(key);
            syncPortalInUrl(key);
          }}
        >
          {portalOptions.map((opt) => (
            <option key={opt.key} value={opt.key}>
              {opt.label}
            </option>
          ))}
        </select>
        <small>{loginPortalOption(portalKey).description}</small>
      </label>

      <label>
        E-mail
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          type="email"
          name="email"
          autoComplete="username"
          required
          readOnly={passwordLocked}
        />
      </label>
      <label>
        Senha
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          type="password"
          name="password"
          autoComplete="current-password"
          minLength={8}
          required
          readOnly={passwordLocked}
        />
      </label>

      {step === "email_otp" && (
        <label>
          Código enviado por e-mail
          <small>Digite os 6 dígitos que enviamos para {email}</small>
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
        <label>
          Código do autenticador
          <small>Use o app Google Authenticator, Microsoft Authenticator ou similar</small>
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

      {notice && <p className="site-login-note">{notice}</p>}
      {error && <p className="site-error">{error}</p>}

      <button className="site-submit" type="submit" disabled={loading} style={{ width: "100%" }}>
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
          className="site-login-back"
          style={{ border: 0, background: "none", cursor: "pointer", padding: 0 }}
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

      <p className="site-login-note">
        <LockKeyhole size={14} aria-hidden />
        Ambiente protegido e monitorado
      </p>

      {!operacaoOnly && (
        <Link href="/login/operacao" className="site-login-back">
          Sou da operação LETTER (admin / equipe interna) →
        </Link>
      )}
      {operacaoOnly && (
        <Link href="/login?portal=cliente" className="site-login-back">
          ← Voltar ao login de clientes e parceiros
        </Link>
      )}

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
