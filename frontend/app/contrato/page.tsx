"use client";

import Link from "next/link";
import { FormEvent, Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import "../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import { api, downloadApi, type User } from "@/lib/api";
import {
  acceptPlatformContract,
  fetchContractStatus,
  redirectAfterOnboarding,
  type ContractStatus,
} from "@/lib/contract-onboarding";
import { portalHomeForRole } from "@/lib/portal-routes";

function ContratoForm() {
  const searchParams = useSearchParams();
  const onboarding = searchParams.get("onboarding") === "1";

  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<ContractStatus | null>(null);
  const [profile, setProfile] = useState({
    phone: "",
    companyName: "",
    companyCnpj: "",
    companyAddress: "",
    companyCity: "",
    companyState: "",
  });
  const [scrollCompleted, setScrollCompleted] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const verificationReference = useMemo(
    () => `contract-${user?.id?.slice(0, 8) ?? "user"}-${Date.now()}`,
    [user?.id],
  );

  useEffect(() => {
    Promise.all([
      api<User>("/auth/me"),
      fetchContractStatus(),
      api<{
        phone: string | null;
        company_name: string | null;
        company_cnpj: string | null;
        company_address: string | null;
        company_city: string | null;
        company_state: string | null;
      }>("/auth/me/profile"),
    ])
      .then(([me, contractStatus, p]) => {
        setUser(me);
        setStatus(contractStatus);
        setProfile({
          phone: p.phone ?? "",
          companyName: p.company_name ?? "",
          companyCnpj: p.company_cnpj ?? "",
          companyAddress: p.company_address ?? "",
          companyCity: p.company_city ?? "",
          companyState: p.company_state ?? "",
        });
        if (!contractStatus.required || contractStatus.completed) {
          window.location.href = portalHomeForRole(me.role);
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Não foi possível carregar o contrato"));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!user || !status) return;
    setError("");
    setLoading(true);
    try {
      const result = await acceptPlatformContract({
        terms_accepted: termsAccepted,
        scroll_completed: scrollCompleted,
        verification_reference: verificationReference,
        phone: profile.phone,
        company_name: profile.companyName,
        company_cnpj: profile.companyCnpj,
        company_address: profile.companyAddress,
        company_city: profile.companyCity,
        company_state: profile.companyState,
      });
      if (result.completed) {
        await redirectAfterOnboarding(user.role);
        return;
      }
      setStatus(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível registrar o aceite");
    } finally {
      setLoading(false);
    }
  }

  if (!status) {
    return <div className="site-login-card">{error || "Carregando contrato…"}</div>;
  }

  return (
    <form className="site-login-card site-invite-card" onSubmit={submit}>
      <p className="eyebrow">Plataforma LETTER</p>
      <h1>{status.template_title ?? "Contrato da plataforma"}</h1>
      <p className="site-invite-lead">
        {onboarding
          ? "Última etapa antes do escritório: leia e aceite o contrato do seu perfil."
          : "Leia e aceite o contrato para continuar usando a plataforma."}
      </p>
      {user && (
        <p className="site-login-note">
          Perfil: <b>{user.role.replaceAll("_", " ")}</b> · {user.email}
        </p>
      )}

      <section className="site-contract-panel">
        <div className="site-contract-head">
          <div>
            <strong>{status.template_title}</strong>
            <small>{status.template_version}</small>
          </div>
          <button
            type="button"
            className="button button-small button-outline"
            onClick={() => void downloadApi("/contracts/me/preview", "contrato-preview.docx")}
          >
            Baixar .docx
          </button>
        </div>
        <div
          className="site-contract-scroll"
          onScroll={(e) => {
            const el = e.currentTarget;
            if (el.scrollTop + el.clientHeight >= el.scrollHeight - 24) setScrollCompleted(true);
          }}
        >
          {status.contract_excerpt}
        </div>
        <label className="site-checkbox-label">
          <input type="checkbox" checked={termsAccepted} onChange={(e) => setTermsAccepted(e.target.checked)} required />
          <span>Li e aceito o contrato acima, com validade jurídica e registro de evidências LETTER.</span>
        </label>
      </section>

      {status.requires_pj_fields && (
        <>
          <label>
            Razão social (PJ)
            <input value={profile.companyName} onChange={(e) => setProfile({ ...profile, companyName: e.target.value })} required />
          </label>
          <label>
            CNPJ
            <input value={profile.companyCnpj} onChange={(e) => setProfile({ ...profile, companyCnpj: e.target.value })} required />
          </label>
          <label>
            Endereço
            <input value={profile.companyAddress} onChange={(e) => setProfile({ ...profile, companyAddress: e.target.value })} required />
          </label>
          <label>
            Cidade
            <input value={profile.companyCity} onChange={(e) => setProfile({ ...profile, companyCity: e.target.value })} required />
          </label>
          <label>
            UF
            <input value={profile.companyState} onChange={(e) => setProfile({ ...profile, companyState: e.target.value })} maxLength={2} required />
          </label>
        </>
      )}

      <label>
        Celular cadastrado
        <input value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} type="tel" required />
      </label>

      {error && <p className="site-error">{error}</p>}

      <button className="site-submit" type="submit" disabled={loading || !scrollCompleted} style={{ width: "100%" }}>
        {loading ? "Registrando aceite…" : "Aceitar contrato e entrar no escritório"}
      </button>

      <Link href="/modules/my-wallet" className="site-login-back">
        ← Voltar ao BANK
      </Link>
    </form>
  );
}

export default function ContratoPage() {
  return (
    <div className="site-root">
      <SiteNav />
      <main className="site-login-main">
        <Suspense fallback={<div className="site-login-card">Carregando contrato…</div>}>
          <ContratoForm />
        </Suspense>
      </main>
    </div>
  );
}
