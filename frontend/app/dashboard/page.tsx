"use client";

import { useEffect } from "react";
import { api, logout, User } from "@/lib/api";
import { portalHomeForRole } from "@/lib/portal-routes";

/** Compatibilidade: /dashboard redireciona para o portal do perfil logado. */
export default function DashboardRedirectPage() {
  useEffect(() => {
    api<User>("/auth/me")
      .then((user) => {
        window.location.href = portalHomeForRole(user.role);
      })
      .catch(() => logout());
  }, []);

  return <div className="loading">Redirecionando para o seu portal...</div>;
}
