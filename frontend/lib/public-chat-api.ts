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

export type FlashResult = {
  principal_fmt: string;
  ltv_fmt: string;
  parcela_fmt: string;
  prazo_fmt: string;
  liquido_fmt: string;
  viavel: boolean;
  motivos?: string[];
};

export type QuitconResult = {
  vp_fmt: string;
  saldo_fmt: string;
  meses_fmt: string;
  admin_fmt: string;
  entrada_fmt: string;
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
  flash_result?: FlashResult;
  quitcon_result?: QuitconResult;
  faq?: boolean;
  items?: ChatOption[];
  contract?: boolean;
  html?: string;
  back?: number;
  video?: string;
  next_decline?: number;
  accept_save?: string;
  decline_save?: string;
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
  lead_id?: string;
};

const CHAT_FETCH_TIMEOUT_MS = 45_000;
/** Render cold start can exceed 2 minutes; home must wait longer than step calls. */
const CHAT_HOME_TIMEOUT_MS = 180_000;

/** Mirrors `home_native()` — lets the UI render before the API wakes up. */
export const CHAT_HOME_FALLBACK: ChatItem[] = [
  {
    text:
      "Olá! Eu sou o Letter. Ajudo você a financiar imóveis e veículos " +
      "com cartas contempladas — menos burocracia que banco, mesmo com score baixo.",
    button: "Continuar",
    next: 10001,
    mascote: 1,
  },
  {
    text: "Quer vender uma cota que você já tem?",
    options: [
      { name: "Vender minha cota", link: "/vender-minha-cota", save: "open_page" },
      { name: "Quero comprar / financiar", next: 10001 },
    ],
  },
];

export function warmChatApi(): void {
  if (typeof window === "undefined") return;
  const base = API_URL.replace(/\/$/, "");
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 120_000);
  void fetch(`${base}/health`, { method: "GET", signal: controller.signal }).finally(() => {
    window.clearTimeout(timer);
  });
}

async function chatFetch<T>(
  path: string,
  body: Record<string, unknown> = {},
  options?: { timeoutMs?: number },
): Promise<T> {
  const timeoutMs = options?.timeoutMs ?? CHAT_FETCH_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("O servidor demorou para responder. Toque em «Tentar novamente».");
    }
    throw new Error("Não foi possível conectar ao atendimento. Verifique sua internet e tente de novo.");
  } finally {
    window.clearTimeout(timer);
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(typeof payload.detail === "string" ? payload.detail : "Atendimento indisponível.");
  }
  return response.json() as Promise<T>;
}

export async function fetchChatHome(
  body: Record<string, unknown> = {},
  options?: { timeoutMs?: number },
): Promise<ChatHomeResponse> {
  const data = await chatFetch<{ OBJ?: { chat_next?: ChatItem[]; info?: ChatSiteInfo; lead_id?: string } }>(
    "/public/site/chat/home",
    body,
    { timeoutMs: options?.timeoutMs ?? CHAT_HOME_TIMEOUT_MS },
  );
  const chat_next = data.OBJ?.chat_next ?? [];
  if (!Array.isArray(chat_next) || chat_next.length === 0) {
    throw new Error("Resposta inválida do atendimento. Tente novamente.");
  }
  return {
    chat_next,
    info: data.OBJ?.info,
    lead_id: typeof data.OBJ?.lead_id === "string" ? data.OBJ.lead_id : undefined,
  };
}

export async function fetchChatStep(step: number | string, body: Record<string, unknown> = {}): Promise<ChatHomeResponse> {
  const data = await chatFetch<{ OBJ?: { chat_next?: ChatItem[]; info?: ChatSiteInfo; lead_id?: string } }>(
    `/public/site/chat/home/${step}`,
    body,
  );
  return {
    chat_next: data.OBJ?.chat_next ?? [],
    info: data.OBJ?.info,
    lead_id: typeof data.OBJ?.lead_id === "string" ? data.OBJ.lead_id : undefined,
  };
}

import { getStoredReferralCode, isVenderCotaLink, rememberReferralCode, venderCotaHref } from "@/lib/referral";

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
  if (isVenderCotaLink(link)) return venderCotaHref("/vender-minha-cota");
  if (link.startsWith("/api/v1/")) {
    const base = API_URL.replace(/\/$/, "");
    // API_URL already ends with /api/v1 — strip duplicate prefix from link
    if (base.endsWith("/api/v1")) {
      return `${base}${link.slice("/api/v1".length)}`;
    }
    return `${base.replace(/\/api\/v1$/, "")}${link}`;
  }
  return link;
}

export function venderCotaChatIntro(): ChatItem[] {
  const ref = getStoredReferralCode();
  return [
    {
      text: ref
        ? `Perfeito — vamos calcular quanto a Letter pagaria pela sua cota contemplada (indicação ${ref}).`
        : "Perfeito — vamos calcular quanto a Letter pagaria pela sua cota contemplada.",
      options: [
        { name: "Preencher aqui no chat", next: -9101 },
        { name: "Abrir formulário completo", link: "/vender-minha-cota", save: "open_page" },
      ],
    },
  ];
}

export function venderCotaChatTipo(): ChatItem[] {
  return [
    {
      text: "Qual o tipo do consórcio?",
      options: [
        { name: "Imóvel", save: "imovel", next: -9102 },
        { name: "Autos", save: "autos", next: -9102 },
        { name: "Pesados", save: "pesados", next: -9102 },
        { name: "Máquinas", save: "maquinas", next: -9102 },
        { name: "Produtos", save: "produtos", next: -9102 },
        { name: "Serviços", save: "servicos", next: -9102 },
      ],
    },
  ];
}

export function venderCotaChatCredit(): ChatItem[] {
  return [
    {
      title: "Valor atual do crédito (R$)",
      input: { name: "vmc_credit", type: "text", tags: 'placeholder="Ex.: 100000"' },
      next: -9103,
    },
  ];
}

export function venderCotaChatPaid(): ChatItem[] {
  return [
    {
      title: "Total já pago em parcelas (R$)",
      input: { name: "vmc_paid", type: "text", tags: 'placeholder="Ex.: 10000"' },
      next: -9104,
    },
  ];
}

export function venderCotaChatTerm(): ChatItem[] {
  return [
    {
      title: "Prazo contratado (meses)",
      input: { name: "vmc_term", type: "number", tags: 'placeholder="Ex.: 120"' },
      next: -9105,
    },
  ];
}

export function venderCotaChatContactName(): ChatItem[] {
  return [
    {
      title: "Seu nome completo",
      input: { name: "vmc_name", type: "text", tags: 'placeholder="Nome completo"' },
      next: -9106,
    },
  ];
}

export function venderCotaChatContactEmail(): ChatItem[] {
  return [
    {
      title: "Seu e-mail",
      input: { name: "vmc_email", type: "email", tags: 'placeholder="voce@email.com"' },
      next: -9107,
    },
  ];
}

export function venderCotaChatContactPhone(): ChatItem[] {
  return [
    {
      title: "Telefone / WhatsApp",
      input: { name: "vmc_phone", type: "tel", tags: 'placeholder="DDD + número"' },
      next: -9108,
    },
  ];
}
