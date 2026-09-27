"use client";

import { Suspense } from "react";
import "../../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import { LoginForm } from "@/components/login-form";

/** Login dedicado da operação LETTER (equipe interna / admin), como na plataforma legada. */
export default function OperacaoLoginPage() {
  return (
    <div className="site-root">
      <SiteNav />
      <main className="site-login-main site-login-main--portal">
        <Suspense fallback={<div className="site-login-card">Carregando…</div>}>
          <LoginForm operacaoOnly />
        </Suspense>
      </main>
    </div>
  );
}
