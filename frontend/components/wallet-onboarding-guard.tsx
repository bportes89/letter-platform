"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, logout, type User } from "@/lib/api";
import { portalHomeForRole, postSignupRedirectForRole } from "@/lib/portal-routes";

type WalletPeek = { has_subaccount: boolean };

const SKIP_PREFIXES = ["/cadastro", "/login", "/convite", "/recuperar-senha", "/seguranca"];

export function WalletOnboardingGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (SKIP_PREFIXES.some((p) => pathname.startsWith(p))) {
      setReady(true);
      return;
    }
    api<User>("/auth/me")
      .then(async (user) => {
        const onboarding = postSignupRedirectForRole(user.role);
        if (onboarding === portalHomeForRole(user.role)) {
          setReady(true);
          return;
        }
        const wallet = await api<WalletPeek>("/wallet/me");
        if (!wallet.has_subaccount) {
          window.location.href = "/cadastro/conta";
          return;
        }
        setReady(true);
      })
      .catch(() => logout());
  }, [pathname]);

  if (!ready) {
    return <div className="loading">Verificando sua conta LETTER…</div>;
  }

  return children;
}
