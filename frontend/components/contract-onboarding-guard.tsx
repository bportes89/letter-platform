"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, logout, type User } from "@/lib/api";
import {
  fetchContractStatus,
  isContractOnboardingRoute,
  roleRequiresPlatformContract,
  shouldForceContractOnboarding,
  contractOnboardingPath,
} from "@/lib/contract-onboarding";
import {
  isWalletOnboardingRoute,
  shouldForceWalletOnboarding,
  walletOnboardingPath,
  type WalletPeek,
} from "@/lib/wallet-onboarding";

const SKIP_PREFIXES = ["/cadastro", "/login", "/convite", "/recuperar-senha", "/recuperar-email", "/seguranca"];

export function ContractOnboardingGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (SKIP_PREFIXES.some((p) => pathname.startsWith(p))) {
      setReady(true);
      return;
    }
    if (isWalletOnboardingRoute(pathname) || isContractOnboardingRoute(pathname)) {
      setReady(true);
      return;
    }
    Promise.all([api<User>("/auth/me"), api<WalletPeek>("/wallet/me"), fetchContractStatus()])
      .then(([user, wallet, contract]) => {
        if (shouldForceWalletOnboarding(user.role, wallet)) {
          window.location.href = walletOnboardingPath();
          return;
        }
        if (!roleRequiresPlatformContract(user.role)) {
          setReady(true);
          return;
        }
        if (shouldForceContractOnboarding(user.role, contract)) {
          window.location.href = contractOnboardingPath();
          return;
        }
        setReady(true);
      })
      .catch(() => logout());
  }, [pathname]);

  if (!ready) {
    return <div className="loading">Verificando contratos da plataforma…</div>;
  }

  return children;
}
