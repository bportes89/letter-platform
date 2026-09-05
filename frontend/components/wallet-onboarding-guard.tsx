"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, logout, type User } from "@/lib/api";
import {
  shouldForceWalletOnboarding,
  type WalletPeek,
  type WalletProfile,
} from "@/lib/wallet-onboarding";

const SKIP_PREFIXES = ["/cadastro", "/login", "/convite", "/recuperar-senha", "/seguranca"];

export function WalletOnboardingGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (SKIP_PREFIXES.some((p) => pathname.startsWith(p))) {
      setReady(true);
      return;
    }
    Promise.all([
      api<User>("/auth/me"),
      api<WalletProfile>("/auth/me/profile"),
      api<WalletPeek>("/wallet/me"),
    ])
      .then(([user, profile, wallet]) => {
        if (shouldForceWalletOnboarding(user.role, wallet, profile)) {
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
