"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type ContractDoc = {
  html: string;
  can_edit: boolean;
  has_site_contract: boolean;
  contract_ack?: { accepted_at?: string; provider?: string } | null;
  locked_fields?: Array<{ field: string; label: string; value: string }>;
};

type Props = {
  leadId: string;
  open: boolean;
  onClose: () => void;
  onSaved?: () => void;
  onOpenPdf?: () => void;
};

export function MarketplaceContractEditor({ leadId, open, onClose, onSaved, onOpenPdf }: Props) {
  const [doc, setDoc] = useState<ContractDoc | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const editorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || !leadId) return;
    setError("");
    setBusy(true);
    api<ContractDoc>(`/marketplace/cadastros/${leadId}/contrato`)
      .then((row) => {
        setDoc(row);
        if (editorRef.current) editorRef.current.innerHTML = row.html;
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar contrato"))
      .finally(() => setBusy(false));
  }, [open, leadId]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  async function save() {
    if (!doc?.can_edit || !editorRef.current) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api<ContractDoc>(`/marketplace/cadastros/${leadId}/contrato`, {
        method: "PUT",
        body: JSON.stringify({ html: editorRef.current.innerHTML }),
      });
      setDoc(updated);
      onSaved?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar");
    } finally {
      setBusy(false);
    }
  }

  async function regenerate() {
    if (!doc?.can_edit) return;
    if (!window.confirm("Regerar o contrato a partir do template? Texto livre será substituído; dados do cliente permanecem travados.")) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api<ContractDoc>(`/marketplace/cadastros/${leadId}/contrato/regenerate`, { method: "POST" });
      setDoc(updated);
      if (editorRef.current) editorRef.current.innerHTML = updated.html;
      onSaved?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao regerar");
    } finally {
      setBusy(false);
    }
  }

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1300,
        background: "rgba(0,0,0,0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
      onClick={onClose}
    >
      <div
        className="panel"
        style={{ width: "min(960px, 100%)", maxHeight: "92vh", overflow: "hidden", display: "flex", flexDirection: "column" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", gap: 12 }}>
          <div>
            <b>Contrato da compra</b>
            {doc?.contract_ack?.accepted_at ? (
              <div className="muted" style={{ fontSize: 11 }}>
                Aceito em {new Date(doc.contract_ack.accepted_at).toLocaleString("pt-BR")}
              </div>
            ) : (
              <div className="muted" style={{ fontSize: 11 }}>Rascunho / aguardando aceite no chat</div>
            )}
          </div>
          <button type="button" className="table-action" onClick={onClose}>Fechar</button>
        </div>
        {error && <div className="error" style={{ margin: "10px 18px 0" }}>{error}</div>}
        <p className="muted" style={{ fontSize: 11, margin: "10px 18px 0", lineHeight: 1.45 }}>
          Edite cláusulas e textos livres. Os campos em cinza são preenchidos pelo sistema (nome, valores, documento) — não altere.
        </p>
        <div style={{ flex: 1, overflow: "auto", padding: "0 18px 12px" }}>
          <div
            ref={editorRef}
            className="marketplace-contract-editor"
            contentEditable={doc?.can_edit && !busy}
            suppressContentEditableWarning
            style={{
              minHeight: 360,
              padding: 16,
              border: "1px solid var(--line)",
              borderRadius: 10,
              background: "#fff",
              fontSize: 13,
              lineHeight: 1.55,
              textAlign: "justify",
            }}
          />
        </div>
        <div style={{ padding: "12px 18px 16px", display: "flex", flexWrap: "wrap", gap: 8, borderTop: "1px solid var(--line)" }}>
          {onOpenPdf && doc?.has_site_contract ? (
            <button type="button" className="table-action" disabled={busy} onClick={onOpenPdf}>Baixar PDF</button>
          ) : null}
          {doc?.can_edit ? (
            <>
              <button type="button" className="admin-button" disabled={busy} onClick={() => void save()}>Salvar alterações</button>
              <button type="button" className="table-action" disabled={busy} onClick={() => void regenerate()}>Regerar do template</button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
