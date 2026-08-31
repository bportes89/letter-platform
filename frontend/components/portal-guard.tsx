"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, logout, User } from "@/lib/api";
import { portalHomeForRole, roleMatchesPortal, type PortalSlug } from "@/lib/portal-routes";

export function PortalGuard({
  slug,
  children,
}: {
  slug: PortalSlug;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    api<User>("/auth/me")
      .then((user) => {
        if (!roleMatchesPortal(user.role, slug)) {
          router.replace(portalHomeForRole(user.role));
          return;
        }
        setAllowed(true);
      })
      .catch(() => logout());
  }, [slug, router]);

  if (!allowed) {
    return <div className="loading">Carregando portal...</div>;
  }

  return children;
}
