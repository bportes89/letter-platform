"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, logout, type User } from "@/lib/api";

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
      .then(() => setReady(true))
      .catch(() => logout());
  }, [pathname]);

  if (!ready) {
    return <div className="loading">Verificando sua conta LETTER…</div>;
  }

  return children;
}
