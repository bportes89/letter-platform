"use client";

import { useEffect, useState } from "react";
import { BookOpen, KeyRound, ShieldCheck } from "lucide-react";
import { MfaGuidePanel } from "@/components/mfa-guide-panel";
import { MfaSetupPanel } from "@/components/mfa-setup-panel";
import { api, logout, User } from "@/lib/api";

type SegurancaTab = "guia" | "ativar";

export default function SegurancaPage() {
  const [user, setUser] = useState<User | null>(null);
  const [tab, setTab] = useState<SegurancaTab>("guia");

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
          <h1>Segurança da conta</h1>
          <p>
            No login, a <strong>verificação por e-mail (código de 6 dígitos)</strong> é a proteção principal da plataforma
            LETTER. O autenticador (TOTP) abaixo é <strong>opcional</strong> e recomendado para parceiros e gestores.
            {user.mfa_enabled ? " Seu autenticador está ativo." : " Você pode ativar o autenticador quando quiser."}
          </p>
        </div>
        <div className="operational-icon"><ShieldCheck /></div>
      </div>

      <div className="mfa-tabs" role="tablist" aria-label="Autenticação em duas etapas">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "guia"}
          className={tab === "guia" ? "mfa-tab active" : "mfa-tab"}
          onClick={() => setTab("guia")}
        >
          <BookOpen size={14} />
          Como funciona
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "ativar"}
          className={tab === "ativar" ? "mfa-tab active" : "mfa-tab"}
          onClick={() => setTab("ativar")}
        >
          <KeyRound size={14} />
          Ativar agora
        </button>
      </div>

      {tab === "guia" ? (
        <MfaGuidePanel onActivate={() => setTab("ativar")} />
      ) : (
        <MfaSetupPanel />
      )}
    </>
  );
}
