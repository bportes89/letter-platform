export const MARITAL_STATUS_OPTIONS = [
  { value: "SOLTEIRO", label: "Solteiro(a)" },
  { value: "CASADO", label: "Casado(a)" },
  { value: "DIVORCIADO", label: "Divorciado(a)" },
  { value: "VIUVO", label: "Viúvo(a)" },
  { value: "UNIAO_ESTAVEL", label: "União estável" },
] as const;

export type MaritalStatusValue = (typeof MARITAL_STATUS_OPTIONS)[number]["value"];

export function maritalRequiresSpouse(status: string): boolean {
  const key = String(status || "").trim().toUpperCase();
  return key === "CASADO" || key === "UNIAO_ESTAVEL";
}

export function spouseDocumentDigits(value: string): string {
  return String(value || "").replace(/\D/g, "");
}

export function validatePfMaritalFields(
  personType: string,
  maritalStatus: string,
  spouseName: string,
  spouseDocument: string,
): string | null {
  if (personType !== "PF") return null;
  if (!maritalStatus.trim()) return "Informe o estado civil do cliente.";
  if (!maritalRequiresSpouse(maritalStatus)) return null;
  if (!spouseName.trim()) return "Informe o nome completo do cônjuge.";
  if (spouseDocumentDigits(spouseDocument).length !== 11) return "Informe o CPF do cônjuge (11 dígitos).";
  return null;
}

export function validateSocioMaritalRows(
  rows: Array<{ name?: string; document?: string; marital_status?: string; spouse_name?: string; spouse_document?: string }>,
): string | null {
  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i];
    if (!String(row.name || "").trim() && !String(row.document || "").trim()) continue;
    if (!String(row.marital_status || "").trim()) return `Informe o estado civil do sócio ${i + 1}.`;
    if (!maritalRequiresSpouse(String(row.marital_status))) continue;
    if (!String(row.spouse_name || "").trim()) return `Informe o nome do cônjuge do sócio ${i + 1}.`;
    if (spouseDocumentDigits(String(row.spouse_document || "")).length !== 11) {
      return `Informe o CPF do cônjuge do sócio ${i + 1} (11 dígitos).`;
    }
  }
  return null;
}
