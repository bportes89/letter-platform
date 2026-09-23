"use client";

import { Copy } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type NetworkReferral, type User } from "@/lib/api";
import { canUseReferralLink } from "@/lib/referral-access";

export function ReferralStickyBar({ user }: { user: User | null }) {
  const [referral, setReferral] = useState<NetworkReferral | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!canUseReferralLink(user?.role)) {
      setReferral(null);
      return;
    }
    api<NetworkReferral>("/network/me/referral")
      .then(setReferral)
      .catch(() => setReferral(null));
  }, [user?.role]);

  if (!referral) return null;

  const shareLink = referral.links.site;

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(shareLink);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2200);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="referral-sticky-bar" role="region" aria-label="Link de divulgação">
      <div className="referral-sticky-bar-inner">
        <span className="referral-sticky-bar-label">Meu link de indicação</span>
        <a className="referral-sticky-bar-url" href={shareLink} target="_blank" rel="noreferrer">
          {shareLink}
        </a>
        <button
          type="button"
          className="referral-sticky-bar-copy"
          onClick={() => void copyLink()}
          title="Copiar link de divulgação"
          aria-label="Copiar link de divulgação"
        >
          <Copy aria-hidden />
          {copied ? "Copiado" : "Copiar"}
        </button>
      </div>
    </div>
  );
}
