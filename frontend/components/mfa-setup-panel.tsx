"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { KeyRound, ShieldCheck } from "lucide-react";
import { api, User } from "@/lib/api";

type MfaSetup = { secret: string; provisioning_uri: string };

export function MfaSetupPanel({ compact = false }: { compact?: boolean }) {
  const [user, setUser] = useState<User | null>(null);
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => api<User>("/auth/me").then(setUser), []);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Não foi possível carregar o perfil"));
  }, [load]);

  async function beginSetup() {
    setError("");
    setMessage("");
    try {
      const result = await api<MfaSetup>("/auth/mfa/setup", { method: "POST" });
      setSetup(result);
      setMessage("Escaneie o QR Code no app autenticador e confirme com o código de 6 dígitos.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível iniciar a configuração");
    }
  }

  async function enable(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const otp = String(new FormData(event.currentTarget).get("otp") ?? "");
    try {
      await api("/auth/mfa/enable", { method: "POST", body: JSON.stringify({ otp }) });
      setSetup(null);
      setMessage("Autenticação em duas etapas ativada. Nos próximos logins, marque a opção no login e informe o código do app.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Código inválido. Tente o código atual do app.");
    }
  }

  async function disable(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const otp = String(new FormData(event.currentTarget).get("otp") ?? "");
    try {
      await api("/auth/mfa/disable", { method: "POST", body: JSON.stringify({ otp }) });
      setMessage("Código validador desativado.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Código inválido");
    }
  }

  const qrUrl = setup
    ? `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(setup.provisioning_uri)}`
    : null;

  return (
    <section className="panel mfa-panel">
      {!compact && (
        <>
          <h2><KeyRound /> Ativar autenticação em duas etapas</h2>
          <p className="muted">
            Gere o código validador no celular com Google Authenticator, Microsoft Authenticator, Authy ou similar.
          </p>
        </>
      )}

      {user && (
        <p className="mfa-status">
          Status:{" "}
          <span className={`pill ${user.mfa_enabled ? "pill-approved" : ""}`}>
            {user.mfa_enabled ? "ATIVO" : "NÃO ATIVADO"}
          </span>
        </p>
      )}

      {message && <div className="notice"><ShieldCheck />{message}</div>}
      {error && <p className="site-error">{error}</p>}

      {user?.mfa_enabled ? (
        <form className="stack-form" onSubmit={disable}>
          <p className="muted">Para desativar, confirme com um código válido do autenticador.</p>
          <input name="otp" inputMode="numeric" placeholder="Código de 6 dígitos" required minLength={6} maxLength={6} />
          <button type="submit">Desativar código validador</button>
        </form>
      ) : !setup ? (
        <>
        <button className="admin-button" type="button" onClick={beginSetup}>
          <KeyRound /> Ativar código validador
        </button>
        {!compact && (
          <p className="muted mfa-hint">Nunca ativou antes? Veja a aba <strong>Como funciona</strong> com o passo a passo completo.</p>
        )}
        </>
      ) : (
        <form className="stack-form" onSubmit={enable}>
          <ol className="mfa-steps">
            <li>Instale um app autenticador no celular.</li>
            <li>Escaneie o QR Code ou copie a chave manualmente.</li>
            <li>Digite o código de 6 dígitos para confirmar.</li>
          </ol>
          {qrUrl && (
            <img className="mfa-qr" src={qrUrl} alt="QR Code para configurar autenticador LETTER" width={220} height={220} />
          )}
          <code className="secret-code">{setup.secret}</code>
          <input name="otp" inputMode="numeric" placeholder="Código de 6 dígitos" required minLength={6} maxLength={6} autoComplete="one-time-code" />
          <button type="submit">Confirmar e ativar</button>
        </form>
      )}
    </section>
  );
}
