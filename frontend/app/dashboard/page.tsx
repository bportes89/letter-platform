"use client";

import { useEffect } from "react";
import { api, logout, User } from "@/lib/api";
import { portalHomeForRole } from "@/lib/portal-routes";
import {
  shouldForceWalletOnboarding,
  walletOnboardingPath,
  type WalletPeek,
} from "@/lib/wallet-onboarding";

/** Compatibilidade: /dashboard redireciona para o portal do perfil logado. */
export default function DashboardRedirectPage() {
  useEffect(() => {
    Promise.all([api<User>("/auth/me"), api<WalletPeek>("/wallet/me")])
      .then(([user, wallet]) => {
        if (shouldForceWalletOnboarding(user.role, wallet)) {
          window.location.href = walletOnboardingPath();
          return;
        }
        window.location.href = portalHomeForRole(user.role);
      })
      .catch(() => logout());
  }, []);

  return <div className="loading">Redirecionando para o seu portal...</div>;
}
