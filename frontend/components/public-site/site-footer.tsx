"use client";

import { useEffect, useState } from "react";
import { api, CompanyProfile } from "@/lib/api";

const FALLBACK: CompanyProfile = {
  legal_name: "LETTER FRANQUEADORA LTDA",
  trade_name: "LETTER",
  cnpj: "57.255.607/0001-30",
  footer_line: "LETTER FRANQUEADORA LTDA · CNPJ 57.255.607/0001-30",
};

export function SiteFooter() {
  const [profile, setProfile] = useState<CompanyProfile>(FALLBACK);

  useEffect(() => {
    void api<CompanyProfile>("/platform/company-profile")
      .then(setProfile)
      .catch(() => undefined);
  }, []);

  return (
    <footer className="site-footer">
      <a href="/" className="logo" aria-label="LETTER — início">
        <img
          className="logo-image logo-image-footer"
          src="/brand/letter-logo-oficial.png"
          alt="LETTER — O Shopping do Crédito Seguro e Inteligente"
        />
      </a>
      <p>Infraestrutura fiduciária e tecnologia para operações empresariais.</p>
      <p className="site-footer-legal">{profile.footer_line}</p>
      <div>
        <span>© {new Date().getFullYear()} {profile.trade_name || profile.legal_name}. Todos os direitos reservados.</span>
        <a href="/simulador/quitcon">Quitação consórcio</a>
        <a href="/login">Deal Room</a>
      </div>
    </footer>
  );
}
