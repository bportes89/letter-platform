"use client";

import { Suspense } from "react";
import "../site.css";
import { SiteNav } from "@/components/public-site/simulator-section";
import { LoginForm } from "@/components/login-form";

export default function LoginPage() {
  return (
    <div className="site-root">
      <SiteNav />
      <main className="site-login-main site-login-main--portal">
        <Suspense fallback={<div className="site-login-card">Carregando…</div>}>
          <LoginForm />
        </Suspense>
      </main>
    </div>
  );
}
