"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, logout, User } from "@/lib/api";
import { portalHomeForRole } from "@/lib/portal-routes";

/** Rota legada — autenticador TOTP removido; login usa código por e-mail. */
export default function SegurancaPage() {
  const router = useRouter();

  useEffect(() => {
    api<User>("/auth/me")
      .then((user) => router.replace(portalHomeForRole(user.role)))
      .catch(() => logout());
  }, [router]);

  return <div className="loading">Redirecionando…</div>;
}
