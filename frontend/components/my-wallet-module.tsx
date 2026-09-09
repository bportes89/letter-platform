"use client";

import { CheckCircle2, Copy, Landmark, QrCode, RefreshCw, Send, Upload, Wallet } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { API_URL, api, getToken, type User } from "@/lib/api";
import { CurrencyInput } from "@/components/currency-input";
import {
  activateWalletAccount,
  redirectToPortalAfterWallet,
  walletActivationErrorMessage,
} from "@/lib/wallet-activation";
import { walletAccountReady } from "@/lib/wallet-onboarding";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export type WalletView = {
  has_subaccount: boolean;
  onboarding_complete?: boolean;
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
    boleto_issuance_enabled?: boolean;
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

type IssuedBoleto = {
  provider: string;
  payment_id: string;
  status: string;
  amount: string;
  due_date?: string | null;
  description?: string | null;
  customer_name?: string | null;
  customer_document?: string | null;
  invoice_url?: string | null;
  bank_slip_url?: string | null;
  identification_field?: string | null;
  barcode?: string | null;
};

type KycDocument = {
  id: string;
  title: string;
  type?: string;
  status: string;
  onboarding_url: string | null;
  accepts_api_upload: boolean;
};

type Profile = {
  document: string | null;
  phone: string | null;
  company_name: string | null;
  company_cnpj: string | null;
};

export function MyWalletModule() {
  const searchParams = useSearchParams();
  const onboarding = searchParams.get("onboarding") === "1" || searchParams.get("onboarding") === "kyc";
  const [wallet, setWallet] = useState<WalletView | null>(null);
  const [holderName, setHolderName] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileDocument, setProfileDocument] = useState("");
  const [profilePhone, setProfilePhone] = useState("");
  const [profileCnpj, setProfileCnpj] = useState("");
  const [profileCompany, setProfileCompany] = useState("");
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);
  const [boletos, setBoletos] = useState<IssuedBoleto[]>([]);
  const [lastBoleto, setLastBoleto] = useState<IssuedBoleto | null>(null);
  const [documents, setDocuments] = useState<KycDocument[]>([]);
  const [pixQr, setPixQr] = useState<{ payload?: string; encoded_image?: string | null } | null>(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploadingDocId, setUploadingDocId] = useState<string | null>(null);
  const [transferAmount, setTransferAmount] = useState("");
  const [billAmount, setBillAmount] = useState("");
  const [boletoAmount, setBoletoAmount] = useState("");
  const [boletoDueDate, setBoletoDueDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 3);
    return d.toISOString().slice(0, 10);
  });

  const load = useCallback(async () => {
    const [w, tx, docs, p, me, boletoList] = await Promise.all([
      api<WalletView>("/wallet/me"),
      api<{ items: WalletTransaction[] }>("/wallet/me/transactions").catch(() => ({ items: [] })),
      api<{ items: KycDocument[] }>("/wallet/me/kyc/documents").catch(() => ({ items: [] })),
      api<Profile>("/auth/me/profile").catch(() => null),
      api<User>("/auth/me").catch(() => null),
      api<{ items: IssuedBoleto[] }>("/wallet/me/boletos").catch(() => ({ items: [] })),
    ]);
    setWallet(w);
    setTransactions(tx.items ?? []);
    setDocuments(docs.items ?? []);
    setBoletos(boletoList.items ?? []);
    if (me?.name) setHolderName(me.name);
    if (p) {
      setProfile(p);
      setProfileDocument(p.document ?? "");
      setProfilePhone(p.phone ?? "");
      setProfileCnpj(p.company_cnpj ?? "");
      setProfileCompany(p.company_name ?? "");
    }
  }, []);

  useEffect(() => {
    load().catch((e) => setNotice(e instanceof Error ? e.message : "Falha ao carregar carteira")).finally(() => setLoading(false));
  }, [load]);

  async function syncWallet() {
    setNotice("");
    const w = await api<WalletView>("/wallet/me/sync", { method: "POST" });
    setWallet(w);
    await load();
    setNotice("Dados da conta LETTER atualizados.");
  }

  async function openWalletAccount() {
    if (!profile) return;
    setOpeningAccount(true);
    setNotice("");
    try {
      const result = await activateWalletAccount(
        {
          document: profileDocument,
          phone: profilePhone,
          companyName: profileCompany,
          companyCnpj: profileCnpj,
        },
        profile,
      );
      await load();
      const refreshed = await api<WalletView>("/wallet/me");
      const ready = refreshed.onboarding_complete ?? refreshed.has_subaccount;
      if (ready) {
        const me = await api<User>("/auth/me");
        await redirectToPortalAfterWallet(me.role);
        return;
      }
      setNotice(result.message || "Conta em abertura — conclua a verificação no BANK para acessar o portal.");
    } catch (e) {
      setNotice(walletActivationErrorMessage(e));
    } finally {
      setOpeningAccount(false);
    }
  }

  async function saveProfile(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await api("/auth/me/profile", {
      method: "PATCH",
      body: JSON.stringify({
        document: profileDocument || undefined,
        phone: profilePhone || undefined,
        company_cnpj: profileCnpj || undefined,
        company_name: profileCompany || undefined,
      }),
    });
    setNotice("Dados cadastrais atualizados. Agora conclua a verificação e abra sua conta.");
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
        amount: transferAmount,
        description: fd.get("description") || "Saque LETTER",
      }),
    });
    setNotice(`Transferência ${result.status} — ${brl.format(Number(result.amount))}`);
    setTransferAmount("");
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
        amount: billAmount,
        description: fd.get("description") || "Pagamento de conta",
      }),
    });
    setNotice(`Pagamento ${result.status} — ${brl.format(Number(result.amount))}`);
    setBillAmount("");
    e.currentTarget.reset();
    await load();
  }

  async function issueBoleto(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const result = await api<IssuedBoleto>("/wallet/me/boletos", {
      method: "POST",
      body: JSON.stringify({
        customer_name: fd.get("customer_name"),
        customer_document: fd.get("customer_document"),
        customer_email: fd.get("customer_email") || undefined,
        customer_phone: fd.get("customer_phone") || undefined,
        amount: boletoAmount,
        due_date: boletoDueDate,
        description: fd.get("description") || "Cobrança LETTER BANK",
      }),
    });
    setLastBoleto(result);
    setNotice(`Boleto emitido (${result.status}) — ${brl.format(Number(result.amount))}`);
    setBoletoAmount("");
    form.reset();
    await load();
  }

  async function uploadDoc(docId: string, file: File, input?: HTMLInputElement | null) {
    setUploadingDocId(docId);
    setNotice("");
    try {
      const data = new FormData();
      data.append("file", file);
      const token = getToken();
      const response = await fetch(`${API_URL}/wallet/me/kyc/documents/${docId}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: data,
      });
      let body: { detail?: string | { msg?: string }[]; message?: string; status?: string } = {};
      try {
        body = await response.json();
      } catch {
        body = {};
      }
      if (!response.ok) {
        const detail = body.detail;
        const message =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
              ? detail.map((item) => (typeof item === "string" ? item : item.msg || "")).filter(Boolean).join("; ")
              : "Falha no upload do documento";
        throw new Error(message);
      }
      setNotice(body.message || `Documento "${file.name}" enviado para análise.`);
      await load();
    } finally {
      setUploadingDocId(null);
      if (input) input.value = "";
    }
  }

  function copyText(value: string) {
    void navigator.clipboard.writeText(value);
    setNotice("Copiado para a área de transferência.");
  }

  if (loading) return <div className="loading">Carregando BANK...</div>;

  const bankReady = wallet ? walletAccountReady(wallet) : false;

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">CONTA DIGITAL</span>
          <h1>BANK</h1>
          <p>
            Saldo em conta, extrato, Pix, emissão e pagamento de boletos, dados bancários e abertura da sua
            conta digital LETTER — tudo em um só lugar.
          </p>
        </div>
        <div className="operational-icon"><Wallet /></div>
      </div>

      {(onboarding || !bankReady) && (
        <div className="notice">
          <CheckCircle2 />
          <div>
            <strong>Ative sua conta LETTER</strong>
            <p>
              {wallet?.has_subaccount
                ? "Sua conta foi criada — conclua a verificação e os documentos abaixo para liberar o acesso ao portal."
                : "Confirme CPF/CNPJ e celular abaixo e abra sua conta digital. Este é o mesmo fluxo do primeiro acesso — você pode concluir aqui no BANK a qualquer momento."}
            </p>
          </div>
        </div>
      )}

      <section className="panel operational-panel financial-panel">
        <div className="toolbar">
          <button onClick={() => void syncWallet()}><RefreshCw />Atualizar dados da conta</button>
          {!wallet?.has_subaccount && (
            <button
              disabled={openingAccount}
              onClick={() => void openWalletAccount()}
            >
              <CheckCircle2 />
              {openingAccount ? "Abrindo conta LETTER…" : "Abrir minha conta LETTER"}
            </button>
          )}
        </div>

        {notice && <div className="notice"><CheckCircle2 />{notice}</div>}
        {wallet && <div className="notice"><Landmark />{wallet.message}</div>}

        {!wallet?.has_subaccount && (
          <section className="panel">
            <h3>Dados para abertura da conta LETTER</h3>
            <p className="muted">
              Informe CPF válido (pessoa física) ou CNPJ válido (pessoa jurídica) e celular com DDD antes de concluir a verificação.
            </p>
            <form className="stack-form" onSubmit={(e) => void saveProfile(e).catch((err) => setNotice(err.message))}>
              <input
                value={profileDocument}
                onChange={(e) => setProfileDocument(e.target.value)}
                placeholder="CPF (somente números ou formatado)"
              />
              <input
                value={profilePhone}
                onChange={(e) => setProfilePhone(e.target.value)}
                placeholder="Celular com DDD"
                required
              />
              <input
                value={profileCompany}
                onChange={(e) => setProfileCompany(e.target.value)}
                placeholder="Razão social (opcional — PJ)"
              />
              <input
                value={profileCnpj}
                onChange={(e) => setProfileCnpj(e.target.value)}
                placeholder="CNPJ (opcional — PJ tem prioridade na conta LETTER)"
              />
              <button type="submit">Salvar dados cadastrais</button>
              <button
                type="button"
                disabled={openingAccount}
                onClick={() => void openWalletAccount()}
              >
                {openingAccount ? "Abrindo conta LETTER…" : "Abrir minha conta LETTER"}
              </button>
            </form>
          </section>
        )}

        {!wallet?.has_subaccount ? (
          <p className="muted">Complete o cadastro com CPF/CNPJ e conclua a verificação para visualizar agência, conta e Pix.</p>
        ) : (
          <>
            <div className="balance-grid">
              <div className="balance-card">
                <small>Saldo disponível</small>
                <b>{brl.format(Number(wallet.account?.available_balance ?? 0))}</b>
                <span>{wallet.account?.subaccount_name ?? "Subconta LETTER"}</span>
              </div>
              <div className="balance-card">
                <small>Verificação de identidade</small>
                <b>{wallet.account?.asaas_kyc_status ?? "PENDENTE"}</b>
                <span>Comercial: {wallet.account?.asaas_commercial_status ?? "—"}</span>
              </div>
              <div className="balance-card">
                <small>Tipo de conta</small>
                <b>{wallet.capabilities?.escrow_locked ? "Com Escrow" : "Normal"}</b>
                <span>{wallet.capabilities?.withdrawals_enabled ? "Saques liberados" : "Saques bloqueados"}</span>
              </div>
            </div>

            <section className="panel" style={{ marginTop: 16 }}>
              <h3>Dados bancários do cliente</h3>
              <p className="muted" style={{ marginTop: 0 }}>
                Dados da conta digital LETTER para recebimentos e identificação bancária.
              </p>
              <div className="escrow-grid">
                <div className="escrow-card">
                  <small>Titular</small>
                  <b>{profile?.company_name || holderName || wallet.account?.subaccount_name || "—"}</b>
                </div>
                <div className="escrow-card">
                  <small>CPF / CNPJ</small>
                  <b>{profile?.company_cnpj || profile?.document || "—"}</b>
                </div>
                <div className="escrow-card">
                  <small>Banco</small>
                  <b>{wallet.banking?.display_bank || wallet.banking?.bank_name || "LETTER / Asaas"}</b>
                  <span>Código: {wallet.banking?.bank_code || "—"}</span>
                </div>
                <div className="escrow-card">
                  <small>Agência</small>
                  <b>{wallet.banking?.agency || "Em processamento"}</b>
                </div>
                <div className="escrow-card">
                  <small>Conta corrente</small>
                  <b>{wallet.banking?.account_number || "Em processamento"}</b>
                  {wallet.banking?.account_number && (
                    <button className="table-action" onClick={() => copyText(wallet.banking!.account_number!)}>
                      <Copy />Copiar
                    </button>
                  )}
                </div>
                <div className="escrow-card">
                  <small>Chave Pix</small>
                  <b>{wallet.banking?.pix_key || "Não gerada"}</b>
                  {wallet.banking?.pix_key && (
                    <button className="table-action" onClick={() => copyText(wallet.banking!.pix_key!)}>
                      <Copy />Copiar
                    </button>
                  )}
                </div>
              </div>
              <div className="toolbar">
                {!wallet.banking?.pix_key && wallet.capabilities?.pix_key_enabled && (
                  <button onClick={() => void createPixKey().catch((e) => setNotice(e.message))}>
                    <QrCode />Gerar chave Pix
                  </button>
                )}
                {wallet.banking?.pix_key && (
                  <button onClick={() => void loadPixQr().catch((e) => setNotice(e.message))}>
                    <QrCode />Ver QR Code Pix
                  </button>
                )}
                <button onClick={() => void syncWallet()}>
                  <RefreshCw />Atualizar dados bancários
                </button>
              </div>
              {pixQr?.payload && (
                <div className="notice">
                  <small>Pix copia e cola</small>
                  <code style={{ display: "block", wordBreak: "break-all", marginTop: 8 }}>{pixQr.payload}</code>
                  <button className="table-action" onClick={() => copyText(pixQr.payload!)}>
                    <Copy />Copiar Pix
                  </button>
                </div>
              )}
            </section>

            {(wallet.account?.asaas_onboarding_url || documents.length > 0) && (
              <section className="panel">
                <h3>Documentação de verificação</h3>
                <p className="muted" style={{ marginTop: 0 }}>
                  Envie o contrato social e demais documentos em PDF (até 10 MB). Após o envio, o status muda para análise.
                </p>
                {wallet.account?.asaas_onboarding_url && (
                  <div className="notice">
                    Alguns documentos exigem o link oficial de verificação LETTER:{" "}
                    <a href={wallet.account.asaas_onboarding_url} target="_blank" rel="noreferrer">Abrir verificação</a>
                  </div>
                )}
                {documents.map((doc) => (
                  <div className="session-row" key={doc.id}>
                    <div>
                      <b>{doc.title}</b>
                      <small>
                        Status: {doc.status}
                        {doc.type ? ` · ${doc.type}` : ""}
                      </small>
                    </div>
                    {doc.onboarding_url ? (
                      <a className="table-action" href={doc.onboarding_url} target="_blank" rel="noreferrer">Enviar pelo link</a>
                    ) : doc.accepts_api_upload ? (
                      <label className="table-action" aria-busy={uploadingDocId === doc.id}>
                        <Upload />
                        {uploadingDocId === doc.id ? "Enviando…" : "Enviar PDF"}
                        <input
                          type="file"
                          accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                          hidden
                          disabled={uploadingDocId === doc.id}
                          onChange={(e) => {
                            const input = e.currentTarget;
                            const file = input.files?.[0];
                            if (!file) return;
                            void uploadDoc(doc.id, file, input).catch((err) =>
                              setNotice(err instanceof Error ? err.message : "Falha no upload"),
                            );
                          }}
                        />
                      </label>
                    ) : (
                      <small className="muted">Aguardando análise</small>
                    )}
                  </div>
                ))}
              </section>
            )}

            {wallet.capabilities?.withdrawals_enabled && (
              <form className="stack-form" onSubmit={(e) => void transfer(e).catch((err) => setNotice(err.message))}>
                <h3>Saque via Pix</h3>
                <input name="pix_key" placeholder="Chave Pix de destino (mesma titularidade)" required />
                <CurrencyInput value={transferAmount} onChange={setTransferAmount} placeholder="Valor (R$)" required />
                <input name="description" placeholder="Descrição (opcional)" />
                <button><Send />Transferir</button>
              </form>
            )}

            {(wallet.capabilities?.boleto_issuance_enabled ?? wallet.capabilities?.bill_payments_enabled) && (
              <form className="stack-form" onSubmit={(e) => void issueBoleto(e).catch((err) => setNotice(err.message))}>
                <h3>Emitir boleto</h3>
                <p className="muted" style={{ margin: 0 }}>
                  Gere uma cobrança por boleto para o pagador. Após emitir, compartilhe o link ou a linha digitável.
                </p>
                <input name="customer_name" placeholder="Nome do pagador" required />
                <input name="customer_document" placeholder="CPF ou CNPJ do pagador" required />
                <input name="customer_email" type="email" placeholder="E-mail do pagador (opcional)" />
                <input name="customer_phone" placeholder="Celular do pagador (opcional)" />
                <CurrencyInput value={boletoAmount} onChange={setBoletoAmount} placeholder="Valor (R$)" required />
                <label>
                  Vencimento
                  <input
                    type="date"
                    value={boletoDueDate}
                    onChange={(ev) => setBoletoDueDate(ev.target.value)}
                    required
                  />
                </label>
                <input name="description" placeholder="Descrição da cobrança (opcional)" />
                <button><Send />Emitir boleto</button>
              </form>
            )}

            {lastBoleto && (
              <section className="panel">
                <h3>Último boleto emitido</h3>
                <div className="escrow-grid">
                  <div className="escrow-card">
                    <small>Status</small>
                    <b>{lastBoleto.status}</b>
                  </div>
                  <div className="escrow-card">
                    <small>Valor</small>
                    <b>{brl.format(Number(lastBoleto.amount))}</b>
                  </div>
                  <div className="escrow-card">
                    <small>Vencimento</small>
                    <b>{lastBoleto.due_date || "—"}</b>
                  </div>
                  <div className="escrow-card">
                    <small>Pagador</small>
                    <b>{lastBoleto.customer_name || "—"}</b>
                    <span>{lastBoleto.customer_document || ""}</span>
                  </div>
                </div>
                {lastBoleto.identification_field && (
                  <div className="notice">
                    <small>Linha digitável</small>
                    <code style={{ display: "block", wordBreak: "break-all", marginTop: 8 }}>
                      {lastBoleto.identification_field}
                    </code>
                    <button className="table-action" onClick={() => copyText(lastBoleto.identification_field!)}>
                      <Copy />Copiar linha digitável
                    </button>
                  </div>
                )}
                <div className="toolbar">
                  {lastBoleto.invoice_url && (
                    <a className="table-action" href={lastBoleto.invoice_url} target="_blank" rel="noreferrer">
                      Abrir fatura
                    </a>
                  )}
                  {lastBoleto.bank_slip_url && (
                    <a className="table-action" href={lastBoleto.bank_slip_url} target="_blank" rel="noreferrer">
                      Abrir PDF do boleto
                    </a>
                  )}
                </div>
              </section>
            )}

            {wallet.capabilities?.bill_payments_enabled && (
              <form className="stack-form" onSubmit={(e) => void payBill(e).catch((err) => setNotice(err.message))}>
                <h3>Pagamento de contas</h3>
                <input name="barcode" placeholder="Linha digitável ou código de barras" required />
                <CurrencyInput value={billAmount} onChange={setBillAmount} placeholder="Valor (R$)" required />
                <input name="description" placeholder="Descrição (opcional)" />
                <button><Send />Pagar boleto</button>
              </form>
            )}

            {(wallet.capabilities?.boleto_issuance_enabled ?? wallet.capabilities?.bill_payments_enabled) && (
              <section className="panel">
                <div className="subheading">
                  <h2>Boletos emitidos</h2>
                  <button onClick={() => void load()}><RefreshCw />Atualizar</button>
                </div>
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Pagador</th>
                        <th>Vencimento</th>
                        <th>Status</th>
                        <th>Valor</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {boletos.length === 0 ? (
                        <tr>
                          <td colSpan={5}>
                            <small className="muted">Nenhum boleto emitido ainda.</small>
                          </td>
                        </tr>
                      ) : (
                        boletos.map((boleto) => (
                          <tr key={boleto.payment_id}>
                            <td>
                              <b>{boleto.customer_name || boleto.description || "Cobrança"}</b>
                              <small>{boleto.customer_document || boleto.payment_id}</small>
                            </td>
                            <td>{boleto.due_date || "—"}</td>
                            <td>
                              <span className="pill pill-pending">{boleto.status}</span>
                            </td>
                            <td>{brl.format(Number(boleto.amount))}</td>
                            <td>
                              {boleto.invoice_url ? (
                                <a className="table-action" href={boleto.invoice_url} target="_blank" rel="noreferrer">
                                  Abrir
                                </a>
                              ) : boleto.identification_field ? (
                                <button className="table-action" onClick={() => copyText(boleto.identification_field!)}>
                                  <Copy />Copiar
                                </button>
                              ) : null}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
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
