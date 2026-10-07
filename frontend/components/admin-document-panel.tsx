"use client";

import { CheckCircle2, Download, FileUp, Trash2 } from "lucide-react";
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

export type ChecklistDocOption = {
  code: string;
  label: string;
  required?: boolean;
  uploaded?: boolean;
};

type Props = {
  title?: string;
  hint?: string;
  documents: AdminDocumentRow[];
  busy?: boolean;
  canDelete?: boolean;
  docTypeOptions?: DocTypeOption[];
  defaultDocType?: string;
  checklistDocs?: ChecklistDocOption[];
  optionalUpload?: DocTypeOption;
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
  checklistDocs,
  optionalUpload,
  onUpload,
  onDownload,
  onDelete,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const checklistInputRef = useRef<HTMLInputElement>(null);
  const [docType, setDocType] = useState(defaultDocType || docTypeOptions?.[0]?.value || "");
  const [uploading, setUploading] = useState(false);
  const [pendingCode, setPendingCode] = useState<string | null>(null);

  const checklistMode = Boolean(checklistDocs?.length);

  async function handleFile(file: File, type?: string) {
    setUploading(true);
    try {
      await onUpload(file, type ?? (docTypeOptions?.length ? docType : undefined));
    } finally {
      setUploading(false);
      setPendingCode(null);
    }
  }

  function labelFor(doc: AdminDocumentRow) {
    const type = doc.doc_type || doc.kind || "DOCUMENTO";
    const name = doc.filename || type;
    const when = doc.created_at ? new Date(doc.created_at).toLocaleString("pt-BR") : null;
    return { type, name, when };
  }

  const pendingChecklist = checklistMode
    ? (checklistDocs ?? []).filter((d) => !d.uploaded)
    : [];
  const doneChecklist = checklistMode
    ? (checklistDocs ?? []).filter((d) => d.uploaded)
    : [];

  function checklistLabel(code: string) {
    return checklistDocs?.find((d) => d.code === code)?.label ?? code;
  }

  return (
    <div className="admin-document-panel">
      <div className="admin-document-panel__head">
        <div>
          <b>{title}</b>
          {hint && <small className="muted" style={{ display: "block", marginTop: 4 }}>{hint}</small>}
        </div>
        {!checklistMode && (
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
        )}
      </div>

      {checklistMode && (
        <div style={{ marginTop: 10 }}>
          <input
            ref={checklistInputRef}
            type="file"
            hidden
            accept=".pdf,.png,.jpg,.jpeg,.xml,.docx"
            disabled={busy || uploading}
            onChange={(e) => {
              const file = e.target.files?.[0];
              const code = pendingCode;
              if (file && code) void handleFile(file, code);
              e.target.value = "";
              setPendingCode(null);
            }}
          />
          {pendingChecklist.length > 0 ? (
            <ul className="admin-document-panel__checklist-pending" style={{ margin: 0, padding: 0, listStyle: "none" }}>
              {pendingChecklist.map((d) => (
                <li
                  key={d.code}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 10,
                    padding: "8px 10px",
                    marginBottom: 6,
                    borderRadius: 8,
                    border: "1px solid var(--line)",
                    background: "#fff",
                    fontSize: 12,
                  }}
                >
                  <span>
                    {d.label}
                    {d.required === false ? <span className="muted"> (opcional)</span> : null}
                  </span>
                  <button
                    type="button"
                    className="table-action"
                    disabled={busy || uploading}
                    onClick={() => {
                      setPendingCode(d.code);
                      checklistInputRef.current?.click();
                    }}
                  >
                    <FileUp />
                    {uploading && pendingCode === d.code ? "Enviando…" : "Anexar"}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted" style={{ fontSize: 11, margin: "0 0 8px" }}>
              Todos os itens do checklist foram anexados. Revise os arquivos abaixo antes de transmitir.
            </p>
          )}
          {doneChecklist.length > 0 && (
            <ul style={{ margin: "10px 0 0", padding: 0, listStyle: "none", fontSize: 11 }}>
              {doneChecklist.map((d) => (
                <li key={d.code} style={{ color: "#067647", display: "flex", gap: 6, alignItems: "center", marginBottom: 4 }}>
                  <CheckCircle2 size={14} />
                  {d.label}
                </li>
              ))}
            </ul>
          )}
          {optionalUpload && (
            <label className="table-action" style={{ marginTop: 10, cursor: busy || uploading ? "not-allowed" : "pointer" }}>
              <FileUp />
              {optionalUpload.label}
              <input
                type="file"
                hidden
                accept=".pdf,.png,.jpg,.jpeg,.xml,.docx"
                disabled={busy || uploading}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleFile(file, optionalUpload.value);
                  e.target.value = "";
                }}
              />
            </label>
          )}
        </div>
      )}

      {documents.length === 0 ? (
        !checklistMode && <small className="muted">Nenhum documento anexado.</small>
      ) : (
        <ul className="admin-document-panel__list" style={{ marginTop: checklistMode ? 12 : 0 }}>
          {documents.map((doc) => {
            const { type, name, when } = labelFor(doc);
            const typeLabel = checklistMode ? checklistLabel(type) : type;
            return (
              <li key={doc.id}>
                <div>
                  <b>{name}</b>
                  <small>
                    {typeLabel}
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
                        if (!window.confirm(`Excluir "${name}"? O item voltará ao checklist para novo anexo.`)) return;
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
