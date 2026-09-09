"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  Landmark,
  ShieldCheck,
  Wallet,
  HandCoins,
  TrendingUp,
} from "lucide-react";
import { api, type Summary } from "@/lib/api";

const CONTROLS = [
  {
    href: "/modules/payments",
    title: "Pagamentos e escrow",
    text: "Pix, locks, payouts, estornos e conciliação Asaas.",
    icon: Landmark,
  },
  {
    href: "/modules/wallet",
    title: "Ledger e saldos",
    text: "Razão de dupla entrada, extratos e posições contábeis.",
    icon: Wallet,
  },
  {
    href: "/modules/collections",
    title: "Cobrança e inadimplência",
    text: "Régua de cobrança, mora e recuperação de crédito.",
    icon: HandCoins,
  },
  {
    href: "/modules/flash-invest",
    title: "Flash Invest",
    text: "Oportunidades, reservas e posições de investimento.",
    icon: TrendingUp,
  },
  {
    href: "/modules/my-wallet",
    title: "Carteira LETTER",
    text: "Conta digital, Pix e status de subconta do parceiro/cliente.",
    icon: Landmark,
  },
  {
    href: "/modules/operations",
    title: "Operações",
    text: "Jobs, retries, readiness e observabilidade do ambiente.",
    icon: Activity,
  },
] as const;

export function BankControlModule() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Summary>("/dashboard")
      .then(setSummary)
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar"));
  }, []);

  return (
    <div className="module-page">
      <div className="module-hero">
        <div>
          <p className="eyebrow">BANK · CONTROLE INTERNO</p>
          <h2>Gestão e auditoria do BANK</h2>
          <p>
            Painel interno para acompanhar ações, controles e operação da conta digital,
            escrow, ledger e produtos de investimento.
          </p>
        </div>
        <div className="module-checklist">
          <h3>Checklist operacional</h3>
          <span>
            <ShieldCheck /> Transações financeiras:{" "}
            {summary?.financial_transactions_enabled ? "liberadas" : "modo seguro"}
          </span>
          <span>
            <ShieldCheck /> Operações ativas: {summary?.active_operations ?? "—"}
          </span>
          <span>
            <ShieldCheck /> Propostas ativas: {summary?.active_proposals ?? "—"}
          </span>
        </div>
      </div>

      {error && <div className="notice">{error}</div>}

      <div className="backlog-grid" style={{ marginTop: 8 }}>
        {CONTROLS.map((item) => {
          const Icon = item.icon;
          return (
            <Link key={item.href} href={item.href} className="backlog-item">
              <span>
                <Icon size={16} />
              </span>
              <div>
                <strong>{item.title}</strong>
                <p>{item.text}</p>
              </div>
              <ArrowRight size={16} />
            </Link>
          );
        })}
      </div>
    </div>
  );
}
