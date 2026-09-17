"use client";

import { CheckCircle2, RefreshCw, Send } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { AdminWalletTransfer, api, EscrowAccount, EscrowAsaasStatus } from "@/lib/api";
import { CurrencyFormField } from "@/components/currency-input";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type WalletPixLookup = {
  pix_key: string;
  pix_key_type: string;
  owner_name: string;
  owner_document_masked?: string | null;
  institution_name?: string | null;
  valid: boolean;
};

type Props = {
  accounts: EscrowAccount[];
  asaas: EscrowAsaasStatus | null;
  formKey: number;
  transferring: boolean;
  onTransferring: (value: boolean) => void;
  onSuccess: (message: string) => void;
  onError: (message: string) => void;
};

export function AdminTransferForm({
  accounts,
  asaas,
  formKey,
  transferring,
  onTransferring,
  onSuccess,
  onError,
}: Props) {
  const [destinationType, setDestinationType] = useState("SUBACCOUNT");
  const [sourceId, setSourceId] = useState("");
  const [pixKey, setPixKey] = useState("");
  const [pixLookup, setPixLookup] = useState<WalletPixLookup | null>(null);
  const [pixLookupLoading, setPixLookupLoading] = useState(false);

  useEffect(() => {
    setDestinationType("SUBACCOUNT");
    setSourceId("");
    setPixKey("");
    setPixLookup(null);
  }, [formKey]);

  async function validatePixKey() {
    const key = pixKey.trim();
    if (key.length < 3) {
      onError("Informe a chave Pix antes de validar.");
      setPixLookup(null);
      return;
    }
    setPixLookupLoading(true);
    try {
      const params = new URLSearchParams({ pix_key: key });
      if (sourceId) params.set("source_escrow_account_id", sourceId);
      const result = await api<WalletPixLookup>(`/escrow/pix-key/lookup?${params.toString()}`);
      setPixLookup(result);
      setPixKey(result.pix_key);
      onSuccess(`Chave validada — recebedor: ${result.owner_name}`);
    } catch (err) {
      setPixLookup(null);
      onError(err instanceof Error ? err.message : "Não foi possível validar a chave Pix.");
    } finally {
      setPixLookupLoading(false);
    }
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (transferring) return;
    if (destinationType === "PIX" && !pixLookup?.valid) {
      onError("Valide a chave Pix e confira o nome do recebedor antes de enviar.");
      return;
    }
    onTransferring(true);
    onError("");
    const form = e.currentTarget;
    const fd = new FormData(form);
    try {
      const result = await api<AdminWalletTransfer>("/escrow/transfers", {
        method: "POST",
        body: JSON.stringify({
          source_escrow_account_id: sourceId || null,
          destination_type: destinationType,
          destination_escrow_account_id:
            destinationType === "SUBACCOUNT" ? String(fd.get("destination_escrow_account_id") || "") : null,
          pix_key: destinationType === "PIX" ? pixLookup?.pix_key ?? pixKey : null,
          pix_key_type: destinationType === "PIX" ? pixLookup?.pix_key_type : null,
          amount: fd.get("amount"),
          description: fd.get("description") || null,
        }),
      });
      onSuccess(
        `Transferência enviada: ${result.source_label} → ${result.destination_label} · ${brl.format(Number(result.amount))} · status ${result.status}.`,
      );
      form.reset();
      setSourceId("");
      setPixKey("");
      setPixLookup(null);
      setDestinationType("SUBACCOUNT");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Falha ao enviar dinheiro.");
    } finally {
      onTransferring(false);
    }
  }

  return (
    <form key={formKey} className="payout-form transfer-form" onSubmit={(ev) => void submit(ev)}>
      <h3>Enviar dinheiro</h3>
      <select
        name="source_escrow_account_id"
        value={sourceId}
        onChange={(ev) => {
          setSourceId(ev.target.value);
          setPixLookup(null);
        }}
      >
        <option value="">Carteira matriz LETTER{asaas?.balance ? ` · saldo ${asaas.balance}` : ""}</option>
        {accounts.map((a) => (
          <option key={a.id} value={a.id}>
            {a.subaccount_name ?? a.external_account_id.slice(-10)} · {brl.format(Number(a.available_balance))}
          </option>
        ))}
      </select>
      <select
        name="destination_type"
        value={destinationType}
        onChange={(ev) => {
          setDestinationType(ev.target.value);
          setPixLookup(null);
        }}
      >
        <option value="SUBACCOUNT">Para subconta interna</option>
        <option value="PIX">Para conta de terceiros (Pix)</option>
      </select>
      {destinationType === "SUBACCOUNT" ? (
        <select name="destination_escrow_account_id">
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.subaccount_name ?? a.external_account_id.slice(-10)}
            </option>
          ))}
        </select>
      ) : (
        <>
          <input
            value={pixKey}
            onChange={(ev) => {
              setPixKey(ev.target.value);
              setPixLookup(null);
            }}
            placeholder="Chave Pix do terceiro"
            required
          />
          <button type="button" disabled={pixLookupLoading} onClick={() => void validatePixKey()}>
            <RefreshCw />
            {pixLookupLoading ? "Validando chave…" : "Validar chave e ver recebedor"}
          </button>
          {pixLookup && (
            <div className="notice">
              <CheckCircle2 />
              <div>
                <strong>{pixLookup.owner_name}</strong>
                <p style={{ margin: "4px 0 0" }}>
                  {pixLookup.owner_document_masked && <span>Documento: {pixLookup.owner_document_masked} · </span>}
                  {pixLookup.institution_name && <span>{pixLookup.institution_name} · </span>}
                  Tipo: {pixLookup.pix_key_type}
                </p>
              </div>
            </div>
          )}
        </>
      )}
      <CurrencyFormField name="amount" placeholder="Valor (R$)" required />
      <input name="description" placeholder="Descrição (opcional)" />
      <button type="submit" disabled={transferring || (destinationType === "PIX" && !pixLookup?.valid)}>
        <Send />
        {transferring ? "Enviando..." : "Enviar dinheiro"}
      </button>
      <small className="muted">Matriz → subconta: crédito interno. Matriz ou subconta → Pix: saída para terceiros.</small>
    </form>
  );
}
