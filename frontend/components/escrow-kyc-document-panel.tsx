"use client";

import { ExternalLink, RefreshCw, Upload } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, API_URL, EscrowAccount, getToken } from "@/lib/api";

type KycDocument = {
  id: string;
  title: string;
  type: string;
  status: string;
  onboarding_url?: string | null;
  accepts_api_upload?: boolean;
};

const IDENTITY_TYPES = new Set(["IDENTIFICATION", "IDENTIFICATION_SELFIE"]);

function isIdentityDoc(doc: KycDocument) {
  return IDENTITY_TYPES.has((doc.type || "").toUpperCase());
}

type Props = {
  accounts: EscrowAccount[];
};

export function EscrowKycDocumentPanel({ accounts }: Props) {
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "");
  const [documents, setDocuments] = useState<KycDocument[]>([]);
  const [identityOnboardingUrl, setIdentityOnboardingUrl] = useState<string | null>(null);
  const [hint, setHint] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadingId, setUploadingId] = useState<string | null>(null);

  const selected = accounts.find((a) => a.id === accountId) ?? null;

  const resolvedIdentityUrl = useMemo(() => {
    if (identityOnboardingUrl?.trim()) return identityOnboardingUrl.trim();
    const fromDoc = documents.map((d) => d.onboarding_url).find((u) => u && u.trim());
    return fromDoc?.trim() ?? null;
  }, [documents, identityOnboardingUrl]);

  const loadDocs = useCallback(async (id: string) => {
    if (!id) {
      setDocuments([]);
      setIdentityOnboardingUrl(null);
      return;
    }
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const data = await api<{
        items: KycDocument[];
        hint?: string | null;
        identity_onboarding_url?: string | null;
      }>(`/escrow/accounts/${id}/kyc/documents`);
      setDocuments(data.items ?? []);
      setHint(data.hint?.trim() ?? "");
      setIdentityOnboardingUrl(data.identity_onboarding_url?.trim() ?? null);
    } catch (e) {
      setDocuments([]);
      setIdentityOnboardingUrl(null);
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
    setNotice("");
    try {
      const result = await api<{ identity_onboarding_url?: string | null; hint?: string | null }>(
        `/escrow/accounts/${accountId}/kyc/sync`,
        { method: "POST", body: "{}" },
      );
      await loadDocs(accountId);
      if (result.identity_onboarding_url?.trim()) {
        setNotice("Link de verificação RG/selfie atualizado com o Asaas.");
      } else {
        setNotice("Sincronização concluída. Se o link de identidade não aparecer, aguarde 1–2 minutos e sincronize de novo.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao sincronizar documentos");
    } finally {
      setLoading(false);
    }
  }

  async function uploadDoc(docId: string, file: File, input?: HTMLInputElement | null) {
    if (!accountId) return;
    setUploadingId(docId);
    setError("");
    setNotice(`Enviando "${file.name}"…`);
    try {
      const data = new FormData();
      data.append("file", file, file.name);
      const token = getToken();
      const response = await fetch(`${API_URL}/escrow/accounts/${accountId}/kyc/documents/${encodeURIComponent(docId)}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: data,
      });
      const body: { detail?: string | { msg?: string }[]; message?: string } = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = body.detail;
        const message =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
              ? detail.map((item) => (typeof item === "string" ? item : item.msg || "")).filter(Boolean).join("; ")
              : "Falha no envio do documento";
        throw new Error(message);
      }
      setNotice(body.message || `Documento "${file.name}" enviado ao Asaas.`);
      await loadDocs(accountId);
    } catch (e) {
      setNotice("");
      setError(e instanceof Error ? e.message : "Falha no upload");
    } finally {
      setUploadingId(null);
      if (input) input.value = "";
    }
  }

  if (!accounts.length) return null;

  return (
    <section className="panel escrow-kyc-panel">
      <h3>Documentos KYC — subcontas (Admin)</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        <strong>Contrato social e PDFs:</strong> anexe aqui. <strong>RG e selfie:</strong> o Asaas não aceita upload pelo painel — use o{" "}
        <strong>link oficial</strong> (conta do titular em BANK ou link abaixo após sincronizar).
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
          <RefreshCw className={loading ? "spin" : undefined} />
          {loading ? "Sincronizando…" : "Sincronizar com Asaas"}
        </button>
      </div>
      {selected && <small className="muted">Conta: {selected.subaccount_name ?? selected.external_account_id}</small>}
      {resolvedIdentityUrl && (
        <div className="notice" style={{ marginTop: 10 }}>
          <strong>Verificação RG/selfie (link Asaas)</strong>
          <p style={{ margin: "6px 0 8px" }}>
            Abra no navegador do titular (celular recomendado), permita câmera e conclua o cadastro.
          </p>
          <a className="table-action" href={resolvedIdentityUrl} target="_blank" rel="noreferrer">
            <ExternalLink />
            Abrir link oficial de identidade
          </a>
        </div>
      )}
      {notice && !error && <div className="notice" style={{ marginTop: 10 }}>{notice}</div>}
      {error && <div className="error" style={{ marginTop: 10 }}>{error}</div>}
      {hint && !error && !resolvedIdentityUrl && <div className="notice" style={{ marginTop: 10 }}>{hint}</div>}
      {loading ? (
        <small className="muted">Carregando documentos…</small>
      ) : documents.length === 0 ? (
        <small className="muted">Nenhum documento listado. Use Sincronizar com Asaas para atualizar.</small>
      ) : (
        documents.map((doc) => {
          const identity = isIdentityDoc(doc);
          const docLink = doc.onboarding_url?.trim() || (identity ? resolvedIdentityUrl : null);
          const canUpload = Boolean(doc.accepts_api_upload) && !docLink && !identity;

          return (
            <div className="session-row" key={doc.id}>
              <div>
                <b>{doc.title}</b>
                <small>
                  Status: {doc.status}
                  {doc.type ? ` · ${doc.type}` : ""}
                  {identity ? " · somente link oficial" : ""}
                </small>
              </div>
              {docLink ? (
                <a className="table-action" href={docLink} target="_blank" rel="noreferrer">
                  <ExternalLink />
                  Link oficial
                </a>
              ) : canUpload ? (
                <label
                  className="table-action kyc-upload-trigger"
                  style={{ cursor: uploadingId === doc.id ? "wait" : "pointer", opacity: uploadingId === doc.id ? 0.7 : 1 }}
                >
                  <Upload />
                  {uploadingId === doc.id ? "Enviando…" : "Anexar PDF"}
                  <input
                    className="kyc-file-input"
                    type="file"
                    accept="application/pdf,.pdf"
                    disabled={uploadingId === doc.id}
                    onChange={(e) => {
                      const input = e.currentTarget;
                      const file = input.files?.[0];
                      if (file) void uploadDoc(doc.id, file, input).catch(() => undefined);
                    }}
                  />
                </label>
              ) : identity ? (
                <button type="button" className="table-action" disabled={loading} onClick={() => void syncDocs()}>
                  <RefreshCw />
                  Buscar link
                </button>
              ) : (
                <small className="muted">Aguardando análise</small>
              )}
            </div>
          );
        })
      )}
    </section>
  );
}
