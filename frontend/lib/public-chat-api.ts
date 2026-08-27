const API_URL = (process.env.NEXT_PUBLIC_API_URL?.trim() || "http://localhost:8001/api/v1").replace(/\s+/g, "");

export type ChatOption = {
  id?: number | string;
  name?: string;
  text?: string;
  next?: number;
  link?: string;
  save?: string | Record<string, unknown>;
  administradora?: string;
  tipo_credito?: string;
  valor_bem?: string;
  price?: string;
  price_entrada?: string;
  valor_spread?: string;
  valor_alavancado?: string;
  parcelas?: string | number;
  price_parcela?: string;
  vencimento_dia?: string;
  vencimento_proxima?: string;
  sdc?: boolean;
};

export type ChatInput = {
  label?: string;
  name: string;
  type?: string;
  tags?: string;
};

export type SdcResult = {
  valor_alavancado_fmt: string;
  prazo_fmt: string;
  parcela_fmt: string;
  taxa_fmt: string;
  viavel: boolean;
  motivos?: string[];
};

export type ChatItem = {
  text?: string;
  button?: string;
  next?: number;
  link?: string;
  load?: number;
  mascote?: number;
  options?: ChatOption[];
  options_muplite?: boolean;
  options_quotas?: boolean;
  options_select?: boolean;
  options_empty?: string;
  input?: ChatInput;
  title?: string;
  tile?: string;
  address?: boolean;
  resumo?: boolean;
  quotas?: ChatOption[];
  sdc_result?: SdcResult;
  faq?: boolean;
  items?: ChatOption[];
  contract?: boolean;
  html?: string;
  back?: number;
  video?: string;
};

export type ChatSiteInfo = {
  whatsapp?: string;
  whatsapp_code?: string;
  whatsapp_txt?: string;
  email?: string;
};

export type ChatHomeResponse = {
  chat_next: ChatItem[];
  info?: ChatSiteInfo;
};

async function chatFetch<T>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Não foi possível conectar ao atendimento. Tente novamente em instantes.");
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(typeof payload.detail === "string" ? payload.detail : "Atendimento indisponível.");
  }
  return response.json() as Promise<T>;
}

export async function fetchChatHome(body: Record<string, unknown> = {}): Promise<ChatHomeResponse> {
  const data = await chatFetch<{ OBJ?: { chat_next?: ChatItem[]; info?: ChatSiteInfo } }>(
    "/public/site/chat/home",
    body,
  );
  return {
    chat_next: data.OBJ?.chat_next ?? [],
    info: data.OBJ?.info,
  };
}

export async function fetchChatStep(step: number | string, body: Record<string, unknown> = {}): Promise<ChatHomeResponse> {
  const data = await chatFetch<{ OBJ?: { chat_next?: ChatItem[]; info?: ChatSiteInfo } }>(
    `/public/site/chat/home/${step}`,
    body,
  );
  return {
    chat_next: data.OBJ?.chat_next ?? [],
    info: data.OBJ?.info,
  };
}

export function whatsappHref(info?: ChatSiteInfo): string | null {
  const raw = info?.whatsapp?.replace(/\D/g, "") ?? "";
  if (!raw) return null;
  const text = encodeURIComponent(
    info?.whatsapp_txt ?? "Olá, gostaria de falar com a LETTER.",
  );
  const prefix = info?.whatsapp_code?.replace(/\D/g, "") || "55";
  return `https://wa.me/${prefix}${raw}?text=${text}`;
}

export function mapLegacyLink(link: string): string {
  if (link === "/vender_minha_cota") return "/login";
  return link;
}
