"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ChatItem,
  ChatOption,
  ChatSiteInfo,
  CHAT_HOME_FALLBACK,
  fetchChatHome,
  fetchChatStep,
  formatChatBrlDisplay,
  isChatMoneyField,
  mapLegacyLink,
  warmChatApi,
  venderCotaChatContactEmail,
  venderCotaChatContactName,
  venderCotaChatContactPhone,
  venderCotaChatCredit,
  venderCotaChatIntro,
  venderCotaChatPaid,
  venderCotaChatTerm,
  venderCotaChatTipo,
  whatsappHref,
} from "@/lib/public-chat-api";
import { CurrencyFormField } from "@/components/currency-input";
import { calculateVenderCota, fetchVenderCotaBootstrap, storeVenderCota } from "@/lib/public-site-api";
import { getStoredReferralCode, isVenderCotaLink, rememberReferralCode } from "@/lib/referral";

type FlowMeta = {
  visibleCount: number;
  optionReveal: Record<number, number>;
  loading: boolean;
};

type UserEcho = {
  flowIndex: number;
  itemIndex: number;
  value: string;
};

function parseInputTags(tags?: string) {
  const placeholder = tags?.match(/placeholder="([^"]+)"/)?.[1];
  const type = tags?.match(/type="([^"]+)"/)?.[1] ?? "text";
  return { placeholder, type };
}

function fullNameOk(name: string): boolean {
  const s = name.trim();
  if (!s) return false;
  const parts = s.split(/\s+/);
  if (parts.length < 2) return false;
  const primeiro = parts[0];
  const sobrenome = s.slice(primeiro.length).trim();
  return primeiro.length > 2 && sobrenome.length > 2;
}

function optionLabel(option: ChatOption) {
  return option.name ?? option.text ?? "Opção";
}

/** Produtos que só seguem na área logada (API antiga ainda pode listar no chat). */
const LOGGED_AREA_PRODUCT_KEYS = new Set(["SDC", "FLASH", "QUITCON"]);

function optionLoggedAreaProductKey(option: ChatOption): string | null {
  const raw = option.save ?? option.id;
  if (raw == null) return null;
  const key = String(raw).toUpperCase();
  return LOGGED_AREA_PRODUCT_KEYS.has(key) ? key : null;
}

function filterExternalBotOptions(options: ChatOption[]): ChatOption[] {
  return options.filter((o) => !optionLoggedAreaProductKey(o));
}

function loggedAreaProductGateFlow(productKey: string): ChatItem[] {
  const labels: Record<string, string> = {
    SDC: "Capital de Giro (SDC)",
    FLASH: "Flash Capital",
    QUITCON: "QuitCon",
  };
  const label = labels[productKey] ?? productKey;
  return [
    {
      text:
        `${label} não é concluído neste chat público. ` +
        "Cadastre-se ou entre na sua conta LETTER para simular e enviar documentos na área logada.",
      options: [
        { name: "Criar minha conta", link: "/cadastro", save: "open_page" },
        { name: "Já tenho conta — entrar", link: "/login", save: "open_page" },
        { name: "Comprar carta contemplada", next: 10005 },
        { name: "Vender minha cota", link: "/vender-minha-cota", save: "open_page" },
      ],
    },
  ];
}

function ChatUserEcho({ value }: { value: string }) {
  return (
    <div className="attendance-user-row">
      <div className="attendance-user-bubble">{value}</div>
    </div>
  );
}

function chatVideoEmbedUrl(url: string): string | null {
  const trimmed = url.trim();
  if (!trimmed) return null;
  const yt =
    trimmed.match(/(?:youtube\.com\/watch\?v=|youtube\.com\/embed\/|youtu\.be\/)([\w-]{6,})/i)?.[1] ??
    trimmed.match(/youtube\.com\/shorts\/([\w-]{6,})/i)?.[1];
  if (yt) return `https://www.youtube-nocookie.com/embed/${yt}`;
  const vimeo = trimmed.match(/vimeo\.com\/(?:video\/)?(\d+)/i)?.[1];
  if (vimeo) return `https://player.vimeo.com/video/${vimeo}`;
  return null;
}

function ChatVideoBlock({ url }: { url: string }) {
  const embed = chatVideoEmbedUrl(url);
  if (embed) {
    return (
      <div className="attendance-video">
        <iframe
          src={embed}
          title="Vídeo explicativo"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
        />
      </div>
    );
  }
  return (
    <a className="text-link" href={url} target="_blank" rel="noreferrer">
      Assistir vídeo explicativo →
    </a>
  );
}

function QuotaCard({ quota }: { quota: ChatOption }) {
  return (
    <div className="attendance-quota-card">
      {quota.lane ? (
        <p className="attendance-quota-lane">
          <span>Opção:</span> {quota.lane}
        </p>
      ) : null}
      {quota.administradora ? (
        <p>
          <span>Administradora:</span> {quota.administradora}
        </p>
      ) : null}
      {quota.tipo_credito ? (
        <p>
          <span>Tipo do crédito:</span> {quota.tipo_credito}
        </p>
      ) : null}
      {quota.price ? (
        <p>
          <span>Valor do crédito:</span> {formatChatBrlDisplay(quota.price)}
        </p>
      ) : null}
      {quota.price_entrada ? (
        <p>
          <span>Valor da entrada:</span> {formatChatBrlDisplay(quota.price_entrada)}
        </p>
      ) : null}
      {quota.parcelas ? (
        <p>
          <span>Prazo restante em meses:</span> {quota.parcelas}
        </p>
      ) : null}
      {quota.price_parcela ? (
        <p>
          <span>Valor da parcela:</span>{" "}
          {String(quota.price_parcela).includes("x de") || String(quota.price_parcela).includes(" mais ")
            ? quota.price_parcela
            : formatChatBrlDisplay(quota.price_parcela)}
        </p>
      ) : null}
      {quota.vencimento_dia ? (
        <p>
          <span>Dia de vencimento das parcelas:</span> {quota.vencimento_dia}
        </p>
      ) : null}
      {quota.vencimento_proxima ? (
        <p>
          <span>Data de vencimento da próxima parcela:</span> {quota.vencimento_proxima}
        </p>
      ) : null}
    </div>
  );
}

export function AttendanceBotSection() {
  const [flows, setFlows] = useState<ChatItem[][]>([]);
  const [meta, setMeta] = useState<FlowMeta[]>([]);
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [echoes, setEchoes] = useState<UserEcho[]>([]);
  const [siteInfo, setSiteInfo] = useState<ChatSiteInfo | undefined>();
  const [apiConnected, setApiConnected] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [connectSlow, setConnectSlow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const blockRef = useRef<HTMLDivElement>(null);
  const formRef = useRef<Record<string, unknown>>({});
  const [mascotTop, setMascotTop] = useState(0);

  useEffect(() => {
    formRef.current = form;
  }, [form]);

  const currentFlowIndex = flows.length - 1;
  const isCurrent = (flowIndex: number) => flowIndex === currentFlowIndex;

  const waLink = useMemo(() => whatsappHref(siteInfo), [siteInfo]);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      if (!blockRef.current) return;
      const items = blockRef.current.querySelectorAll("[data-chat-item]");
      const last = items[items.length - 1] as HTMLElement | undefined;
      if (last) {
        last.scrollIntoView({ behavior: "smooth", block: "nearest" });
        const dockOffset = window.matchMedia("(min-width: 851px)").matches ? 100 : 72;
        const raw = Math.max(0, last.offsetTop + last.offsetHeight - dockOffset);
        const mobile = !window.matchMedia("(min-width: 851px)").matches;
        setMascotTop(mobile ? Math.min(raw, 240) : raw);
      }
    });
  }, []);

  const pushFlow = useCallback(
    (items: ChatItem[], info?: ChatSiteInfo) => {
      if (info) setSiteInfo((prev) => ({ ...prev, ...info }));
      setFlows((prev) => [...prev, items]);
      setMeta((prev) => [
        ...prev,
        {
          visibleCount: items.length > 0 ? 1 : 0,
          optionReveal: {},
          loading: Boolean(items[0]?.load),
        },
      ]);
      scrollToBottom();
    },
    [scrollToBottom],
  );

  const loadInitial = useCallback(async (): Promise<boolean> => {
    setConnecting(true);
    setConnectSlow(false);
    setApiConnected(false);
    setError("");
    warmChatApi();
    setFlows((prev) => (prev.length === 0 ? [CHAT_HOME_FALLBACK] : prev));
    setMeta((prev) =>
      prev.length === 0
        ? [
            {
              visibleCount: CHAT_HOME_FALLBACK.length > 0 ? 1 : 0,
              optionReveal: {},
              loading: Boolean(CHAT_HOME_FALLBACK[0]?.load),
            },
          ]
        : prev,
    );
    try {
      const data = await fetchChatHome({});
      if (data.info) setSiteInfo((prev) => ({ ...prev, ...data.info }));
      if (data.lead_id) {
        setForm((prev) => {
          const next = { ...prev, lead_id: data.lead_id };
          formRef.current = next;
          return next;
        });
      }
      setApiConnected(true);
      setError("");
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao conectar ao atendimento.");
      return false;
    } finally {
      setConnecting(false);
      setConnectSlow(false);
    }
  }, []);

  useEffect(() => {
    void loadInitial();
  }, [loadInitial]);

  useEffect(() => {
    if (!connecting) return;
    const slowTimer = window.setTimeout(() => setConnectSlow(true), 5000);
    return () => window.clearTimeout(slowTimer);
  }, [connecting]);

  const requireApi = useCallback(async () => {
    if (apiConnected) return true;
    if (connecting) {
      setError("Ainda conectando ao servidor. Aguarde alguns segundos.");
      return false;
    }
    const ok = await loadInitial();
    if (!ok) setError("Não foi possível conectar. Toque em «Tentar novamente».");
    return ok;
  }, [apiConnected, connecting, loadInitial]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    rememberReferralCode(params.get("ref"));
  }, []);

  useEffect(() => {
    if (flows.length === 0) return;
    const flowIndex = flows.length - 1;
    const items = flows[flowIndex];
    const stepMs =
      typeof window !== "undefined" && window.matchMedia("(max-width: 850px)").matches ? 550 : 900;
    const timer = window.setInterval(() => {
      setMeta((prev) => {
        const current = prev[flowIndex];
        if (!current) return prev;
        if (current.visibleCount >= items.length) {
          window.clearInterval(timer);
          return prev;
        }
        const nextCount = current.visibleCount + 1;
        const next = [...prev];
        next[flowIndex] = { ...current, visibleCount: nextCount, loading: false };
        scrollToBottom();
        return next;
      });
    }, stepMs);
    return () => window.clearInterval(timer);
  }, [flows.length, flows, scrollToBottom]);


  const recordEcho = (flowIndex: number, itemIndex: number, value: string) => {
    setEchoes((prev) => [...prev.filter((x) => !(x.flowIndex === flowIndex && x.itemIndex === itemIndex)), { flowIndex, itemIndex, value }]);
  };

  const runVmcSubmit = async (merged: Record<string, unknown>) => {
    const boot = await fetchVenderCotaBootstrap();
    const adminId = boot.administrators[0]?.id;
    if (!adminId) throw new Error("Nenhuma administradora disponível no momento.");
    const payload = {
      tipo_consorcio: String(merged.vmc_tipo || ""),
      administrator_id: adminId,
      credit_value: String(merged.vmc_credit || "").replace(/\D/g, "") || "0",
      paid_value: String(merged.vmc_paid || "").replace(/\D/g, "") || "0",
      outstanding_balance: "0",
      term_months: Number(merged.vmc_term || 0),
      contemplated: true,
      contact_name: String(merged.vmc_name || ""),
      contact_email: String(merged.vmc_email || ""),
      contact_phone: String(merged.vmc_phone || ""),
      person_type: "PF",
      partner_referral_code: getStoredReferralCode(),
    };
    const calc = await calculateVenderCota(payload);
    if (!calc.result.viable) {
      pushFlow([
        {
          text: `Não foi possível seguir: ${calc.result.motivos.join(" ") || "oferta inviável."}`,
          options: [{ name: "Abrir formulário completo", link: "/vender-minha-cota" }, { name: "Recomeçar", next: 0 }],
        },
      ]);
      return;
    }
    const stored = await storeVenderCota(payload);
    const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
    pushFlow([
      {
        text: `Prévia Letter: ${brl.format(Number(stored.offer_value))} (${stored.offer_percent}% do crédito). Oferta registrada.`,
        options: [
          { name: "Anexar extrato no formulário", link: `/vender-minha-cota?offer=${stored.offer_id}` },
          { name: "Voltar ao início", next: 0 },
        ],
      },
    ]);
  };

  const advanceVmc = async (step: number, mergedForm: Record<string, unknown>) => {
    if (step === -9101) {
      pushFlow(venderCotaChatTipo());
      return;
    }
    if (step === -9102) {
      pushFlow(venderCotaChatCredit());
      return;
    }
    if (step === -9103) {
      pushFlow(venderCotaChatPaid());
      return;
    }
    if (step === -9104) {
      pushFlow(venderCotaChatTerm());
      return;
    }
    if (step === -9105) {
      pushFlow(venderCotaChatContactName());
      return;
    }
    if (step === -9106) {
      pushFlow(venderCotaChatContactEmail());
      return;
    }
    if (step === -9107) {
      pushFlow(venderCotaChatContactPhone());
      return;
    }
    if (step === -9108) {
      await runVmcSubmit(mergedForm);
      return;
    }
    throw new Error("Etapa do chat de venda inválida");
  };

  const advance = async (
    step: number | string,
    back = 0,
    echo?: { flowIndex: number; itemIndex: number; value: string },
    formOverride?: Record<string, unknown>,
  ) => {
    if (busy) return;
    const numeric = typeof step === "number" ? step : Number(step);
    const vmcLocal = Number.isFinite(numeric) && numeric <= -9101;
    if (!vmcLocal && step !== 0 && !(await requireApi())) return;
    setBusy(true);
    setError("");
    if (echo) recordEcho(echo.flowIndex, echo.itemIndex, echo.value);
    const mergedForm = formOverride ?? formRef.current;
    try {
      if (Number.isFinite(numeric) && numeric <= -9101) {
        await advanceVmc(numeric, mergedForm);
        return;
      }
      if (step === 0) {
        setForm({});
        const data = await fetchChatHome({});
        pushFlow(data.chat_next, data.info);
        return;
      }
      const payload = { ...mergedForm, back, referral_code: getStoredReferralCode() };
      const data = await fetchChatStep(step, payload);
      setForm((prev) => {
        const next = { ...prev, ...mergedForm };
        if (data.lead_id) next.lead_id = data.lead_id;
        formRef.current = next;
        return next;
      });
      if (!Array.isArray(data.chat_next) || data.chat_next.length === 0) {
        setError("O atendimento não retornou a próxima etapa. Toque em «Reiniciar conversa» e tente de novo.");
        if (echo) {
          setEchoes((prev) =>
            prev.filter((x) => !(x.flowIndex === echo.flowIndex && x.itemIndex === echo.itemIndex)),
          );
        }
        return;
      }
      pushFlow(data.chat_next, data.info);
    } catch (e) {
      if (echo) {
        setEchoes((prev) =>
          prev.filter((x) => !(x.flowIndex === echo.flowIndex && x.itemIndex === echo.itemIndex)),
        );
      }
      setError(e instanceof Error ? e.message : "Não foi possível avançar no atendimento.");
    } finally {
      setBusy(false);
    }
  };

  const resetChat = () => {
    setFlows([]);
    setMeta([]);
    setForm({});
    setEchoes([]);
    void loadInitial();
  };

  const onOption = async (flowIndex: number, itemIndex: number, item: ChatItem, option: ChatOption) => {
    if (!isCurrent(flowIndex) || busy) return;
    const loggedProduct = optionLoggedAreaProductKey(option);
    if (loggedProduct) {
      recordEcho(flowIndex, itemIndex, optionLabel(option));
      pushFlow(loggedAreaProductGateFlow(loggedProduct));
      return;
    }
    const needsServer = !option.link && option.next !== undefined;
    if (needsServer && !(await requireApi())) return;
    if (option.link && option.save === "open_page") {
      window.location.href = mapLegacyLink(option.link);
      return;
    }
    if (option.link && isVenderCotaLink(option.link)) {
      recordEcho(flowIndex, itemIndex, optionLabel(option));
      pushFlow(venderCotaChatIntro());
      return;
    }
    if (option.link) {
      const href = mapLegacyLink(option.link);
      if (href.startsWith("http")) window.open(href, "_blank", "noopener,noreferrer");
      else window.location.href = href;
      return;
    }
    const nextForm = { ...formRef.current };
    if (option.id !== undefined) nextForm.option_id = option.id;
    if (option.save !== undefined) {
      nextForm.option_save = option.save;
      if (typeof option.save === "string" && ["imovel", "autos", "pesados", "maquinas", "produtos", "servicos"].includes(option.save)) {
        nextForm.vmc_tipo = option.save;
      }
    }
    formRef.current = nextForm;
    setForm(nextForm);
    const next = option.next ?? item.next ?? 0;
    if (typeof next === "number" && next <= -9101) {
      setBusy(true);
      setError("");
      recordEcho(flowIndex, itemIndex, optionLabel(option));
      try {
        await advanceVmc(next, nextForm);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Falha no fluxo de venda");
      } finally {
        setBusy(false);
      }
      return;
    }
    await advance(next, 0, { flowIndex, itemIndex, value: optionLabel(option) }, nextForm);
  };

  const onButton = async (flowIndex: number, itemIndex: number, item: ChatItem) => {
    if (!isCurrent(flowIndex) || busy) return;
    if (!item.link && !(await requireApi())) return;
    if (item.link) {
      window.open(item.link, "_blank", "noopener,noreferrer");
      return;
    }
    await advance(item.next ?? 0, 0, item.button ? { flowIndex, itemIndex, value: item.button } : undefined);
  };

  const onInput = async (flowIndex: number, itemIndex: number, item: ChatItem, e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!isCurrent(flowIndex) || busy || !item.input) return;
    const formEl = e.currentTarget;
    const fd = new FormData(formEl);
    const value = String(fd.get(item.input.name) ?? "").trim();
    if (!value) {
      setError("Preencha o campo antes de prosseguir.");
      return;
    }
    if (!(await requireApi())) return;
    if (item.input.name === "name" && !fullNameOk(value)) {
      setError("Informe nome e sobrenome completos (ex.: Maria da Silva).");
      return;
    }
    const nextForm = { ...formRef.current, [item.input.name]: value };
    formRef.current = nextForm;
    setForm(nextForm);
    const displayValue = isChatMoneyField(item.input.name) ? formatChatBrlDisplay(value) : value;
    const display =
      item.input.type === "password"
        ? "Senha cadastrada"
        : item.input.label
          ? `${item.input.label}: ${displayValue}`
          : displayValue;
    await advance(item.next ?? 0, 0, { flowIndex, itemIndex, value: display }, nextForm);
  };

  const onContract = async (flowIndex: number, itemIndex: number, item: ChatItem, accepted: boolean) => {
    if (!isCurrent(flowIndex) || busy) return;
    const nextForm = { ...form };
    if (accepted) {
      const save = item.accept_save || "accept";
      nextForm.option_save = save;
      nextForm.option_id = save;
      setForm(nextForm);
      await advance(item.next ?? 0, 0, { flowIndex, itemIndex, value: "Contrato assinado" }, nextForm);
      return;
    }
    const save = item.decline_save || "decline";
    nextForm.option_save = save;
    nextForm.option_id = save;
    setForm(nextForm);
    await advance(
      item.next_decline ?? item.next ?? 0,
      0,
      { flowIndex, itemIndex, value: "Dúvidas" },
      nextForm,
    );
  };

  const renderOptions = (flowIndex: number, itemIndex: number, item: ChatItem) => {
    const options = filterExternalBotOptions(item.options ?? []);
    if (item.options_quotas) {
      return (
        <div className="attendance-quota-options">
          {options.map((option, optionIndex) => (
            <div key={`${option.id ?? optionIndex}-${optionLabel(option)}`} className="attendance-quota-option-block">
              <QuotaCard quota={option} />
              <button
                type="button"
                className="attendance-primary attendance-quota-pick"
                disabled={busy}
                onClick={() => void onOption(flowIndex, itemIndex, item, option)}
              >
                Escolher esta opção
              </button>
            </div>
          ))}
          {item.options_empty ? <p className="attendance-empty">{item.options_empty}</p> : null}
          {waLink ? (
            <a className="attendance-option attendance-option-muted" href={waLink} target="_blank" rel="noreferrer">
              Não encontrou, clique aqui. Atendimento sob medida
            </a>
          ) : null}
        </div>
      );
    }
    return (
      <div className="attendance-options">
        {options.map((option, optionIndex) => (
          <button
            key={`${option.id ?? optionIndex}-${optionLabel(option)}`}
            type="button"
            className="attendance-option"
            disabled={busy}
            onClick={() => void onOption(flowIndex, itemIndex, item, option)}
          >
            {optionLabel(option)}
          </button>
        ))}
        {item.options_empty ? <p className="attendance-empty">{item.options_empty}</p> : null}
      </div>
    );
  };

  const showInteractive = (flowIndex: number, itemIndex: number) =>
    isCurrent(flowIndex) && !echoes.some((x) => x.flowIndex === flowIndex && x.itemIndex === itemIndex);

  return (
    <section id="atendimento" className="section attendance-section">
      <div className="section-kicker">Atendimento · Robô Letter</div>
      <div className="section-heading">
        <h2>
          Fale com o Letter.
          <br />
          <em>Atendimento externo 24/7.</em>
        </h2>
      </div>

      <div className="attendance-shell">
        {connecting ? (
          <p className="attendance-status">
            Conectando ao servidor…
            {connectSlow
              ? " Na primeira visita do dia isso pode levar até 2 minutos; você já pode ler as mensagens abaixo."
              : null}
          </p>
        ) : null}
        {error ? <p className="attendance-error">{error}</p> : null}
        {error && !apiConnected ? (
          <div className="attendance-actions attendance-retry-wrap">
            <button type="button" className="attendance-primary" disabled={connecting} onClick={() => void loadInitial()}>
              Tentar novamente
            </button>
          </div>
        ) : null}

        <div className="attendance-chat" ref={blockRef}>

          <div className="attendance-mascot-wrap" style={flows.length > 0 ? { marginTop: mascotTop } : undefined}>
            <Image
              src="/brand/letter-mascote.png"
              alt="Mascote Letter"
              width={100}
              height={100}
              className="attendance-mascot"
            />
            {meta[currentFlowIndex]?.loading || busy ? <span className="attendance-typing" aria-hidden /> : null}
          </div>

          {busy && apiConnected ? (
            <div className="attendance-bot-row" data-chat-item>
              <div className="attendance-bot-bubble">Buscando opções de cota…</div>
            </div>
          ) : null}

          {flows.map((items, flowIndex) =>
            items.map((item, itemIndex) => {
              const visible = itemIndex < (meta[flowIndex]?.visibleCount ?? 0);
              if (!visible) return null;
              const echo = echoes.find((x) => x.flowIndex === flowIndex && x.itemIndex === itemIndex);

              return (
                <div key={`${flowIndex}-${itemIndex}`}>
                  {item.text ? (
                    <div className="attendance-bot-row" data-chat-item>
                      <div className="attendance-bot-bubble">{item.text}</div>
                    </div>
                  ) : null}

                  {item.info_html ? (
                    <div className="attendance-bot-row" data-chat-item>
                      <div
                        className="attendance-bot-bubble attendance-bot-bubble-wide letter-contract-body"
                        dangerouslySetInnerHTML={{ __html: item.info_html }}
                      />
                    </div>
                  ) : null}

                  {item.video ? (
                    <div className="attendance-bot-row" data-chat-item>
                      <div className="attendance-bot-bubble attendance-bot-bubble-wide">
                        <p style={{ marginTop: 0 }}>Antes de escolher, assista ao vídeo explicativo:</p>
                        <ChatVideoBlock url={item.video} />
                      </div>
                    </div>
                  ) : null}

                  {item.button && showInteractive(flowIndex, itemIndex) ? (
                    <div className="attendance-actions" data-chat-item>
                      <button
                        type="button"
                        className="attendance-primary"
                        disabled={busy || connecting}
                        onClick={() => void onButton(flowIndex, itemIndex, item)}
                      >
                        {item.button}
                      </button>
                    </div>
                  ) : null}

                  {Array.isArray(item.options) && showInteractive(flowIndex, itemIndex) ? (
                    <div data-chat-item>{renderOptions(flowIndex, itemIndex, item)}</div>
                  ) : null}

                  {item.input && showInteractive(flowIndex, itemIndex) ? (
                    <div className="attendance-form-wrap" data-chat-item>
                      {(item.title || item.tile) && <p className="attendance-form-title">{item.title || item.tile}</p>}
                      <form className="attendance-form" onSubmit={(e) => void onInput(flowIndex, itemIndex, item, e)}>
                        {isChatMoneyField(item.input.name) ? (
                          <CurrencyFormField
                            name={item.input.name}
                            placeholder={parseInputTags(item.input.tags).placeholder ?? "R$ 0,00"}
                            disabled={busy || connecting}
                            required
                          />
                        ) : (
                          <input
                            name={item.input.name}
                            type={parseInputTags(item.input.tags).type}
                            placeholder={parseInputTags(item.input.tags).placeholder ?? item.input.label ?? "Digite aqui"}
                            autoComplete={item.input.name === "name" ? "name" : undefined}
                            enterKeyHint="go"
                            required
                            disabled={busy || connecting}
                          />
                        )}
                        <button
                          type="submit"
                          className="attendance-primary"
                          disabled={busy || (connecting && !apiConnected)}
                        >
                          Prosseguir
                        </button>
                      </form>
                      <p className="attendance-form-hint">Toque em Prosseguir ou use Enter no teclado.</p>
                    </div>
                  ) : null}


                  {item.address && isCurrent(flowIndex) ? (
                    <div className="attendance-actions" data-chat-item>
                      <p className="attendance-form-title">Informe seu endereço completo pelo WhatsApp para continuar.</p>
                      {waLink ? (
                        <a className="attendance-primary" href={waLink} target="_blank" rel="noreferrer">
                          Continuar no WhatsApp
                        </a>
                      ) : null}
                    </div>
                  ) : null}

                  {item.resumo && Array.isArray(item.quotas) ? (
                    <div className="attendance-resumo" data-chat-item>
                      {item.quotas.map((quota, qIndex) => (
                        <QuotaCard key={quota.id ?? qIndex} quota={quota} />
                      ))}
                      {isCurrent(flowIndex) ? (
                        <button
                          type="button"
                          className="attendance-primary"
                          disabled={busy}
                          onClick={() => void onButton(flowIndex, itemIndex, item)}
                        >
                          Continuar
                        </button>
                      ) : null}
                    </div>
                  ) : null}

                  {item.sdc_result ? (
                    <div className="attendance-sdc-result" data-chat-item>
                      <h4>Resultado da análise</h4>
                      <div className="attendance-sdc-grid">
                        <div>
                          <span>Valor alavancado</span>
                          <strong>{item.sdc_result.valor_alavancado_fmt}</strong>
                        </div>
                        <div>
                          <span>Prazo estimado</span>
                          <strong>{item.sdc_result.prazo_fmt}</strong>
                        </div>
                        <div>
                          <span>Parcela estimada</span>
                          <strong>{item.sdc_result.parcela_fmt}</strong>
                        </div>
                        <div>
                          <span>Taxa estimada</span>
                          <strong>{item.sdc_result.taxa_fmt}</strong>
                        </div>
                      </div>
                      {item.sdc_result.viavel ? (
                        <>
                          <p className="attendance-sdc-ok">
                            Operação passível de aprovação. Clique em continuar para dar andamento.
                          </p>
                          {isCurrent(flowIndex) ? (
                            <button
                              type="button"
                              className="attendance-primary"
                              disabled={busy}
                              onClick={() => void onButton(flowIndex, itemIndex, item)}
                            >
                              Continuar
                            </button>
                          ) : null}
                        </>
                      ) : (
                        <>
                          <p className="attendance-sdc-block">Não foi possível seguir com a sua operação.</p>
                          {Array.isArray(item.sdc_result.motivos) ? (
                            <ul>
                              {item.sdc_result.motivos.map((motivo) => (
                                <li key={motivo}>{motivo}</li>
                              ))}
                            </ul>
                          ) : null}
                          {isCurrent(flowIndex) ? (
                            <div className="attendance-actions">
                              <button type="button" className="attendance-primary" onClick={() => void advance(10005, 1)}>
                                Mudar a categoria
                              </button>
                              <button type="button" className="attendance-secondary" onClick={resetChat}>
                                Começar do início
                              </button>
                            </div>
                          ) : null}
                        </>
                      )}
                    </div>
                  ) : null}

                  {item.flash_result ? (
                    <div className="attendance-sdc-result" data-chat-item>
                      <h4>Flash Capital — análise</h4>
                      <div className="attendance-sdc-grid">
                        <div>
                          <span>Principal (LTV 40%)</span>
                          <strong>{item.flash_result.principal_fmt}</strong>
                        </div>
                        <div>
                          <span>LTV</span>
                          <strong>{item.flash_result.ltv_fmt}</strong>
                        </div>
                        <div>
                          <span>Parcela estimada</span>
                          <strong>{item.flash_result.parcela_fmt}</strong>
                        </div>
                        <div>
                          <span>Prazo</span>
                          <strong>{item.flash_result.prazo_fmt}</strong>
                        </div>
                        <div>
                          <span>Líquido estimado</span>
                          <strong>{item.flash_result.liquido_fmt}</strong>
                        </div>
                      </div>
                      {item.flash_result.viavel ? (
                        <>
                          <p className="attendance-sdc-ok">
                            Operação Flash viável. Clique em continuar para registrar na mesa.
                          </p>
                          {isCurrent(flowIndex) ? (
                            <button
                              type="button"
                              className="attendance-primary"
                              disabled={busy}
                              onClick={() => void onButton(flowIndex, itemIndex, item)}
                            >
                              Continuar
                            </button>
                          ) : null}
                        </>
                      ) : (
                        <>
                          <p className="attendance-sdc-block">Não foi possível seguir com a operação Flash.</p>
                          {Array.isArray(item.flash_result.motivos) ? (
                            <ul>
                              {item.flash_result.motivos.map((motivo) => (
                                <li key={motivo}>{motivo}</li>
                              ))}
                            </ul>
                          ) : null}
                          {isCurrent(flowIndex) ? (
                            <div className="attendance-actions">
                              <button type="button" className="attendance-primary" onClick={() => void advance(10005, 1)}>
                                Mudar a categoria
                              </button>
                              <button type="button" className="attendance-secondary" onClick={resetChat}>
                                Começar do início
                              </button>
                            </div>
                          ) : null}
                        </>
                      )}
                    </div>
                  ) : null}

                  {item.quitcon_result ? (
                    <div className="attendance-sdc-result" data-chat-item>
                      <h4>QuitCon — análise</h4>
                      <div className="attendance-sdc-grid">
                        <div>
                          <span>Valor presente (VP)</span>
                          <strong>{item.quitcon_result.vp_fmt}</strong>
                        </div>
                        <div>
                          <span>Saldo bruto</span>
                          <strong>{item.quitcon_result.saldo_fmt}</strong>
                        </div>
                        <div>
                          <span>Prazo restante</span>
                          <strong>{item.quitcon_result.meses_fmt}</strong>
                        </div>
                        <div>
                          <span>Administradora</span>
                          <strong>{item.quitcon_result.admin_fmt}</strong>
                        </div>
                        <div>
                          <span>Custos de abertura</span>
                          <strong>{item.quitcon_result.entrada_fmt}</strong>
                        </div>
                      </div>
                      {item.quitcon_result.viavel ? (
                        <>
                          <p className="attendance-sdc-ok">
                            Operação QuitCon viável. Clique em continuar para registrar na mesa.
                          </p>
                          {isCurrent(flowIndex) ? (
                            <button
                              type="button"
                              className="attendance-primary"
                              disabled={busy}
                              onClick={() => void onButton(flowIndex, itemIndex, item)}
                            >
                              Continuar
                            </button>
                          ) : null}
                        </>
                      ) : (
                        <>
                          <p className="attendance-sdc-block">Não foi possível seguir com a operação QuitCon.</p>
                          {Array.isArray(item.quitcon_result.motivos) ? (
                            <ul>
                              {item.quitcon_result.motivos.map((motivo) => (
                                <li key={motivo}>{motivo}</li>
                              ))}
                            </ul>
                          ) : null}
                          {isCurrent(flowIndex) ? (
                            <div className="attendance-actions">
                              <button type="button" className="attendance-primary" onClick={() => void advance(10005, 1)}>
                                Mudar a categoria
                              </button>
                              <button type="button" className="attendance-secondary" onClick={resetChat}>
                                Começar do início
                              </button>
                            </div>
                          ) : null}
                        </>
                      )}
                    </div>
                  ) : null}

                  {item.faq && Array.isArray(item.items) && showInteractive(flowIndex, itemIndex) ? (
                    <div className="attendance-options" data-chat-item>
                      {item.items.map((faqItem, faqIndex) => (
                        <button
                          key={faqItem.id ?? faqIndex}
                          type="button"
                          className="attendance-option"
                          disabled={busy}
                          onClick={() => {
                            const faqId = String(faqItem.id ?? "");
                            const nextForm = {
                              ...form,
                              option_id: faqId,
                              option_save: faqId,
                              faq_id: faqId,
                            };
                            setForm(nextForm);
                            void advance(
                              item.next ?? 10040,
                              0,
                              { flowIndex, itemIndex, value: faqItem.name ?? "Dúvida" },
                              nextForm,
                            );
                          }}
                        >
                          {faqItem.name}
                        </button>
                      ))}
                    </div>
                  ) : null}

                  {item.contract && item.html ? (
                    <div className="attendance-contract" data-chat-item>
                      <div className="attendance-contract-body" dangerouslySetInnerHTML={{ __html: item.html }} />
                      {isCurrent(flowIndex) ? (
                        <div className="attendance-actions">
                          <button
                            type="button"
                            className="attendance-primary"
                            disabled={busy}
                            onClick={() => void onContract(flowIndex, itemIndex, item, true)}
                          >
                            Aceitar os termos e assinar
                          </button>
                          <button
                            type="button"
                            className="attendance-secondary"
                            disabled={busy}
                            onClick={() => void onContract(flowIndex, itemIndex, item, false)}
                          >
                            Não aceitar os termos
                          </button>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {echo ? <ChatUserEcho value={echo.value} /> : null}
                </div>
              );
            }),
          )}
        </div>

        {flows.length > 0 ? (
          <button type="button" className="attendance-reset" onClick={resetChat}>
            Reiniciar conversa
          </button>
        ) : null}
      </div>

      {waLink ? (
        <a className="attendance-whatsapp" href={waLink} target="_blank" rel="noreferrer" aria-label="WhatsApp LETTER">
          WhatsApp
        </a>
      ) : null}
    </section>
  );
}

export function AttendanceWhatsAppFab({ info }: { info?: ChatSiteInfo }) {
  const href = whatsappHref(info);
  if (!href) return null;
  return (
    <a className="attendance-whatsapp" href={href} target="_blank" rel="noreferrer" aria-label="WhatsApp LETTER">
      WhatsApp
    </a>
  );
}
