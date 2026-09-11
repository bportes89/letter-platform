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
  const data = await chatFetch<{ OBJ?: { chat_next?: ChatItem[]; info?: ChatSiteInfo; lead_id?: string } }>(
    "/public/site/chat/home",
    body,
  );
  return {
    chat_next: data.OBJ?.chat_next ?? [],
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
