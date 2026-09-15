"use client";

import { Copy, Link2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type NetworkReferral } from "@/lib/api";

const LINK_ITEMS: { key: keyof NetworkReferral["links"]; label: string }[] = [
  { key: "cadastro", label: "Cadastro de cliente" },
  { key: "vender_cota", label: "Vender minha cota" },
  { key: "site", label: "Site LETTER (chat e simulador)" },
];

export function ReferralLinksPanel({
  onMessage,
  variant = "partner",
}: {
  onMessage: (message: string) => void;
  variant?: "partner" | "client";
}) {
  const [referral, setReferral] = useState<NetworkReferral | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    api<NetworkReferral>("/network/me/referral")
      .then(setReferral)
      .catch(() => setReferral(null))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function copyText(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text);
      onMessage(`${label} copiado para a área de transferência.`);
    } catch {
      onMessage("Não foi possível copiar automaticamente. Selecione e copie o texto manualmente.");
    }
  }

  if (loading) {
    return (
      <section className="panel referral-panel">
        <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.875rem" }}>Carregando link de indicação…</p>
      </section>
    );
  }

  if (!referral) return null;

  return (
    <section className="panel referral-panel">
      <h2><Link2 /> Meu link de indicação</h2>
      <p style={{ marginTop: 0, color: "var(--muted)", fontSize: "0.875rem" }}>
        {variant === "client" || referral.propagator_mode
          ? "Compartilhe com amigos e familiares. Quem se cadastrar pelo seu link entra na sua indicação e permanece vinculado ao parceiro LETTER que te atende."
          : "Compartilhe com clientes. Leads e cadastros feitos por esses links ficam vinculados à sua rede comercial."}
      </p>
      <div className="referral-code-row">
        <code className="referral-code">{referral.referral_code}</code>
        <button type="button" className="table-action" onClick={() => void copyText(referral.referral_code, "Código")}>
          <Copy /> Copiar código
        </button>
      </div>
      <div className="referral-links">
        {LINK_ITEMS.map((item) => (
          <div className="referral-link-row" key={item.key}>
            <div>
              <b>{item.label}</b>
              <small>{referral.links[item.key]}</small>
            </div>
            <button type="button" className="table-action" onClick={() => void copyText(referral.links[item.key], item.label)}>
              <Copy /> Copiar link
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
