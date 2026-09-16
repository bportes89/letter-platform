"use client";

import { RefreshCw, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, API_URL, EscrowAccount, getToken } from "@/lib/api";

type KycDocument = {
  id: string;
  title: string;
  type: string;
  status: string;
  onboarding_url?: string | null;
  accepts_api_upload?: boolean;
};

type Props = {
  accounts: EscrowAccount[];
};

export function EscrowKycDocumentPanel({ accounts }: Props) {
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "");
  const [documents, setDocuments] = useState<KycDocument[]>([]);
  const [hint, setHint] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadingId, setUploadingId] = useState<string | null>(null);

  const selected = accounts.find((a) => a.id === accountId) ?? null;

  const loadDocs = useCallback(async (id: string) => {
    if (!id) {
      setDocuments([]);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await api<{ items: KycDocument[]; hint?: string | null }>(`/escrow/accounts/${id}/kyc/documents`);
      setDocuments(data.items ?? []);
      setHint(data.hint?.trim() ?? "");
    } catch (e) {
      setDocuments([]);
      setError(e instanceof Error ? e.message : "Falha ao carregar documentos KYC");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!accountId && accounts[0]?.id) {
      setAccountId(accounts[0].id);
      return;
    }
    if (accountId) void loadDocs(accountId);
  }, [accountId, accounts, loadDocs]);

  async function syncDocs() {
    if (!accountId) return;
    setLoading(true);
    setError("");
    try {
      await api(`/escrow/accounts/${accountId}/kyc/sync`, { method: "POST", body: "{}" });
      await loadDocs(accountId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao sincronizar documentos");
    } finally {
      setLoading(false);
    }
  }

  async function uploadDoc(docId: string, file: File) {
    if (!accountId) return;
    setUploadingId(docId);
    setError("");
    try {
      const data = new FormData();
      data.append("file", file, file.name);
      const token = getToken();
      const response = await fetch(`${API_URL}/escrow/accounts/${accountId}/kyc/documents/${encodeURIComponent(docId)}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: data,
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "Falha no envio do documento");
      await loadDocs(accountId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no upload");
    } finally {
      setUploadingId(null);
    }
  }

  if (!accounts.length) return null;

  return (
    <section className="panel escrow-kyc-panel">
      <h3>Documentos KYC — subcontas (Admin)</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Anexe documentos manualmente em cada subconta. RG/selfie podem exigir o fluxo Asaas quando o link oficial estiver disponível.
      </p>
      <div className="toolbar" style={{ marginBottom: 12 }}>
        <select value={accountId} onChange={(e) => setAccountId(e.target.value)}>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.subaccount_name ?? a.external_account_id.slice(-10)}
            </option>
          ))}
        </select>
        <button type="button" className="table-action" disabled={loading || !accountId} onClick={() => void syncDocs()}>
          <RefreshCw />
          Sincronizar
        </button>
      </div>
      {selected && <small className="muted">Conta: {selected.subaccount_name ?? selected.external_account_id}</small>}
      {error && <div className="error">{error}</div>}
      {hint && !error && <div className="notice">{hint}</div>}
      {loading ? (
        <small className="muted">Carregando documentos…</small>
      ) : documents.length === 0 ? (
        <small className="muted">Nenhum documento listado. Use Sincronizar para atualizar com o Asaas.</small>
      ) : (
        documents.map((doc) => (
          <div className="session-row" key={doc.id}>
            <div>
              <b>{doc.title}</b>
              <small>
                Status: {doc.status}
                {doc.type ? ` · ${doc.type}` : ""}
              </small>
            </div>
            {doc.onboarding_url ? (
              <a className="table-action" href={doc.onboarding_url} target="_blank" rel="noreferrer">Link oficial</a>
            ) : doc.accepts_api_upload ? (
              <>
                <button
                  type="button"
                  className="table-action"
                  disabled={uploadingId === doc.id}
                  onClick={() => {
                    const input = document.getElementById(`escrow-kyc-${doc.id}`) as HTMLInputElement | null;
                    input?.click();
                  }}
                >
                  <Upload />
                  {uploadingId === doc.id ? "Enviando…" : "Anexar"}
                </button>
                <input
                  id={`escrow-kyc-${doc.id}`}
                  type="file"
                  hidden
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void uploadDoc(doc.id, file);
                    e.target.value = "";
                  }}
                />
              </>
            ) : (
              <small className="muted">Somente link oficial</small>
            )}
          </div>
        ))
      )}
    </section>
  );
}
