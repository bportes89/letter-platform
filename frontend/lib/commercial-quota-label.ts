const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function supplierLeak(text: string): boolean {
  return (
    /sync[-_]/i.test(text) ||
    /\bSUP\d{2,}/i.test(text) ||
    /-(LUME|FRAGA|BITTELO|UNI_|CONTEMPLADO)/i.test(text) ||
    /\bSYNC-/i.test(text)
  );
}

export type CommercialQuotaLabelInput = {
  quota_id: string;
  group_code?: string;
  quota_code?: string;
  label?: string;
  credit_value: string;
  entrada_final: string;
  installment_value?: string;
  remaining_installments?: number | null;
  administrator_name?: string | null;
};

/** Exibição comercial — nunca mostrar código/sync do fornecedor na lista. */
export function commercialQuotaDisplay(c: CommercialQuotaLabelInput): string {
  if (c.label && !supplierLeak(c.label)) return c.label;
  const gc = c.group_code || "";
  const qc = c.quota_code || "";
  if (gc && qc && !supplierLeak(`${gc} ${qc}`)) {
    const parc = c.remaining_installments != null ? ` · ${c.remaining_installments} parcelas` : "";
    return `${gc} · ${qc} · ${c.administrator_name ?? "Adm."} · crédito ${brl.format(Number(c.credit_value))} · entrada ${brl.format(Number(c.entrada_final))} · parc. ${brl.format(Number(c.installment_value || 0))}${parc}`;
  }
  const ref = c.quota_id.replace(/-/g, "").slice(-6).toUpperCase();
  const parc = c.remaining_installments != null ? ` · ${c.remaining_installments} parcelas` : "";
  return `Letter · Ref ${ref} · ${c.administrator_name ?? "Adm."} · crédito ${brl.format(Number(c.credit_value))} · entrada ${brl.format(Number(c.entrada_final))} · parc. ${brl.format(Number(c.installment_value || 0))}${parc}`;
}
