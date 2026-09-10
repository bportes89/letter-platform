"use client";

import {
  CheckCircle2,
  ExternalLink,
  FileCheck2,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  WalletCards,
} from "lucide-react";
import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  api,
  LssAllocationPreview,
  LssEntitlement,
  SaaSPlan,
  SaaSSubscription,
  SaaSTerms,
  User,
  ValidStampRecord,
} from "@/lib/api";
import { isInternalProductRole } from "@/lib/product-nav";
import { ValidStamp } from "@/components/valid-stamp";

const BILLING_OPTIONS = [
  { value: "BOLETO", label: "Boleto bancário" },
  { value: "PIX", label: "Pix (cobrança mensal)" },
  { value: "CREDIT_CARD", label: "Cartão de crédito" },
];

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export function LSSModule() {
  const [user, setUser] = useState<User | null>(null);
  const [plans, setPlans] = useState<SaaSPlan[]>([]);
  const [terms, setTerms] = useState<SaaSTerms[]>([]);
  const [subs, setSubs] = useState<SaaSSubscription[]>([]);
  const [stamps, setStamps] = useState<ValidStampRecord[]>([]);
  const [entitlement, setEntitlement] = useState<LssEntitlement | null>(null);
  const [allocation, setAllocation] = useState<LssAllocationPreview | null>(null);
  const [planId, setPlanId] = useState("");
  const [termsId, setTermsId] = useState("");
  const [scrollDone, setScrollDone] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [recurringAuthorized, setRecurringAuthorized] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const [opsPlanCode, setOpsPlanCode] = useState("LSS-PRO");
  const [opsPlanName, setOpsPlanName] = useState("LSS Profissional");
  const [opsPlanPrice, setOpsPlanPrice] = useState("199.90");
  const [opsTermsCode, setOpsTermsCode] = useState("LSS-B2B");
  const [opsTermsTitle, setOpsTermsTitle] = useState("Termos SaaS LSS");
  const [opsTermsVersion, setOpsTermsVersion] = useState("1");
  const [opsTermsBody, setOpsTermsBody] = useState(
    "Termos empresariais versionados do LETTER Servicing Suite (LSS), com recorrência mensal, cancelamento ao fim do período, alocação 70% central / 30% rede e trilha de aceite clickwrap sujeita à revisão jurídica.",
  );
  const [stepUpPassword, setStepUpPassword] = useState("");

  const termsRef = useRef<HTMLDivElement>(null);
  const termsEndRef = useRef<HTMLDivElement>(null);

  const isInternal = isInternalProductRole(user?.role);

  const activeTerms = useMemo(
    () =>
      terms.find((t) => t.id === termsId) ||
      terms.find((t) => t.active && t.legal_review_status === "APPROVED") ||
      null,
    [terms, termsId],
  );

  const selectedPlan = useMemo(
    () => plans.find((p) => p.id === planId) || plans[0] || null,
    [plans, planId],
  );

  const evaluateTermsScroll = useCallback(() => {
    const el = termsRef.current;
    if (!el) return;
    const remaining = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (remaining <= 24 || el.scrollHeight <= el.clientHeight + 1) setScrollDone(true);
  }, []);

  const load = useCallback(async () => {
    const me = await api<User>("/auth/me");
    setUser(me);
    const [p, t, s, v, e] = await Promise.all([
      api<SaaSPlan[]>("/lss/plans"),
      api<SaaSTerms[]>("/lss/terms"),
      api<SaaSSubscription[]>("/lss/subscriptions"),
      api<ValidStampRecord[]>("/valid-stamps"),
      api<LssEntitlement>("/lss/entitlement"),
    ]);
    setPlans(p);
    setTerms(t);
    setSubs(s);
    setStamps(v);
    setEntitlement(e);
    setPlanId((prev) => prev || p[0]?.id || "");
    const approved = t.find((x) => x.active && x.legal_review_status === "APPROVED");
    setTermsId((prev) => prev || approved?.id || "");
  }, []);

  useEffect(() => {
    setLoading(true);
    load()
      .catch((x) => setError(x instanceof Error ? x.message : "Falha ao carregar LSS"))
      .finally(() => setLoading(false));
  }, [load]);

  useEffect(() => {
    if (!planId) {
      setAllocation(null);
      return;
    }
    api<LssAllocationPreview>(`/lss/plans/${planId}/allocation-preview`)
      .then(setAllocation)
      .catch(() => setAllocation(null));
  }, [planId]);

  useEffect(() => {
    setScrollDone(false);
    setTermsAccepted(false);
    setRecurringAuthorized(false);
    const el = termsRef.current;
    const end = termsEndRef.current;
    if (!el || !activeTerms) return;

    const raf = requestAnimationFrame(evaluateTermsScroll);
    let observer: IntersectionObserver | undefined;
    if (end) {
      observer = new IntersectionObserver(
        (entries) => {
          if (entries.some((entry) => entry.isIntersecting)) setScrollDone(true);
        },
        { root: el, threshold: 0.25 },
      );
      observer.observe(end);
    }
    return () => {
      cancelAnimationFrame(raf);
      observer?.disconnect();
    };
  }, [activeTerms, evaluateTermsScroll]);

  async function subscribe(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!scrollDone) {
      setError("Role os termos até o final antes de contratar.");
      return;
    }
    const form = e.currentTarget;
    const f = new FormData(form);
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const body = await api<SaaSSubscription>("/lss/subscriptions", {
        method: "POST",
        body: JSON.stringify({
          plan_id: f.get("plan_id") || planId,
          terms_template_id: f.get("terms_id") || termsId,
          company_name: f.get("company_name"),
          company_cnpj: f.get("company_cnpj"),
          representative_name: f.get("representative_name"),
          representative_document: f.get("representative_document"),
          subscriber_email: f.get("subscriber_email"),
          billing_type: f.get("billing_type"),
          scroll_completed: true,
          terms_accepted: termsAccepted,
          recurring_authorized: recurringAuthorized,
          verification_reference: f.get("verification_reference"),
        }),
      });
      const checkout = body.payment_checkout_url;
      if (body.status === "PENDING_PAYMENT" && checkout) {
        setMessage("Aceite registrado. Conclua o pagamento da primeira mensalidade para ativar o LSS.");
        window.open(checkout, "_blank", "noopener,noreferrer");
      } else if (body.status === "ACTIVE_SANDBOX") {
        setMessage(
          "Aceite LSS registrado em sandbox — cobrança real indisponível (LETTER_LSS_BILLING_ENABLED + Asaas).",
        );
      } else {
        setMessage("Assinatura LSS criada. Aguarde a confirmação do pagamento.");
      }
      form.reset();
      setScrollDone(false);
      setTermsAccepted(false);
      setRecurringAuthorized(false);
      await load();
    } catch (x) {
      setError(x instanceof Error ? x.message : "Falha no aceite");
    } finally {
      setBusy(false);
    }
  }

  async function cancel(id: string) {
    setBusy(true);
    setError("");
    try {
      await api(`/lss/subscriptions/${id}/cancel`, { method: "POST", body: "{}" });
      setMessage("Cancelamento agendado para o fim do período — acesso mantido até lá.");
      await load();
    } catch (x) {
      setError(x instanceof Error ? x.message : "Falha ao cancelar");
    } finally {
      setBusy(false);
    }
  }

  async function evaluate(id: string) {
    setBusy(true);
    setError("");
    try {
      const row = await api<SaaSSubscription>(`/lss/subscriptions/${id}/evaluate`, {
        method: "POST",
        body: "{}",
      });
      setMessage(`Avaliação financeira: ${row.status}`);
      await load();
    } catch (x) {
      setError(x instanceof Error ? x.message : "Falha ao avaliar");
    } finally {
      setBusy(false);
    }
  }

  async function createPlan(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api<SaaSPlan>("/lss/plans", {
        method: "POST",
        body: JSON.stringify({
          code: opsPlanCode,
          name: opsPlanName,
          monthly_price: opsPlanPrice,
          central_share_percent: "70",
          network_pool_percent: "30",
        }),
      });
      setMessage("Plano LSS criado.");
      await load();
    } catch (x) {
      setError(x instanceof Error ? x.message : "Falha ao criar plano");
    } finally {
      setBusy(false);
    }
  }

  async function createTerms(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api<SaaSTerms>("/lss/terms", {
        method: "POST",
        body: JSON.stringify({
          code: opsTermsCode,
          version: Number(opsTermsVersion),
          title: opsTermsTitle,
          body: opsTermsBody,
        }),
      });
      setMessage("Termos LSS criados — aguardam aprovação jurídica (step-up).");
      await load();
    } catch (x) {
      setError(x instanceof Error ? x.message : "Falha ao criar termos");
    } finally {
      setBusy(false);
    }
  }

  async function approveTerms(id: string) {
    if (!stepUpPassword) {
      setError("Informe a senha de step-up antes de aprovar os termos.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(`/auth/step-up`, {
        method: "POST",
        body: JSON.stringify({ password: stepUpPassword }),
      });
      await api(`/lss/terms/${id}/approve`, { method: "POST", body: "{}" });
      setMessage("Termos aprovados.");
      setStepUpPassword("");
      await load();
    } catch (x) {
      setError(x instanceof Error ? x.message : "Falha ao aprovar termos");
    } finally {
      setBusy(false);
    }
  }

  const canSubscribe =
    scrollDone && termsAccepted && recurringAuthorized && Boolean(activeTerms) && Boolean(selectedPlan);
  const billingLive = entitlement?.billing_live ?? false;

  if (loading) {
    return (
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">LETTER SERVICING SUITE</span>
          <h1>SaaS LSS</h1>
          <p>Carregando mesa comercial…</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">LETTER SERVICING SUITE</span>
          <h1>SaaS LSS</h1>
          <p>
            Clickwrap com rolagem integral, recorrência Asaas e entitlement por status de assinatura.
          </p>
        </div>
        <div className="operational-icon">
          <FileCheck2 />
        </div>
      </div>

      {message && (
        <div className="notice">
          <ShieldCheck />
          {message}
        </div>
      )}
      {error && <div className="warning-banner">{error}</div>}

      {entitlement && (
        <section className={`panel ${entitlement.entitled ? "lss-entitled" : "lss-blocked"}`}>
          <div className="finops-summary">
            <article>
              <small>Entitlement</small>
              <strong>{entitlement.entitled ? "LIBERADO" : "BLOQUEADO"}</strong>
            </article>
            <article>
              <small>Status</small>
              <strong>{entitlement.subscription_status ?? "—"}</strong>
            </article>
            <article>
              <small>Billing</small>
              <strong>{billingLive ? "ASAAS LIVE" : "SANDBOX"}</strong>
            </article>
          </div>
          <p>{entitlement.message}</p>
          {entitlement.payment_checkout_url && entitlement.reason === "PENDING_PAYMENT" && (
            <a
              className="table-action"
              href={entitlement.payment_checkout_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink /> Pagar 1ª mensalidade
            </a>
          )}
        </section>
      )}

      <div className="lss-grid">
        <section className="panel lss-offer">
          <span className="eyebrow dark">PLANO EMPRESARIAL</span>
          <h2>{selectedPlan?.name ?? "LSS Profissional"}</h2>
          <strong>
            {brl.format(Number(selectedPlan?.monthly_price ?? 199.9))}
            <small>/mês</small>
          </strong>
          <ul>
            <li>
              <CheckCircle2 /> Aceite com IP, data, hash e verificação
            </li>
            <li>
              <CheckCircle2 /> Alocação {selectedPlan?.central_share_percent ?? "70"}% central /{" "}
              {selectedPlan?.network_pool_percent ?? "30"}% rede
            </li>
            <li>
              <CheckCircle2 /> Comissão recorrente da rede no dia 10 (cron)
            </li>
            <li>
              <CheckCircle2 /> Cancelamento ao final do período
            </li>
          </ul>
          {allocation && (
            <div className="finops-summary">
              <article>
                <small>Central</small>
                <strong>{brl.format(Number(allocation.central_share))}</strong>
              </article>
              <article>
                <small>Pool rede</small>
                <strong>{brl.format(Number(allocation.network_pool))}</strong>
              </article>
              <article>
                <small>Execução</small>
                <strong>{allocation.execution === "ASAAS_RECURRING" ? "Asaas" : "Preview"}</strong>
              </article>
            </div>
          )}
          {!billingLive && (
            <div className="warning-banner">
              <WalletCards />
              <div>
                <strong>Billing sandbox</strong>
                <p>
                  Sem <code>LETTER_LSS_BILLING_ENABLED</code> + chave Asaas, o aceite fica{" "}
                  <code>ACTIVE_SANDBOX</code> sem cobrança real.
                </p>
              </div>
            </div>
          )}
        </section>

        <section className="panel">
          <h2>Contratar como Pessoa Jurídica</h2>
          <form className="stack-form" onSubmit={subscribe}>
            <select
              name="plan_id"
              required
              value={planId}
              onChange={(e) => setPlanId(e.target.value)}
            >
              <option value="" disabled>
                Selecione o plano
              </option>
              {plans.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.name} · {brl.format(Number(x.monthly_price))}
                </option>
              ))}
            </select>
            <select
              name="terms_id"
              required
              value={termsId}
              onChange={(e) => setTermsId(e.target.value)}
            >
              <option value="" disabled>
                Termos aprovados
              </option>
              {terms
                .filter((x) => x.active && x.legal_review_status === "APPROVED")
                .map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.title} v{x.version}
                  </option>
                ))}
            </select>

            {activeTerms ? (
              <div>
                <h3 className="tapaf-section-title">{activeTerms.title} · v{activeTerms.version}</h3>
                <div
                  ref={termsRef}
                  className="manifest-scroll"
                  onScroll={() => evaluateTermsScroll()}
                >
                  <ScrollText size={18} />
                  <div className="manifest-body" style={{ whiteSpace: "pre-wrap" }}>
                    {activeTerms.body}
                  </div>
                  <div ref={termsEndRef} className="manifest-end-sentinel" aria-hidden="true" />
                </div>
                {!scrollDone && (
                  <small className="form-help">
                    Role os termos até o final para habilitar as declarações.
                  </small>
                )}
                {scrollDone && (
                  <small className="form-help">Termos lidos — marque as declarações abaixo.</small>
                )}
              </div>
            ) : (
              <div className="warning-banner">
                Não há termos aprovados. Peça ao admin para criar e aprovar a versão jurídica.
              </div>
            )}

            <input name="company_name" placeholder="Razão social" required />
            <input name="company_cnpj" placeholder="CNPJ" required />
            <input name="representative_name" placeholder="Representante legal" required />
            <input name="representative_document" placeholder="CPF do representante" required />
            <input name="subscriber_email" type="email" placeholder="E-mail financeiro" required />
            <select name="billing_type" required defaultValue="BOLETO">
              {BILLING_OPTIONS.map((x) => (
                <option key={x.value} value={x.value}>
                  {x.label}
                </option>
              ))}
            </select>
            <input name="verification_reference" placeholder="Referência OTP/liveness" required />

            <div className="tapaf-acceptance">
              <h4>Declarações obrigatórias</h4>
              <label className="tapaf-check">
                <input
                  type="checkbox"
                  checked={termsAccepted}
                  disabled={!scrollDone}
                  onChange={(e) => setTermsAccepted(e.target.checked)}
                />
                <span>Aceito o contrato SaaS LSS v{activeTerms?.version ?? "—"}</span>
              </label>
              <label className="tapaf-check">
                <input
                  type="checkbox"
                  checked={recurringAuthorized}
                  disabled={!scrollDone}
                  onChange={(e) => setRecurringAuthorized(e.target.checked)}
                />
                <span>Autorizo cobrança recorrente mensal</span>
              </label>
            </div>

            <button type="submit" disabled={!canSubscribe || busy}>
              {busy ? "Processando…" : "Contratar LSS"}
            </button>
          </form>
        </section>
      </div>

      <section className="panel">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <h2>Assinaturas e evidências</h2>
          <button type="button" className="table-action" disabled={busy} onClick={() => void load()}>
            <RefreshCw size={14} /> Atualizar
          </button>
        </div>
        <p className="form-help">
          Pool de rede (30%) alimenta comissão recorrente — liquidação programada no dia 10 via cron.
        </p>
        <div className="contract-grid">
          {subs.map((x) => {
            const stamp = stamps.find((s) => s.entity_id === x.id);
            return (
              <article className="contract-card" key={x.id}>
                <b>{x.subscriber_company_name}</b>
                <span className={`pill pill-${x.status.toLowerCase().replace(/_/g, "-")}`}>
                  {x.status}
                </span>
                <code>{x.acceptance_hash}</code>
                <small>Acesso até {new Date(x.current_period_end).toLocaleDateString("pt-BR")}</small>
                {x.billing_type && (
                  <small>
                    Forma: {x.billing_type}
                    {x.last_payment_status ? ` · ${x.last_payment_status}` : ""}
                  </small>
                )}
                {x.payment_checkout_url && x.status === "PENDING_PAYMENT" && (
                  <a
                    className="table-action"
                    href={x.payment_checkout_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <ExternalLink /> Pagar mensalidade
                  </a>
                )}
                {!x.cancel_at_period_end &&
                  !["CANCELLED", "SUSPENDED", "SUSPENDED_PAST_DUE_SANDBOX"].includes(x.status) && (
                    <button className="table-action" disabled={busy} onClick={() => void cancel(x.id)}>
                      Cancelar no fim do período
                    </button>
                  )}
                {isInternal && (
                  <button className="table-action" disabled={busy} onClick={() => void evaluate(x.id)}>
                    Avaliar billing
                  </button>
                )}
                {stamp && <ValidStamp code={stamp.stamp_code} hash={stamp.chain_hash} />}
              </article>
            );
          })}
          {!subs.length && <p className="form-help">Nenhuma assinatura nesta organização.</p>}
        </div>
      </section>

      {isInternal && (
        <section className="panel">
          <h2>Ops — planos e termos</h2>
          <div className="lss-grid">
            <form className="stack-form" onSubmit={createPlan}>
              <h3>Novo plano</h3>
              <input value={opsPlanCode} onChange={(e) => setOpsPlanCode(e.target.value)} placeholder="Código" required />
              <input value={opsPlanName} onChange={(e) => setOpsPlanName(e.target.value)} placeholder="Nome" required />
              <input value={opsPlanPrice} onChange={(e) => setOpsPlanPrice(e.target.value)} placeholder="Preço mensal" required />
              <small className="form-help">Alocação fixa 70% central / 30% rede</small>
              <button type="submit" disabled={busy}>
                Criar plano
              </button>
            </form>
            <form className="stack-form" onSubmit={createTerms}>
              <h3>Novos termos</h3>
              <input value={opsTermsCode} onChange={(e) => setOpsTermsCode(e.target.value)} placeholder="Código" required />
              <input value={opsTermsTitle} onChange={(e) => setOpsTermsTitle(e.target.value)} placeholder="Título" required />
              <input
                value={opsTermsVersion}
                onChange={(e) => setOpsTermsVersion(e.target.value)}
                placeholder="Versão"
                type="number"
                min={1}
                required
              />
              <textarea
                value={opsTermsBody}
                onChange={(e) => setOpsTermsBody(e.target.value)}
                rows={6}
                required
                minLength={50}
              />
              <button type="submit" disabled={busy}>
                Criar termos
              </button>
            </form>
          </div>
          <div className="stack-form" style={{ marginTop: 16, maxWidth: 360 }}>
            <input
              type="password"
              value={stepUpPassword}
              onChange={(e) => setStepUpPassword(e.target.value)}
              placeholder="Senha step-up (aprovação jurídica)"
              autoComplete="current-password"
            />
          </div>
          <div className="contract-grid" style={{ marginTop: 16 }}>
            {terms.map((t) => (
              <article className="contract-card" key={t.id}>
                <b>
                  {t.title} v{t.version}
                </b>
                <span className={`pill pill-${t.legal_review_status.toLowerCase()}`}>{t.legal_review_status}</span>
                <small>{t.active ? "Ativo" : "Inativo"}</small>
                <code>{t.body_hash.slice(0, 16)}…</code>
                {t.legal_review_status !== "APPROVED" && (
                  <button className="table-action" disabled={busy} onClick={() => void approveTerms(t.id)}>
                    Aprovar (step-up)
                  </button>
                )}
              </article>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
