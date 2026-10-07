"use client";

import { Plus, Trash2 } from "lucide-react";
import { MARITAL_STATUS_OPTIONS, maritalRequiresSpouse } from "@/lib/marital-status";

export type SocioPartner = {
  name: string;
  document: string;
  role: string;
  share_percent: string;
  has_credit_restriction?: "" | "NAO" | "SIM";
  marital_status?: string;
  spouse_name?: string;
  spouse_document?: string;
};

const emptyRow = (): SocioPartner => ({
  name: "",
  document: "",
  role: "",
  share_percent: "",
});

type Props = {
  value: SocioPartner[];
  onChange: (rows: SocioPartner[]) => void;
  title?: string;
  captureCreditRestriction?: boolean;
  captureMaritalStatus?: boolean;
};

export function PartnerSociosFields({
  value,
  onChange,
  title = "Sócios / parceiros",
  captureCreditRestriction = false,
  captureMaritalStatus = false,
}: Props) {
  const rows = value.length ? value : [emptyRow()];

  function patch(index: number, key: keyof SocioPartner, val: string) {
    const next = rows.map((row, i) => {
      if (i !== index) return row;
      const updated = { ...row, [key]: val };
      if (key === "marital_status" && !maritalRequiresSpouse(val)) {
        updated.spouse_name = "";
        updated.spouse_document = "";
      }
      return updated;
    });
    onChange(next);
  }

  function addRow() {
    onChange([...rows, emptyRow()]);
  }

  function removeRow(index: number) {
    const next = rows.filter((_, i) => i !== index);
    onChange(next.length ? next : [emptyRow()]);
  }

  return (
    <div className="stack-form" style={{ gridColumn: "1 / -1" }}>
      <b>{title}</b>
      <small className="muted">
        Opcional — cadastro de sócios ou parceiros vinculados à operação.
        {captureMaritalStatus ? " Informe estado civil; se casado ou união estável, preencha o cônjuge." : ""}
      </small>
      {rows.map((row, index) => (
        <div
          key={index}
          style={{
            display: "grid",
            gap: 8,
            padding: 10,
            border: "1px solid var(--line)",
            borderRadius: 10,
            background: "#fafcfb",
          }}
        >
          <div
            style={{
              display: "grid",
              gap: 8,
              gridTemplateColumns: captureCreditRestriction
                ? "1.2fr 1fr 1fr 0.6fr 1fr auto"
                : "1.2fr 1fr 1fr 0.6fr auto",
              alignItems: "end",
            }}
          >
            <label>
              Nome
              <input value={row.name} onChange={(e) => patch(index, "name", e.target.value)} placeholder="Nome completo" />
            </label>
            <label>
              CPF/CNPJ
              <input value={row.document} onChange={(e) => patch(index, "document", e.target.value)} />
            </label>
            <label>
              Função
              <input value={row.role} onChange={(e) => patch(index, "role", e.target.value)} placeholder="Sócio, avalista…" />
            </label>
            <label>
              %
              <input value={row.share_percent} onChange={(e) => patch(index, "share_percent", e.target.value)} placeholder="%" />
            </label>
            {captureCreditRestriction && (
              <label>
                Restrição?
                <select
                  value={row.has_credit_restriction || ""}
                  onChange={(e) => patch(index, "has_credit_restriction", e.target.value)}
                >
                  <option value="">—</option>
                  <option value="NAO">Não</option>
                  <option value="SIM">Sim</option>
                </select>
              </label>
            )}
            <button type="button" className="table-action" onClick={() => removeRow(index)} aria-label="Remover sócio">
              <Trash2 size={14} />
            </button>
          </div>
          {captureMaritalStatus && (
            <div style={{ display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr 1fr" }}>
              <label style={{ fontSize: 11, fontWeight: 700 }}>
                Estado civil
                <select
                  value={row.marital_status || ""}
                  onChange={(e) => patch(index, "marital_status", e.target.value)}
                  style={{ width: "100%", marginTop: 4, padding: 8, borderRadius: 8, fontWeight: 400 }}
                >
                  <option value="">Selecione…</option>
                  {MARITAL_STATUS_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </label>
              {maritalRequiresSpouse(row.marital_status || "") && (
                <>
                  <label style={{ fontSize: 11, fontWeight: 700 }}>
                    Cônjuge — nome
                    <input
                      value={row.spouse_name || ""}
                      onChange={(e) => patch(index, "spouse_name", e.target.value)}
                      placeholder="Nome completo"
                      style={{ width: "100%", marginTop: 4 }}
                    />
                  </label>
                  <label style={{ fontSize: 11, fontWeight: 700 }}>
                    Cônjuge — CPF
                    <input
                      value={row.spouse_document || ""}
                      onChange={(e) => patch(index, "spouse_document", e.target.value)}
                      placeholder="CPF"
                      style={{ width: "100%", marginTop: 4 }}
                    />
                  </label>
                </>
              )}
            </div>
          )}
        </div>
      ))}
      <button type="button" className="table-action" onClick={addRow}>
        <Plus size={14} />
        Adicionar sócio
      </button>
    </div>
  );
}

export function sociosPayload(rows: SocioPartner[]): SocioPartner[] {
  return rows.filter((r) => r.name.trim() || r.document.trim());
}
