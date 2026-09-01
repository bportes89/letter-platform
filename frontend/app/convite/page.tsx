"use client";

import Link from "next/link";
import { FormEvent, Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import "../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import {
  acceptPartnerInvitation,
  fetchInvitationPreview,
  invitationContractPreviewUrl,
  type InvitationPreview,
} from "@/lib/public-site-api";
import { login } from "@/lib/api";
import { portalHomeForRole } from "@/lib/portal-routes";

function ConviteForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token")?.trim() ?? "";

  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [name, setName] = useState("");
  const [document, setDocument] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [companyCnpj, setCompanyCnpj] = useState("");
  const [companyAddress, setCompanyAddress] = useState("");
  const [companyCity, setCompanyCity] = useState("");
  const [companyState, setCompanyState] = useState("");
  const [password, setPassword] = useState("");
  const [scrollCompleted, setScrollCompleted] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const verificationReference = useMemo(
    () => `invite-${token.slice(0, 8)}-${Date.now()}`,
    [token],
  );

  useEffect(() => {
    if (!token) {
      setError("Link de convite inválido. Solicite um novo convite ao seu patrocinador.");
      return;
    }
    fetchInvitationPreview(token)
      .then(setPreview)
      .catch((e) => setError(e instanceof Error ? e.message : "Convite inválido ou expirado"));
  }, [token]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!preview || !token) return;
    setError("");
    setLoading(true);
    try {
      const user = await acceptPartnerInvitation({
        token,
        name,
        document,
        password,
        company_name: companyName,
        company_cnpj: companyCnpj,
        company_address: companyAddress,
        company_city: companyCity,
        company_state: companyState,
        terms_accepted: termsAccepted,
        scroll_completed: scrollCompleted,
        verification_reference: verificationReference,
      });
      await login(preview.email, password);
      window.location.href = portalHomeForRole(user.role);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível concluir o aceite");
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="site-login-card">
        <h1>Convite inválido</h1>
        <p className="site-error">Este link não contém um token de convite válido.</p>
        <Link href="/login" className="site-login-back">Ir para login →</Link>
      </div>
    );
  }

  return (
    <form className="site-login-card site-invite-card" onSubmit={submit}>
      <p className="eyebrow">Rede comercial LETTER</p>
      <h1>Aceite do contrato de parceiro</h1>
      {preview ? (
        <p className="site-invite-lead">
          Convite para <b>{preview.email}</b> como <b>{preview.role}</b>
          {preview.inviter_name ? <> · indicado por <b>{preview.inviter_name}</b></> : null}
        </p>
      ) : (
        <p className="site-invite-lead">Validando convite…</p>
      )}

      {preview?.contract_required && (
        <section className="site-contract-panel">
          <div className="site-contract-head">
            <div>
              <strong>{preview.contract_title}</strong>
              <small>{preview.contract_version}</small>
            </div>
            <a className="button button-small button-outline" href={invitationContractPreviewUrl(token)} target="_blank" rel="noopener noreferrer">
              Baixar .docx
            </a>
          </div>
          <div className="site-contract-scroll" onScroll={(e) => {
            const el = e.currentTarget;
            if (el.scrollTop + el.clientHeight >= el.scrollHeight - 24) setScrollCompleted(true);
          }}>
            {preview.contract_excerpt}
          </div>
          <label className="site-checkbox-label">
            <input type="checkbox" checked={scrollCompleted} onChange={(e) => setScrollCompleted(e.target.checked)} required />
            <span>Li integralmente o contrato de parceiro e manifesto ciência das condições comerciais e de compliance.</span>
          </label>
          <label className="site-checkbox-label">
            <input type="checkbox" checked={termsAccepted} onChange={(e) => setTermsAccepted(e.target.checked)} required />
            <span>Aceito o contrato de credenciamento com {preview.company_legal_name} (CNPJ {preview.company_cnpj}) e autorizo registro de evidência digital (IP, data, hash).</span>
          </label>
        </section>
      )}

      <div className="site-invite-grid">
        <label>
          Representante legal
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          CPF do representante
          <input value={document} onChange={(e) => setDocument(e.target.value)} required />
        </label>
        <label>
          Razão social (PJ parceira)
          <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} required />
        </label>
        <label>
          CNPJ
          <input value={companyCnpj} onChange={(e) => setCompanyCnpj(e.target.value)} required />
        </label>
        <label>
          Endereço
          <input value={companyAddress} onChange={(e) => setCompanyAddress(e.target.value)} required />
        </label>
        <label>
          Cidade
          <input value={companyCity} onChange={(e) => setCompanyCity(e.target.value)} required />
        </label>
        <label>
          UF
          <input value={companyState} onChange={(e) => setCompanyState(e.target.value.toUpperCase())} maxLength={2} required />
        </label>
        <label>
          Senha de acesso
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={10} required />
        </label>
      </div>

      {error && <p className="site-error">{error}</p>}

      <button className="site-submit" type="submit" disabled={loading || !preview}>
        {loading ? "Registrando aceite…" : "Aceitar contrato e entrar na plataforma"}
      </button>

      <Link href="/login" className="site-login-back">Já possui conta? Entrar →</Link>
    </form>
  );
}

export default function ConvitePage() {
  return (
    <div className="site-root">
      <SiteNav />
      <main className="site-login-main site-invite-main">
        <Suspense fallback={<div className="site-login-card">Carregando convite…</div>}>
          <ConviteForm />
        </Suspense>
      </main>
    </div>
  );
}
