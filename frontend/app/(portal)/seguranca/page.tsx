"use client";

import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { MfaSetupPanel } from "@/components/mfa-setup-panel";
import { api, logout, User } from "@/lib/api";

export default function SegurancaPage() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => logout());
  }, []);

  if (!user) return <div className="loading">Carregando segurança da conta...</div>;

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">CONTA</span>
          <h1>Segurança</h1>
          <p>
            Ative o código validador (MFA) para proteger o acesso de <strong>{user.email}</strong>.
          </p>
        </div>
        <div className="operational-icon"><ShieldCheck /></div>
      </div>
      <MfaSetupPanel />
      <section className="panel">
        <h2>Como usar no login</h2>
        <p className="muted">
          Depois de ativar, na tela de login marque <strong>Já ativei o autenticador (código MFA)</strong> e informe o código do app.
        </p>
      </section>
    </>
  );
}
