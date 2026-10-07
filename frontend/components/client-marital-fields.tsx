"use client";

import { MARITAL_STATUS_OPTIONS, maritalRequiresSpouse } from "@/lib/marital-status";

type Props = {
  maritalStatus: string;
  spouseName: string;
  spouseDocument: string;
  onMaritalStatusChange: (value: string) => void;
  onSpouseNameChange: (value: string) => void;
  onSpouseDocumentChange: (value: string) => void;
  title?: string;
};

export function ClientMaritalFields({
  maritalStatus,
  spouseName,
  spouseDocument,
  onMaritalStatusChange,
  onSpouseNameChange,
  onSpouseDocumentChange,
  title = "Estado civil (compliance)",
}: Props) {
  const needsSpouse = maritalRequiresSpouse(maritalStatus);
  return (
    <div style={{ display: "grid", gap: 8, gridColumn: "1 / -1" }}>
      <b style={{ fontSize: 12 }}>{title}</b>
      <label style={{ fontSize: 11, fontWeight: 700 }}>
        Estado civil
        <select
          value={maritalStatus}
          onChange={(e) => onMaritalStatusChange(e.target.value)}
          style={{ width: "100%", marginTop: 4, padding: 8, borderRadius: 8, fontWeight: 400 }}
        >
          <option value="">Selecione…</option>
          {MARITAL_STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </label>
      {needsSpouse && (
        <div style={{ display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr", padding: "10px 12px", background: "#f7fbf9", borderRadius: 10, border: "1px solid var(--line)" }}>
          <label style={{ fontSize: 11, fontWeight: 700 }}>
            Nome do cônjuge
            <input
              value={spouseName}
              onChange={(e) => onSpouseNameChange(e.target.value)}
              placeholder="Nome completo"
              style={{ width: "100%", marginTop: 4 }}
            />
          </label>
          <label style={{ fontSize: 11, fontWeight: 700 }}>
            CPF do cônjuge
            <input
              value={spouseDocument}
              onChange={(e) => onSpouseDocumentChange(e.target.value)}
              placeholder="000.000.000-00"
              style={{ width: "100%", marginTop: 4 }}
            />
          </label>
          <small className="muted" style={{ gridColumn: "1 / -1", fontSize: 10, lineHeight: 1.45 }}>
            Dados do cônjuge são obrigatórios para certidões e compliance (TAPAF), quando o cliente é casado ou em união estável.
          </small>
        </div>
      )}
    </div>
  );
}
