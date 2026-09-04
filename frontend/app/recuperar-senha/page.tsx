"use client";

import Link from "next/link";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import "../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import { confirmPasswordReset, requestPasswordReset } from "@/lib/public-site-api";

function RecuperarSenhaForm() {
  const searchParams = useSearchParams();
  const tokenFromUrl = searchParams.get("token")?.trim() ?? "";

  const [step, setStep] = useState<"request" | "confirm" | "done">("request");
  const [email, setEmail] = useState("");
  const [token, setToken] = useState(tokenFromUrl);
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (tokenFromUrl) {
      setToken(tokenFromUrl);
      setStep("confirm");
    }
  }, [tokenFromUrl]);

  async function submitRequest(event: FormEvent) {
    event.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);
    try {
      const result = await requestPasswordReset(email.trim());
      if (result.development_token) {
        setToken(result.development_token);
        setStep("confirm");
        setInfo("E-mail encontrado. Defina sua nova senha abaixo.");
      } else {
        setInfo(
          "Se o e-mail estiver cadastrado, você poderá redefinir a senha em instantes. Verifique também a caixa de spam.",
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível solicitar a redefinição");
    } finally {
      setLoading(false);
    }
  }

  async function submitConfirm(event: FormEvent) {
    event.preventDefault();
    setError("");
    setInfo("");
    if (password !== passwordConfirm) {
      setError("As senhas não coincidem.");
      return;
    }
    if (!token.trim()) {
      setError("Token de redefinição ausente. Solicite novamente pelo e-mail.");
      setStep("request");
      return;
    }
    setLoading(true);
    try {
      await confirmPasswordReset(token.trim(), password);
      setStep("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível redefinir a senha");
    } finally {
      setLoading(false);
    }
  }

  if (step === "done") {
    return (
      <div className="site-login-card">
        <p className="site-kicker">Conta LETTER</p>
        <h1>Senha atualizada</h1>
        <p>Sua senha foi redefinida com sucesso. Agora você pode entrar na plataforma.</p>
        <Link href="/login" className="site-submit" style={{ display: "block", textAlign: "center", textDecoration: "none" }}>
          Ir para o login
        </Link>
      </div>
    );
  }

  if (step === "confirm") {
    return (
      <form className="site-login-card" onSubmit={submitConfirm}>
        <p className="site-kicker">Conta LETTER</p>
        <h1>Redefinir senha</h1>
        <p>Escolha uma nova senha com no mínimo 10 caracteres.</p>
        {info && <p className="site-referral-ok">{info}</p>}

        <label>
          Nova senha
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            minLength={10}
            required
          />
        </label>
        <label>
          Confirmar nova senha
          <input
            value={passwordConfirm}
            onChange={(e) => setPasswordConfirm(e.target.value)}
            type="password"
            minLength={10}
            required
          />
        </label>

        {error && <p className="site-error">{error}</p>}

        <button className="site-submit" type="submit" disabled={loading} style={{ width: "100%" }}>
          {loading ? "Salvando…" : "Salvar nova senha"}
        </button>

        <button
          type="button"
          className="site-login-back"
          style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
          onClick={() => {
            setStep("request");
            setToken("");
            setPassword("");
            setPasswordConfirm("");
            setError("");
            setInfo("");
          }}
        >
          ← Usar outro e-mail
        </button>
      </form>
    );
  }

  return (
    <form className="site-login-card" onSubmit={submitRequest}>
      <p className="site-kicker">Conta LETTER</p>
      <h1>Redefinir senha</h1>
      <p>
        Informe o e-mail da sua conta. Se estiver cadastrado, você poderá definir uma nova senha na próxima etapa.
      </p>

      <label>
        E-mail da conta
        <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
      </label>

      {error && <p className="site-error">{error}</p>}
      {info && <p className="site-referral-ok">{info}</p>}

      <button className="site-submit" type="submit" disabled={loading} style={{ width: "100%" }}>
        {loading ? "Verificando…" : "Continuar"}
      </button>

      <Link href="/cadastro" className="site-login-back">
        Abrir conta →
      </Link>
      <Link href="/login" className="site-login-back">
        Já sei minha senha — entrar →
      </Link>
      <Link href="/" className="site-login-back">
        ← Voltar ao site institucional
      </Link>
    </form>
  );
}

export default function RecuperarSenhaPage() {
  return (
    <div className="site-root">
      <SiteNav />
      <main className="site-login-main">
        <Suspense fallback={<div className="site-login-card">Carregando…</div>}>
          <RecuperarSenhaForm />
        </Suspense>
      </main>
    </div>
  );
}
