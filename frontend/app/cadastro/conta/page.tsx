"use client";

import { Suspense, useEffect } from "react";
import "../../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import { getToken } from "@/lib/api";
import { walletOnboardingPath } from "@/lib/wallet-onboarding";

function RedirectToWalletOnboarding() {
  useEffect(() => {
    if (!getToken()) {
      window.location.href = "/cadastro";
      return;
    }
    window.location.href = walletOnboardingPath();
  }, []);

  return <div className="site-login-card">Redirecionando para abertura da conta LETTER…</div>;
}

export default function AberturaContaPage() {
  return (
    <div className="site-root">
      <SiteNav />
      <main className="site-login-main">
        <Suspense fallback={<div className="site-login-card">Carregando…</div>}>
          <RedirectToWalletOnboarding />
        </Suspense>
      </main>
    </div>
  );
}
