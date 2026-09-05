"use client";

import Link from "next/link";
import { CheckCircle2 } from "lucide-react";
import { FormEvent, Suspense, useEffect, useState } from "react";
import "../../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import { api, getToken, type User } from "@/lib/api";
import { portalHomeForRole } from "@/lib/portal-routes";

type Profile = {
  document: string | null;
  phone: string | null;
  company_name: string | null;
  company_cnpj: string | null;
};

type WalletView = {
  has_subaccount: boolean;
  message: string;
  account?: { asaas_onboarding_url: string | null };
};

function AberturaContaForm() {
  const [user, setUser] = useState<User | null>(null);
  const [document, setDocument] = useState("");
  const [phone, setPhone] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [companyCnpj, setCompanyCnpj] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [onboardingUrl, setOnboardingUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      window.location.href = "/cadastro";
      return;
    }
    Promise.all([
      api<User>("/auth/me"),
      api<Profile>("/auth/me/profile"),
      api<WalletView>("/wallet/me"),
    ])
      .then(([me, profile, wallet]) => {
        setUser(me);
        if (wallet.has_subaccount) {
          window.location.href = portalHomeForRole(me.role);
          return;
        }
        setDocument(profile.document ?? "");
        setPhone(profile.phone ?? "");
        setCompanyName(profile.company_name ?? "");
        setCompanyCnpj(profile.company_cnpj ?? "");
        setOnboardingUrl(wallet.account?.asaas_onboarding_url ?? null);
      })
      .catch(() => {
        window.location.href = "/login";
      })
      .finally(() => setLoading(false));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    setSubmitting(true);
    try {
      await api("/auth/me/profile", {
        method: "PATCH",
        body: JSON.stringify({
          document: document.trim() || undefined,
          phone: phone.trim() || undefined,
          company_cnpj: companyCnpj.trim() || undefined,
          company_name: companyName.trim() || undefined,
        }),
      });
      const kyc = await api<{ message: string }>("/kyc/me/complete", { method: "POST" });
      const wallet = await api<WalletView>("/wallet/me");
      if (wallet.has_subaccount) {
        window.location.href = portalHomeForRole(user?.role);
        return;
      }
      setNotice(kyc.message);
      setOnboardingUrl(wallet.account?.asaas_onboarding_url ?? null);
      if (!wallet.account?.asaas_onboarding_url) {
        setError("Conta ainda em processamento. Revise CPF/CNPJ e celular ou tente novamente em instantes.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível abrir a conta");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="site-login-card">Preparando abertura da conta…</div>;
  }

  return (
    <form className="site-login-card" onSubmit={submit}>
      <p className="site-kicker">Passo 2 de 2 · Conta LETTER</p>
      <h1>Ative sua conta</h1>
      <p>
        Confirme seus dados para abrir a conta digital LETTER. Depois disso você entra no escritório com
        a carteira pronta para uso.
      </p>

      <label>
        CPF
        <input
          value={document}
          onChange={(e) => setDocument(e.target.value)}
          placeholder="Somente números ou formatado"
          required
        />
      </label>
      <label>
        Celular com DDD
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          type="tel"
          placeholder="(11) 99999-9999"
          required
          minLength={10}
        />
      </label>
      <label>
        Razão social
        <small>Opcional — preencha se for pessoa jurídica</small>
        <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
      </label>
      <label>
        CNPJ
        <small>Opcional — se informado, a conta será aberta em nome da empresa</small>
        <input value={companyCnpj} onChange={(e) => setCompanyCnpj(e.target.value)} />
      </label>

      {notice && (
        <div className="notice" style={{ margin: 0 }}>
          <CheckCircle2 size={16} />
          {notice}
        </div>
      )}
      {error && <p className="site-error">{error}</p>}

      {onboardingUrl && (
        <p className="site-login-note">
          Documentos adicionais:{" "}
          <a href={onboardingUrl} target="_blank" rel="noreferrer">abrir verificação</a>
          . Você já pode entrar no escritório — a conta será liberada após análise.
        </p>
      )}

      <button className="site-submit" type="submit" disabled={submitting} style={{ width: "100%" }}>
        {submitting ? "Abrindo conta LETTER…" : "Abrir minha conta LETTER"}
      </button>

      {onboardingUrl && user && (
        <button
          type="button"
          className="site-submit"
          style={{ width: "100%", marginTop: 8, background: "transparent", color: "inherit", border: "1px solid currentColor" }}
          onClick={() => { window.location.href = portalHomeForRole(user.role); }}
        >
          Ir para o escritório
        </button>
      )}

      <Link href="/" className="site-login-back">← Voltar ao site institucional</Link>
    </form>
  );
}

export default function AberturaContaPage() {
  return (
    <div className="site-root">
      <SiteNav />
      <main className="site-login-main">
        <Suspense fallback={<div className="site-login-card">Carregando…</div>}>
          <AberturaContaForm />
        </Suspense>
      </main>
    </div>
  );
}
