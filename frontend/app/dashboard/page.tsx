"use client";

import { useEffect } from "react";
import { api, logout, User } from "@/lib/api";
import { portalHomeForRole } from "@/lib/portal-routes";
import {
  contractOnboardingPath,
  fetchContractStatus,
  shouldForceContractOnboarding,
} from "@/lib/contract-onboarding";
import {
  shouldForceWalletOnboarding,
  walletOnboardingPath,
  type WalletPeek,
} from "@/lib/wallet-onboarding";

/** Compatibilidade: /dashboard redireciona para o portal do perfil logado. */
export default function DashboardRedirectPage() {
  useEffect(() => {
    Promise.all([api<User>("/auth/me"), api<WalletPeek>("/wallet/me"), fetchContractStatus()])
      .then(([user, wallet, contract]) => {
        if (shouldForceWalletOnboarding(user.role, wallet)) {
          window.location.href = walletOnboardingPath();
          return;
        }
        if (shouldForceContractOnboarding(user.role, contract)) {
          window.location.href = contractOnboardingPath();
          return;
        }
        window.location.href = portalHomeForRole(user.role);
      })
      .catch(() => logout());
  }, []);

  return <div className="loading">Redirecionando para o seu portal...</div>;
}
