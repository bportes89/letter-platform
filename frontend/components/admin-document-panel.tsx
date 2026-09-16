"use client";

import { Download, FileUp, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

export type AdminDocumentRow = {
  id: string;
  document_id?: string | null;
  doc_type?: string | null;
  kind?: string | null;
  filename?: string | null;
  status?: string | null;
  created_at?: string | null;
};

type DocTypeOption = { value: string; label: string };

type Props = {
  title?: string;
  hint?: string;
  documents: AdminDocumentRow[];
  busy?: boolean;
  canDelete?: boolean;
  docTypeOptions?: DocTypeOption[];
  defaultDocType?: string;
  onUpload: (file: File, docType?: string) => Promise<void>;
  onDownload: (doc: AdminDocumentRow) => Promise<void>;
  onDelete?: (doc: AdminDocumentRow) => Promise<void>;
};

export function AdminDocumentPanel({
  title = "Documentos",
  hint,
  documents,
  busy = false,
  canDelete = true,
  docTypeOptions,
  defaultDocType,
  onUpload,
  onDownload,
  onDelete,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [docType, setDocType] = useState(defaultDocType || docTypeOptions?.[0]?.value || "");
  const [uploading, setUploading] = useState(false);

  async function handleFile(file: File) {
    setUploading(true);
    try {
      await onUpload(file, docTypeOptions?.length ? docType : undefined);
    } finally {
      setUploading(false);
    }
  }

  function labelFor(doc: AdminDocumentRow) {
    const type = doc.doc_type || doc.kind || "DOCUMENTO";
    const name = doc.filename || type;
    const when = doc.created_at ? new Date(doc.created_at).toLocaleString("pt-BR") : null;
    return { type, name, when };
  }

  return (
    <div className="admin-document-panel">
      <div className="admin-document-panel__head">
        <div>
          <b>{title}</b>
          {hint && <small className="muted" style={{ display: "block", marginTop: 4 }}>{hint}</small>}
        </div>
        <div className="admin-document-panel__actions">
          {docTypeOptions && docTypeOptions.length > 0 && (
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              disabled={busy || uploading}
              style={{ padding: "6px 8px", borderRadius: 8, border: "1px solid var(--line)", fontSize: 12 }}
            >
              {docTypeOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          )}
          <label className="table-action" style={{ cursor: busy || uploading ? "not-allowed" : "pointer" }}>
            <FileUp />
            {uploading ? "Enviando…" : "Anexar"}
            <input
              ref={inputRef}
              type="file"
              hidden
              accept=".pdf,.png,.jpg,.jpeg,.xml,.docx"
              disabled={busy || uploading}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void handleFile(file);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </div>
      {documents.length === 0 ? (
        <small className="muted">Nenhum documento anexado.</small>
      ) : (
        <ul className="admin-document-panel__list">
          {documents.map((doc) => {
            const { type, name, when } = labelFor(doc);
            return (
              <li key={doc.id}>
                <div>
                  <b>{name}</b>
                  <small>
                    {type}
                    {doc.status ? ` · ${doc.status}` : ""}
                    {when ? ` · ${when}` : ""}
                  </small>
                </div>
                <div className="admin-document-panel__row-actions">
                  <button
                    type="button"
                    className="table-action"
                    disabled={busy || !doc.document_id}
                    onClick={() => void onDownload(doc)}
                  >
                    <Download />
                    Baixar
                  </button>
                  {canDelete && onDelete && (
                    <button
                      type="button"
                      className="table-action"
                      disabled={busy}
                      onClick={() => {
                        if (!window.confirm(`Excluir "${name}"?`)) return;
                        void onDelete(doc);
                      }}
                    >
                      <Trash2 />
                      Excluir
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
