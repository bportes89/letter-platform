"use client";

import { ArrowRight, BadgeCheck, BrainCircuit, Building2, LockKeyhole, Network, WalletCards } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { getToken, login } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("admin@letter.com.br");
  const [password, setPassword] = useState("Letter@123");
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => { if (getToken()) window.location.href = "/dashboard"; }, []);

  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setLoading(true);
    try { await login(email, password, otp); window.location.href = "/dashboard"; }
    catch (e) { setError(e instanceof Error ? e.message : "Falha no acesso"); setLoading(false); }
  }

  return (
    <main className="login-shell">
      <section className="login-brand">
        <div className="brand-mark"><span>L</span> LETTER</div>
        <div className="hero-copy">
          <span className="eyebrow">FINANCIAL INFRASTRUCTURE</span>
          <h1>Operações estruturadas.<br/><em>Liquidez inteligente.</em></h1>
          <p>Um ecossistema completo para cotas contempladas, SDC, Flash Credit, funding, redes comerciais e proteção transacional.</p>
          <div className="feature-row">
            <span><LockKeyhole size={18}/> Escrow protegido</span>
            <span><BrainCircuit size={18}/> NINA Engine</span>
            <span><BadgeCheck size={18}/> Auditável</span>
          </div>
        </div>
        <div className="orb orb-one"/><div className="orb orb-two"/>
      </section>
      <section className="login-panel">
        <form className="login-card" onSubmit={submit}>
          <div className="mobile-logo">LETTER</div>
          <span className="eyebrow dark">ACESSO SEGURO</span>
          <h2>Bem-vindo à plataforma</h2>
          <p className="muted">Entre no seu escritório virtual para acompanhar todas as operações.</p>
          <label>E-mail corporativo<input value={email} onChange={e => setEmail(e.target.value)} type="email" required /></label>
          <label>Senha<input value={password} onChange={e => setPassword(e.target.value)} type="password" minLength={8} required /></label>
          <label>Código MFA <small className="muted">Preencha somente se estiver ativado</small><input value={otp} onChange={e => setOtp(e.target.value.replace(/\D/g,"").slice(0,6))} inputMode="numeric" placeholder="000000" /></label>
          {error && <div className="error">{error}</div>}
          <button className="primary-button" disabled={loading}>{loading ? "Autenticando..." : "Entrar na plataforma"}<ArrowRight size={18}/></button>
          <div className="secure-note"><LockKeyhole size={14}/> Ambiente protegido e monitorado</div>
        </form>
        <div className="product-icons"><Building2/><WalletCards/><Network/><BrainCircuit/></div>
      </section>
    </main>
  );
}
