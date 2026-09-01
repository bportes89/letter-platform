"use client";

import { CheckCircle2, Copy, Landmark, QrCode, RefreshCw, Send, Upload, Wallet } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { API_URL, api, getToken } from "@/lib/api";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export type WalletView = {
  has_subaccount: boolean;
  message: string;
  kyc_case?: { id: string; status: string; risk_level: string | null; provider: string } | null;
  account?: {
    id: string;
    provider: string;
    subaccount_name: string | null;
    escrow_enabled: boolean;
    status: string;
    available_balance: string;
    locked_balance: string;
    asaas_kyc_status: string | null;
    asaas_commercial_status: string | null;
    asaas_onboarding_url: string | null;
  };
  banking?: {
    bank_code: string;
    bank_name: string;
    agency: string;
    account_number: string | null;
    pix_key: string | null;
    display_bank: string;
  };
  capabilities?: {
    deposits_enabled: boolean;
    withdrawals_enabled: boolean;
    bill_payments_enabled: boolean;
    pix_key_enabled: boolean;
    escrow_locked: boolean;
  };
};

type WalletTransaction = {
  id: string;
  type: string;
  label: string;
  amount: string;
  direction: "CREDIT" | "DEBIT";
  date: string;
};

type KycDocument = {
  id: string;
  title: string;
  status: string;
  onboarding_url: string | null;
  accepts_api_upload: boolean;
};

export function MyWalletModule() {
  const [wallet, setWallet] = useState<WalletView | null>(null);
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);
  const [documents, setDocuments] = useState<KycDocument[]>([]);
  const [pixQr, setPixQr] = useState<{ payload?: string; encoded_image?: string | null } | null>(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const [w, tx, docs] = await Promise.all([
      api<WalletView>("/wallet/me"),
      api<{ items: WalletTransaction[] }>("/wallet/me/transactions").catch(() => ({ items: [] })),
      api<{ items: KycDocument[] }>("/wallet/me/kyc/documents").catch(() => ({ items: [] })),
    ]);
    setWallet(w);
    setTransactions(tx.items ?? []);
    setDocuments(docs.items ?? []);
  }, []);

  useEffect(() => {
    load().catch((e) => setNotice(e instanceof Error ? e.message : "Falha ao carregar carteira")).finally(() => setLoading(false));
  }, [load]);

  async function syncWallet() {
    setNotice("");
    const w = await api<WalletView>("/wallet/me/sync", { method: "POST" });
    setWallet(w);
    await load();
    setNotice("Dados sincronizados com o Asaas.");
  }

  async function completeKyc() {
    const result = await api<{ message: string }>("/kyc/me/complete", { method: "POST" });
    setNotice(result.message);
    await load();
  }

  async function createPixKey() {
    const result = await api<{ pix_key: string; message: string; qr_code_payload?: string }>("/wallet/me/pix-key", { method: "POST" });
    setNotice(result.message);
    if (result.qr_code_payload) setPixQr({ payload: result.qr_code_payload });
    await load();
  }

  async function loadPixQr() {
    const qr = await api<{ payload?: string; encoded_image?: string | null }>("/wallet/me/pix-qrcode");
    setPixQr(qr);
  }

  async function transfer(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const result = await api<{ status: string; amount: string }>("/wallet/me/transfer", {
      method: "POST",
      body: JSON.stringify({
        pix_key: fd.get("pix_key"),
        amount: fd.get("amount"),
        description: fd.get("description") || "Saque LETTER",
      }),
    });
    setNotice(`Transferência ${result.status} — ${brl.format(Number(result.amount))}`);
    e.currentTarget.reset();
    await load();
  }

  async function payBill(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const result = await api<{ status: string; amount: string }>("/wallet/me/bill-payment", {
      method: "POST",
      body: JSON.stringify({
        barcode: fd.get("barcode"),
        amount: fd.get("amount"),
        description: fd.get("description") || "Pagamento de conta",
      }),
    });
    setNotice(`Pagamento ${result.status} — ${brl.format(Number(result.amount))}`);
    e.currentTarget.reset();
    await load();
  }

  async function uploadDoc(docId: string, file: File) {
    const data = new FormData();
    data.append("file", file);
    const token = getToken();
    const response = await fetch(`${API_URL}/wallet/me/kyc/documents/${docId}`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: data,
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Falha no upload");
    setNotice(body.message || "Documento enviado.");
    await load();
  }

  function copyText(value: string) {
    void navigator.clipboard.writeText(value);
    setNotice("Copiado para a área de transferência.");
  }

  if (loading) return <div className="loading">Carregando Minha Carteira...</div>;

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">CONTA DIGITAL</span>
          <h1>Minha Carteira</h1>
          <p>Dados bancários, Pix, extrato, KYC e operações da sua subconta Asaas.</p>
        </div>
        <div className="operational-icon"><Wallet /></div>
      </div>

      <section className="panel operational-panel financial-panel">
        <div className="toolbar">
          <button onClick={() => void syncWallet()}><RefreshCw />Sincronizar com Asaas</button>
          {!wallet?.has_subaccount && (
            <button onClick={() => void completeKyc().catch((e) => setNotice(e.message))}><CheckCircle2 />Concluir KYC e abrir subconta</button>
          )}
        </div>

        {notice && <div className="notice"><CheckCircle2 />{notice}</div>}
        {wallet && <div className="notice"><Landmark />{wallet.message}</div>}

        {!wallet?.has_subaccount ? (
          <p className="muted">Complete o cadastro com CPF/CNPJ e conclua o KYC para visualizar agência, conta e Pix.</p>
        ) : (
          <>
            <div className="balance-grid">
              <div className="balance-card">
                <small>Saldo disponível</small>
                <b>{brl.format(Number(wallet.account?.available_balance ?? 0))}</b>
                <span>{wallet.account?.subaccount_name ?? "Subconta LETTER"}</span>
              </div>
              <div className="balance-card">
                <small>KYC Asaas</small>
                <b>{wallet.account?.asaas_kyc_status ?? "PENDENTE"}</b>
                <span>Comercial: {wallet.account?.asaas_commercial_status ?? "—"}</span>
              </div>
              <div className="balance-card">
                <small>Tipo de conta</small>
                <b>{wallet.capabilities?.escrow_locked ? "Com Escrow" : "Normal"}</b>
                <span>{wallet.capabilities?.withdrawals_enabled ? "Saques liberados" : "Saques bloqueados"}</span>
              </div>
            </div>

            {wallet.banking && (
              <section className="panel">
                <h3>Dados bancários</h3>
                <div className="escrow-grid">
                  <div className="escrow-card">
                    <small>Banco</small>
                    <b>{wallet.banking.display_bank}</b>
                  </div>
                  <div className="escrow-card">
                    <small>Agência</small>
                    <b>{wallet.banking.agency}</b>
                  </div>
                  <div className="escrow-card">
                    <small>Conta corrente</small>
                    <b>{wallet.banking.account_number ?? "Aguardando Asaas"}</b>
                  </div>
                  <div className="escrow-card">
                    <small>Chave Pix</small>
                    <b>{wallet.banking.pix_key ?? "Não gerada"}</b>
                    {wallet.banking.pix_key && (
                      <button className="table-action" onClick={() => copyText(wallet.banking!.pix_key!)}><Copy />Copiar</button>
                    )}
                  </div>
                </div>
                <div className="toolbar">
                  {!wallet.banking.pix_key && wallet.capabilities?.pix_key_enabled && (
                    <button onClick={() => void createPixKey().catch((e) => setNotice(e.message))}><QrCode />Gerar chave Pix</button>
                  )}
                  {wallet.banking.pix_key && (
                    <button onClick={() => void loadPixQr().catch((e) => setNotice(e.message))}><QrCode />Ver QR Code Pix</button>
                  )}
                </div>
                {pixQr?.payload && (
                  <div className="notice">
                    <small>Pix copia e cola</small>
                    <code style={{ display: "block", wordBreak: "break-all", marginTop: 8 }}>{pixQr.payload}</code>
                    <button className="table-action" onClick={() => copyText(pixQr.payload!)}><Copy />Copiar Pix</button>
                  </div>
                )}
              </section>
            )}

            {(wallet.account?.asaas_onboarding_url || documents.length > 0) && (
              <section className="panel">
                <h3>Documentação KYC (Asaas)</h3>
                {wallet.account?.asaas_onboarding_url && (
                  <div className="notice">
                    Envie seus documentos pelo link oficial Asaas:{" "}
                    <a href={wallet.account.asaas_onboarding_url} target="_blank" rel="noreferrer">Abrir onboarding</a>
                  </div>
                )}
                {documents.map((doc) => (
                  <div className="session-row" key={doc.id}>
                    <div>
                      <b>{doc.title}</b>
                      <small>Status: {doc.status}</small>
                    </div>
                    {doc.onboarding_url ? (
                      <a className="table-action" href={doc.onboarding_url} target="_blank" rel="noreferrer">Enviar pelo link</a>
                    ) : doc.accepts_api_upload ? (
                      <label className="table-action">
                        <Upload />Enviar
                        <input type="file" accept=".pdf,.png,.jpg,.jpeg" hidden onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) void uploadDoc(doc.id, file).catch((err) => setNotice(err.message));
                        }} />
                      </label>
                    ) : null}
                  </div>
                ))}
              </section>
            )}

            {wallet.capabilities?.withdrawals_enabled && (
              <form className="stack-form" onSubmit={(e) => void transfer(e).catch((err) => setNotice(err.message))}>
                <h3>Saque via Pix</h3>
                <input name="pix_key" placeholder="Chave Pix de destino (mesma titularidade)" required />
                <input name="amount" type="number" min="0.01" step="0.01" placeholder="Valor" required />
                <input name="description" placeholder="Descrição (opcional)" />
                <button><Send />Transferir</button>
              </form>
            )}

            {wallet.capabilities?.bill_payments_enabled && (
              <form className="stack-form" onSubmit={(e) => void payBill(e).catch((err) => setNotice(err.message))}>
                <h3>Pagamento de contas</h3>
                <input name="barcode" placeholder="Linha digitável ou código de barras" required />
                <input name="amount" type="number" min="0.01" step="0.01" placeholder="Valor" required />
                <input name="description" placeholder="Descrição (opcional)" />
                <button><Send />Pagar boleto</button>
              </form>
            )}

            <section className="panel">
              <div className="subheading"><h2>Extrato de movimentações</h2><button onClick={() => void load()}><RefreshCw />Atualizar</button></div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead><tr><th>Data</th><th>Descrição</th><th>Tipo</th><th>Valor</th></tr></thead>
                  <tbody>
                    {transactions.length === 0 ? (
                      <tr><td colSpan={4}><small className="muted">Nenhuma movimentação registrada ainda.</small></td></tr>
                    ) : transactions.map((tx) => (
                      <tr key={tx.id}>
                        <td>{new Date(tx.date).toLocaleString("pt-BR")}</td>
                        <td><b>{tx.label}</b><small>{tx.type}</small></td>
                        <td><span className={`pill pill-${tx.direction === "CREDIT" ? "approved" : "pending"}`}>{tx.direction === "CREDIT" ? "Entrada" : "Saída"}</span></td>
                        <td>{tx.direction === "CREDIT" ? "+" : "-"}{brl.format(Number(tx.amount))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </section>
    </>
  );
}
