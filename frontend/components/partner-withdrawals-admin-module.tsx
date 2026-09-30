"use client";

import { WalletCards } from "lucide-react";
import { useState } from "react";
import { PartnerWithdrawalsAdminPanel } from "@/components/partner-withdrawals-admin-panel";

export function PartnerWithdrawalsAdminModule() {
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">FINANCEIRO</span>
          <h1>
            <WalletCards style={{ display: "inline", verticalAlign: "middle", marginRight: 8 }} />
            Saques — parceiros
          </h1>
          <p>Fila de pedidos do Bank legado (comissões AVAILABLE). Processamento manual via PIX.</p>
        </div>
      </div>
      {notice && <div className="notice">{notice}</div>}
      {error && <div className="error">{error}</div>}
      <PartnerWithdrawalsAdminPanel
        onNotice={(msg) => {
          setError("");
          setNotice(msg);
        }}
        onError={(msg) => {
          setNotice("");
          setError(msg);
        }}
      />
    </>
  );
}
