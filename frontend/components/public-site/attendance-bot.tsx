"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ChatItem,
  ChatOption,
  ChatSiteInfo,
  fetchChatHome,
  fetchChatStep,
  mapLegacyLink,
  whatsappHref,
} from "@/lib/public-chat-api";

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

function optionLabel(option: ChatOption) {
  return option.name ?? option.text ?? "Opção";
}

function ChatUserEcho({ value }: { value: string }) {
  return (
    <div className="attendance-user-row">
      <div className="attendance-user-bubble">{value}</div>
    </div>
  );
}

function QuotaCard({ quota }: { quota: ChatOption }) {
  return (
    <div className="attendance-quota-card">
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
          <span>Valor do crédito:</span> {quota.price}
        </p>
      ) : null}
      {quota.price_entrada ? (
        <p>
          <span>Valor da entrada:</span> {quota.price_entrada}
        </p>
      ) : null}
      {quota.parcelas ? (
        <p>
          <span>Prazo restante:</span> {quota.parcelas} meses
        </p>
      ) : null}
      {quota.price_parcela ? (
        <p>
          <span>Valor da parcela:</span> {quota.price_parcela}
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
  const [booting, setBooting] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const blockRef = useRef<HTMLDivElement>(null);
  const [mascotTop, setMascotTop] = useState(0);

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
        setMascotTop(Math.max(0, last.offsetTop + last.offsetHeight - 100));
      }
    });
  }, []);

  const pushFlow = useCallback(
    (items: ChatItem[], info?: ChatSiteInfo) => {
      if (info) setSiteInfo((prev) => ({ ...prev, ...info }));
      setFlows((prev) => [...prev, items]);
      setMeta((prev) => [...prev, { visibleCount: 0, optionReveal: {}, loading: Boolean(items[0]?.load) }]);
      scrollToBottom();
    },
    [scrollToBottom],
  );

  const loadInitial = useCallback(async () => {
    setBooting(true);
    setError("");
    try {
      const data = await fetchChatHome({});
      pushFlow(data.chat_next, data.info);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao iniciar atendimento.");
    } finally {
      setBooting(false);
    }
  }, [pushFlow]);

  useEffect(() => {
    void loadInitial();
  }, [loadInitial]);

  useEffect(() => {
    if (flows.length === 0) return;
    const flowIndex = flows.length - 1;
    const items = flows[flowIndex];
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
    }, 900);
    return () => window.clearInterval(timer);
  }, [flows.length, flows, scrollToBottom]);


  const recordEcho = (flowIndex: number, itemIndex: number, value: string) => {
    setEchoes((prev) => [...prev.filter((x) => !(x.flowIndex === flowIndex && x.itemIndex === itemIndex)), { flowIndex, itemIndex, value }]);
  };

  const advance = async (step: number | string, back = 0, echo?: { flowIndex: number; itemIndex: number; value: string }) => {
    if (busy) return;
    setBusy(true);
    setError("");
    if (echo) recordEcho(echo.flowIndex, echo.itemIndex, echo.value);
    try {
      const payload = { ...form, back };
      const data = await fetchChatStep(step, payload);
      pushFlow(data.chat_next, data.info);
    } catch (e) {
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
    if (option.link) {
      const href = mapLegacyLink(option.link);
      if (href.startsWith("http")) window.open(href, "_blank", "noopener,noreferrer");
      else window.location.href = href;
      return;
    }
    const next = option.next ?? item.next ?? 0;
    const nextForm = { ...form };
    if (option.id !== undefined) nextForm.option_id = option.id;
    if (option.save !== undefined) nextForm.option_save = option.save;
    setForm(nextForm);
    await advance(next, 0, { flowIndex, itemIndex, value: optionLabel(option) });
  };

  const onButton = async (flowIndex: number, itemIndex: number, item: ChatItem) => {
    if (!isCurrent(flowIndex) || busy) return;
    if (item.link) {
      window.open(item.link, "_blank", "noopener,noreferrer");
      return;
    }
    await advance(item.next ?? 0, 0, item.button ? { flowIndex, itemIndex, value: item.button } : undefined);
  };

  const onInput = async (flowIndex: number, itemIndex: number, item: ChatItem, e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!isCurrent(flowIndex) || busy || !item.input) return;
    const fd = new FormData(e.currentTarget);
    const value = String(fd.get(item.input.name) ?? "").trim();
    if (!value) return;
    const nextForm = { ...form, [item.input.name]: value };
    setForm(nextForm);
    const display =
      item.input.type === "password"
        ? "Senha cadastrada"
        : item.input.label
          ? `${item.input.label}: ${value}`
          : value;
    await advance(item.next ?? 0, 0, { flowIndex, itemIndex, value: display });
  };

  const onContract = async (flowIndex: number, itemIndex: number, item: ChatItem, accepted: boolean) => {
    if (!isCurrent(flowIndex) || busy) return;
    if (accepted) await advance(item.next ?? 0, 0, { flowIndex, itemIndex, value: "Contrato assinado" });
    else await advance(93, 0, { flowIndex, itemIndex, value: "Dúvidas" });
  };

  const renderOptions = (flowIndex: number, itemIndex: number, item: ChatItem) => {
    const options = item.options ?? [];
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
        {item.options_quotas && waLink ? (
          <a className="attendance-option attendance-option-muted" href={waLink} target="_blank" rel="noreferrer">
            Não encontrou, clique aqui. Atendimento sob medida
          </a>
        ) : null}
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
        <p>
          O mesmo robô conversacional do portal Letter.app.br — qualificação de interesse, orientação
          sobre SDC, carta contemplada e venda de cotas.
        </p>
      </div>

      <div className="attendance-shell">
        {booting ? <p className="attendance-status">Iniciando atendimento…</p> : null}
        {error ? <p className="attendance-error">{error}</p> : null}

        <div className="attendance-chat" ref={blockRef}>
          <div className="attendance-mascot-wrap" style={{ marginTop: mascotTop }}>
            <Image
              src="/brand/letter-mascote.png"
              alt="Mascote Letter"
              width={100}
              height={100}
              className="attendance-mascot"
            />
            {meta[currentFlowIndex]?.loading ? <span className="attendance-typing" aria-hidden /> : null}
          </div>

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

                  {item.video ? (
                    <div className="attendance-bot-row" data-chat-item>
                      <div className="attendance-bot-bubble attendance-bot-bubble-wide">
                        <Link href="#contato" className="text-link">
                          Assistir vídeo institucional →
                        </Link>
                      </div>
                    </div>
                  ) : null}

                  {item.button && showInteractive(flowIndex, itemIndex) ? (
                    <div className="attendance-actions" data-chat-item>
                      <button
                        type="button"
                        className="attendance-primary"
                        disabled={busy}
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
                        <input
                          name={item.input.name}
                          type={parseInputTags(item.input.tags).type}
                          placeholder={parseInputTags(item.input.tags).placeholder ?? item.input.label ?? "Digite aqui"}
                          required
                          disabled={busy}
                        />
                        <button type="submit" disabled={busy}>
                          Enviar
                        </button>
                      </form>
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
                              <button type="button" className="attendance-primary" onClick={() => void advance(21, 1)}>
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
                          onClick={() => void advance(95, 0, { flowIndex, itemIndex, value: faqItem.name ?? "Dúvida" })}
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
