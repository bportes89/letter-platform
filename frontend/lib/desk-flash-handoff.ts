/** Repasse de dados SDC → Flash Capital (sessionStorage). */

export const FLASH_HANDOFF_STORAGE_KEY = "letter.desk.flash_handoff.v1";

export type DeskFlashHandoff = {
  source: "SDC_DESK";
  saved_at: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  document: string;
  person_type: string;
  address: string;
  occupation: string;
  income_value: string;
  requested_amount: string;
  properties: Array<{
    street: string;
    number: string;
    city: string;
    state: string;
    zip: string;
    matricula: string;
    property_value: string;
    debt_answer?: string;
    debt_type?: string;
    debt_payoff_value?: string;
  }>;
  partners_json: Array<{
    name: string;
    document: string;
    role: string;
    share_percent: string;
    marital_status?: string;
    spouse_name?: string;
    spouse_document?: string;
  }>;
  marital_status?: string;
  spouse_name?: string;
  spouse_document?: string;
};

export function saveFlashHandoff(payload: DeskFlashHandoff): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(FLASH_HANDOFF_STORAGE_KEY, JSON.stringify(payload));
}

export function loadFlashHandoff(): DeskFlashHandoff | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(FLASH_HANDOFF_STORAGE_KEY);
  if (!raw) return null;
  try {
    const data = JSON.parse(raw) as DeskFlashHandoff;
    if (data?.source !== "SDC_DESK") return null;
    return data;
  } catch {
    return null;
  }
}

export function clearFlashHandoff(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(FLASH_HANDOFF_STORAGE_KEY);
}
