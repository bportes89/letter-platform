"use client";

import { Plus, Trash2 } from "lucide-react";

export type SocioPartner = {
  name: string;
  document: string;
  role: string;
  share_percent: string;
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
};

export function PartnerSociosFields({ value, onChange, title = "Sócios / parceiros" }: Props) {
  const rows = value.length ? value : [emptyRow()];

  function patch(index: number, key: keyof SocioPartner, val: string) {
    const next = rows.map((row, i) => (i === index ? { ...row, [key]: val } : row));
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
      <small className="muted">Opcional — cadastro de sócios ou parceiros vinculados à operação.</small>
      {rows.map((row, index) => (
        <div
          key={index}
          style={{ display: "grid", gap: 8, gridTemplateColumns: "1.2fr 1fr 1fr 0.6fr auto", alignItems: "end" }}
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
          <button type="button" className="table-action" onClick={() => removeRow(index)} aria-label="Remover sócio">
            <Trash2 size={14} />
          </button>
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
