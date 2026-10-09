"use client";

import { useEffect, useState } from "react";
import { fetchPublicSpeLedger, type PublicSpeLedger } from "@/lib/public-site-api";

function formatPercent(value: string) {
  const n = Number(value);
  if (Number.isNaN(n)) return "—";
  return `${n.toFixed(2).replace(".", ",")}%`;
}

export function SpeLedgerCard() {
  const [ledger, setLedger] = useState<PublicSpeLedger | null>(null);

  useEffect(() => {
    void fetchPublicSpeLedger()
      .then(setLedger)
      .catch(() => setLedger(null));
  }, []);

  const pipeline = ledger?.pipeline_display ?? "—";
  const crivo = ledger ? formatPercent(ledger.estimated_crivo_percent) : "30,00%";
  const ltv = ledger ? formatPercent(ledger.max_ltv_percent) : "40,00%";
  const hash = ledger?.audit_hash ?? "—";

  return (
    <div className="ledger-card">
      <div className="ledger-head">
        <span>LETTER_SPE_LEDGER</span>
        <span className="live">
          <i /> SISTEMA ONLINE
        </span>
      </div>
      <div className="ledger-main">
        <span>Pipeline corporativo bruto</span>
        <strong>{pipeline}</strong>
        <small>em ativos sob análise estruturada (SDC + Flash Capital)</small>
      </div>
      <div className="ledger-stats">
        <div>
          <span>Crivo estimado</span>
          <strong>{crivo}</strong>
          <small>capacidade elegível</small>
        </div>
        <div>
          <span>LTV máximo</span>
          <strong className="blue">{ltv}</strong>
          <small>mitigação de risco</small>
        </div>
      </div>
      <div className="ledger-foot">
        <span>◆ AUDIT TRAIL ATIVO</span>
        <span>HASH {hash}</span>
      </div>
    </div>
  );
}
