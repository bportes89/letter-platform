"use client";

import { Camera, ChevronLeft, ExternalLink, RefreshCw, Upload, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_URL, getToken } from "@/lib/api";

export type KycIdentityDocument = {
  id: string;
  title: string;
  type?: string;
  status: string;
  onboarding_url: string | null;
  accepts_api_upload: boolean;
  capture_mode?: "link" | "camera" | "file";
};

type Props = {
  documents: KycIdentityDocument[];
  identityOnboardingUrl?: string | null;
  onClose: () => void;
  onComplete: (message: string) => void;
};

type WizardMode = "choose" | "link" | "camera" | "waiting";

function pendingIdentityDocs(documents: KycIdentityDocument[]) {
  return documents.filter((doc) => {
    const type = (doc.type || "").toUpperCase();
    if (type !== "IDENTIFICATION" && type !== "IDENTIFICATION_SELFIE") return false;
    const status = (doc.status || "").toUpperCase();
    return status !== "APPROVED";
  });
}

async function uploadIdentityFile(docId: string, file: File): Promise<string> {
  const data = new FormData();
  data.append("file", file, file.name);
  const token = getToken();
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 90_000);
  let response: Response;
  try {
    response = await fetch(`${API_URL}/wallet/me/kyc/documents/${encodeURIComponent(docId)}`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: data,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Tempo esgotado no envio. Tente uma foto menor ou use a verificação pelo link.");
    }
    throw err;
  } finally {
    window.clearTimeout(timeout);
  }
  let body: { detail?: string | { msg?: string }[]; message?: string } = {};
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
          : `Falha no upload (${response.status})`;
    throw new Error(message);
  }
  return body.message || "Documento enviado para análise.";
}

export function KycIdentityWizard({ documents, identityOnboardingUrl, onClose, onComplete }: Props) {
  const identityDocs = useMemo(() => pendingIdentityDocs(documents), [documents]);
  const linkUrl = useMemo(
    () => identityOnboardingUrl || identityDocs.map((d) => d.onboarding_url).find(Boolean) || null,
    [identityDocs, identityOnboardingUrl],
  );
  const cameraDocs = useMemo(
    () =>
      identityDocs.filter((d) => {
        if (d.onboarding_url) return false;
        if (d.capture_mode === "link") return false;
        return d.accepts_api_upload !== false;
      }),
    [identityDocs],
  );

  const [mode, setMode] = useState<WizardMode>("waiting");

  useEffect(() => {
    setMode(linkUrl ? "choose" : cameraDocs.length ? "camera" : "waiting");
    setStep(0);
    setError("");
  }, [linkUrl, cameraDocs.length, documents]);
  const [step, setStep] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  const currentDoc = cameraDocs[step] ?? null;
  const isSelfie = (currentDoc?.type || "").toUpperCase() === "IDENTIFICATION_SELFIE";

  const resetCapture = useCallback(() => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setSelectedFile(null);
    setError("");
  }, [previewUrl]);

  const handleFile = useCallback(
    (file: File | undefined | null) => {
      if (!file) return;
      resetCapture();
      if (file.size > 10 * 1024 * 1024) {
        setError("Arquivo muito grande. Use uma foto de até 10 MB.");
        return;
      }
      if (!file.type.startsWith("image/")) {
        setError("Para RG e selfie, envie uma foto (JPG ou PNG).");
        return;
      }
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
    },
    [resetCapture],
  );

  async function confirmUpload() {
    if (!currentDoc || !selectedFile) return;
    setUploading(true);
    setError("");
    try {
      const message = await uploadIdentityFile(currentDoc.id, selectedFile);
      resetCapture();
      if (step + 1 >= cameraDocs.length) {
        onComplete(message);
        onClose();
        return;
      }
      setStep((s) => s + 1);
      onComplete(message);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Falha no envio da foto.";
      setError(message);
      const lower = message.toLowerCase();
      if (lower.includes("link oficial") || lower.includes("limitação asaas") || lower.includes("não pode ser enviado")) {
        setMode(linkUrl ? "link" : "waiting");
        resetCapture();
      }
    } finally {
      setUploading(false);
    }
  }

  function closeWizard() {
    resetCapture();
    onClose();
  }

  return (
    <div className="kyc-wizard-overlay" role="dialog" aria-modal="true" aria-labelledby="kyc-wizard-title">
      <div className="kyc-wizard-panel">
        <header className="kyc-wizard-header">
          <div>
            <small className="eyebrow dark">VERIFICAÇÃO LETTER</small>
            <h2 id="kyc-wizard-title">RG e selfie</h2>
          </div>
          <button type="button" className="kyc-wizard-close" onClick={closeWizard} aria-label="Fechar">
            <X />
          </button>
        </header>

        {mode === "choose" && linkUrl && (
          <div className="kyc-wizard-body">
            <p className="muted" style={{ marginTop: 0 }}>
              Escolha como deseja concluir a verificação de identidade. O fluxo oficial com reconhecimento facial é o
              mais rápido.
            </p>
            <button type="button" className="kyc-wizard-primary" onClick={() => setMode("link")}>
              <Camera />
              Verificação no app (recomendado)
            </button>
            {cameraDocs.length > 0 && (
              <button type="button" className="kyc-wizard-secondary" onClick={() => setMode("camera")}>
                <Upload />
                Enviar fotos manualmente (somente homologação)
              </button>
            )}
          </div>
        )}

        {mode === "waiting" && (
          <div className="kyc-wizard-body">
            <p className="muted" style={{ marginTop: 0 }}>
              Para <strong>RG e selfie</strong>, o Asaas não aceita envio de foto pela plataforma (pessoa física). É
              obrigatório usar o <strong>link oficial de verificação</strong>.
            </p>
            <ol className="muted" style={{ margin: "0 0 16px", paddingLeft: 20 }}>
              <li>Feche esta janela.</li>
              <li>No BANK, toque em <strong>Atualizar dados bancários</strong>.</li>
              <li>Aguarde cerca de 1 minuto e abra <strong>Verificar identidade</strong> de novo.</li>
            </ol>
            {linkUrl ? (
              <button type="button" className="kyc-wizard-primary" onClick={() => setMode("link")}>
                <ExternalLink />
                Abrir verificação oficial
              </button>
            ) : (
              <button type="button" className="kyc-wizard-secondary" onClick={closeWizard}>
                Fechar e atualizar dados bancários
              </button>
            )}
          </div>
        )}

        {mode === "link" && linkUrl && (
          <div className="kyc-wizard-body kyc-wizard-link-body">
            <p className="muted" style={{ marginTop: 0 }}>
              Conclua RG e selfie no ambiente seguro LETTER. Permita o uso da câmera quando solicitado.
            </p>
            <iframe
              className="kyc-wizard-iframe"
              src={linkUrl}
              title="Verificação de identidade LETTER"
              allow="camera; microphone; fullscreen"
            />
            <div className="kyc-wizard-actions">
              <button type="button" className="kyc-wizard-secondary" onClick={() => setMode("choose")}>
                <ChevronLeft />
                Voltar
              </button>
              <a className="kyc-wizard-secondary" href={linkUrl} target="_blank" rel="noreferrer">
                <ExternalLink />
                Abrir em nova aba
              </a>
            </div>
          </div>
        )}

        {mode === "waiting" && (
          <div className="kyc-wizard-body">
            <p className="muted" style={{ marginTop: 0 }}>
              Ainda não há link de verificação do Asaas para esta conta. Toque em <strong>Atualizar dados bancários</strong> na
              Carteira LETTER, aguarde cerca de 1 minuto e abra esta tela de novo.
            </p>
            <p className="muted">
              Se o link não aparecer, contate o suporte LETTER — podemos ressincronizar a subconta com o Asaas.
            </p>
          </div>
        )}

        {mode === "camera" && (
          <div className="kyc-wizard-body">
            {!cameraDocs.length ? (
              <p className="muted">Nenhum documento de identidade pendente para envio por foto.</p>
            ) : (
              <>
                <p className="muted" style={{ marginTop: 0 }}>
                  Passo {step + 1} de {cameraDocs.length}: <strong>{currentDoc?.title}</strong>
                </p>
                <p className="muted">
                  {isSelfie
                    ? "Use a câmera frontal, rosto bem iluminado, sem óculos escuros ou boné."
                    : "Fotografe o documento (RG ou CNH) com boa iluminação e texto legível."}
                </p>

                {previewUrl ? (
                  <div className="kyc-wizard-preview">
                    <img src={previewUrl} alt="Pré-visualização" />
                  </div>
                ) : (
                  <div className="kyc-wizard-preview kyc-wizard-preview-empty">
                    <Camera />
                    <span>Nenhuma foto selecionada</span>
                  </div>
                )}

                {error && <div className="error">{error}</div>}

                <div className="kyc-wizard-actions">
                  {linkUrl && (
                    <button type="button" className="kyc-wizard-secondary" onClick={() => setMode("choose")}>
                      <ChevronLeft />
                      Voltar
                    </button>
                  )}
                  <button
                    type="button"
                    className="kyc-wizard-secondary"
                    onClick={() => inputRef.current?.click()}
                    disabled={uploading}
                  >
                    <Camera />
                    {isSelfie ? "Tirar selfie" : "Tirar foto do documento"}
                  </button>
                  <button
                    type="button"
                    className="kyc-wizard-secondary"
                    onClick={() => {
                      const input = inputRef.current;
                      if (input) {
                        input.removeAttribute("capture");
                        input.click();
                      }
                    }}
                    disabled={uploading}
                  >
                    <Upload />
                    Escolher da galeria
                  </button>
                  {previewUrl && (
                    <button type="button" className="kyc-wizard-primary" onClick={() => void confirmUpload()} disabled={uploading}>
                      {uploading ? <RefreshCw className="spin" /> : <Upload />}
                      {uploading ? "Enviando…" : "Enviar foto"}
                    </button>
                  )}
                </div>

                <input
                  ref={inputRef}
                  type="file"
                  accept="image/*"
                  capture={isSelfie ? "user" : "environment"}
                  style={{ display: "none" }}
                  onChange={(e) => {
                    handleFile(e.currentTarget.files?.[0]);
                    e.currentTarget.value = "";
                  }}
                />
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
