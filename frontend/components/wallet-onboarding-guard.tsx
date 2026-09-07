"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, logout, type User } from "@/lib/api";
import {
  isWalletOnboardingRoute,
  shouldForceWalletOnboarding,
  walletOnboardingPath,
  type WalletPeek,
} from "@/lib/wallet-onboarding";

const SKIP_PREFIXES = ["/cadastro", "/login", "/convite", "/recuperar-senha", "/recuperar-email", "/seguranca", "/contrato"];

export function WalletOnboardingGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (SKIP_PREFIXES.some((p) => pathname.startsWith(p))) {
      setReady(true);
      return;
    }
    if (isWalletOnboardingRoute(pathname)) {
      setReady(true);
      return;
    }
    Promise.all([api<User>("/auth/me"), api<WalletPeek>("/wallet/me")])
      .then(([user, wallet]) => {
        if (shouldForceWalletOnboarding(user.role, wallet)) {
          window.location.href = walletOnboardingPath();
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
