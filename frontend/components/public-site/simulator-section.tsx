"use client";

import Link from "next/link";
import Image from "next/image";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  capturePublicLead,
  fetchPublicQuotas,
  simulateFlashPublic,
  simulateSdcPublic,
} from "@/lib/public-site-api";
import {
  DEMO_QUOTAS,
  mockFlashPool,
  mockSdcPool,
  type FlashMockResult,
  type MmnPreview,
  type SdcMockResult,
} from "@/lib/public-simulator-mock";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type QuotaItem = {
  id: string;
  group_code: string;
  quota_code: string;
  category: string;
  credit_value: string;
  status: string;
};

export function PublicSimulatorSection() {
  const [tab, setTab] = useState<"flash" | "sdc">("flash");
  const [unlocked, setUnlocked] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState<FlashMockResult | null>(null);
  const [sdc, setSdc] = useState<SdcMockResult | null>(null);
  const [quotas, setQuotas] = useState<QuotaItem[]>([]);
  const [selectedQuotas, setSelectedQuotas] = useState<string[]>([]);
  const catalog = quotas.length > 0 ? quotas : [...DEMO_QUOTAS];

  const loadQuotas = useCallback(async () => {
    try {
      const rows = await fetchPublicQuotas();
      if (rows.length > 0) setQuotas(rows);
      else setQuotas([...DEMO_QUOTAS]);
    } catch {
      setQuotas([...DEMO_QUOTAS]);
    }
  }, []);

  useEffect(() => {
    void loadQuotas();
  }, [loadQuotas]);

  function switchTab(next: "flash" | "sdc") {
    setTab(next);
    setUnlocked(false);
    setFlash(null);
    setSdc(null);
    setError("");
  }

  function toggleQuota(id: string) {
    setSelectedQuotas((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setLoading(true);
    const f = new FormData(e.currentTarget);
    const bacen = f.get("bacen") === "on";
    if (!bacen) {
      setError("Aceite o termo SCR/Registrato para continuar.");
      setLoading(false);
      return;
    }
    const razao = String(f.get("razao") ?? "").trim();
    const whatsapp = String(f.get("whatsapp") ?? "").trim();
    if (!razao || !whatsapp) {
      setError("Informe razão social e WhatsApp corporativo.");
      setLoading(false);
      return;
    }
    try {
      let valorBase: number | undefined;
      if (tab === "flash") {
        valorBase = Number(f.get("asset_value"));
      } else {
        valorBase = Number(f.get("requested_amount"));
      }

      await capturePublicLead({
        razao_social: razao,
        whatsapp,
        produto: tab,
        valor_base: Number.isFinite(valorBase) && valorBase > 0 ? valorBase : undefined,
        autorizacao_scr_bacen: true,
      });

      if (tab === "flash") {
        const assetValue = Number(f.get("asset_value"));
        const requestedRaw = f.get("requested_amount");
        const requested = requestedRaw ? Number(requestedRaw) : null;
        if (!Number.isFinite(assetValue) || assetValue <= 0) throw new Error("Informe um AVM válido.");
        setFlash(await simulateFlashPublic(assetValue, requested));
        setSdc(null);
      } else {
        const requested = Number(f.get("requested_amount"));
        const durationMonths = Number(f.get("duration_months"));
        const picked = catalog.filter((q) => selectedQuotas.includes(q.id));
        const quotaIds =
          picked.length > 0 ? picked.map((q) => q.id) : catalog.length > 0 ? [catalog[0].id] : [];
        const principal =
          picked.length > 0 ? picked.reduce((s, q) => s + Number(q.credit_value), 0) : requested;
        if (quotaIds.length === 0) throw new Error("Nenhuma cota disponível para simulação.");
        if (!Number.isFinite(principal) || principal <= 0) {
          throw new Error("Selecione cotas ou informe o valor alvo da operação.");
        }
        setSdc(
          await simulateSdcPublic({
            quota_ids: quotaIds,
            requested_amount: principal,
            duration_months: durationMonths,
          }),
        );
        setFlash(null);
      }
      setUnlocked(true);
    } catch (x) {
      setError(x instanceof Error ? x.message : "Falha na simulação");
    } finally {
      setLoading(false);
    }
  }

  const previewFlash = mockFlashPool(1_000_000, null);
  const displayFlash = flash ?? previewFlash;
  const previewSdc = mockSdcPool(800_000, 12, "OTHER");
  const displaySdc = sdc ?? previewSdc;

  return (
    <div className="simulator">
      <form className="sim-form" onSubmit={(ev) => void submit(ev)}>
        <div className="tabs" role="tablist">
          <button
            type="button"
            className={tab === "flash" ? "active" : ""}
            onClick={() => switchTab("flash")}
          >
            Flash Capital
          </button>
          <button
            type="button"
            className={tab === "sdc" ? "active" : ""}
            onClick={() => switchTab("sdc")}
          >
            SDC Giro
          </button>
        </div>

        {tab === "flash" ? (
          <>
            <label>
              Valor do ativo / base de cálculo
              <input
                name="asset_value"
                type="number"
                min="10000"
                step="1000"
                defaultValue="1000000"
                required
              />
            </label>
            <label>
              Valor pretendido (até 40% do AVM)
              <input
                name="requested_amount"
                type="number"
                min="1"
                step="0.01"
                placeholder="Ex.: 400.000"
              />
            </label>
          </>
        ) : (
          <>
            <label>Cotas para composição</label>
            <div className="site-quota-list">
              {catalog.map((q) => (
                <label key={q.id}>
                  <input
                    type="checkbox"
                    checked={selectedQuotas.includes(q.id)}
                    onChange={() => toggleQuota(q.id)}
                  />
                  Grupo {q.group_code} · Cota {q.quota_code} — {brl.format(Number(q.credit_value))}
                </label>
              ))}
            </div>
            <label>
              Valor alvo da operação
              <input
                name="requested_amount"
                type="number"
                min="1"
                step="0.01"
                defaultValue="800000"
                required
              />
            </label>
            <label>
              Prazo, em meses
              <input name="duration_months" type="number" min="1" max="120" defaultValue={12} required />
            </label>
          </>
        )}

        <label>
          Razão social
          <input name="razao" type="text" placeholder="Empresa Exemplo Ltda." required />
        </label>
        <label>
          WhatsApp corporativo
          <input name="whatsapp" type="text" placeholder="(00) 00000-0000" required />
        </label>
        <label className="consent">
          <input name="bacen" type="checkbox" required />
          <span>
            Autorizo a consulta ao histórico de crédito no{" "}
            <strong>SCR / Registrato do Banco Central</strong>, incluindo varredura cadastral
            automática em background, exclusivamente para análise desta simulação e qualificação
            comercial pela LETTER.
          </span>
        </label>
        <button className="button full" type="submit" disabled={loading}>
          {loading ? "Calculando…" : "Calcular estrutura"} <span>→</span>
        </button>
        {error && <p className="form-notice">{error}</p>}
        <small className="legal-copy">
          Ao calcular, seus dados corporativos são registrados no funil comercial. A simulação é
          indicativa e não constitui proposta de crédito nem consulta automática imediata ao Bacen.
        </small>
      </form>

      <div className="sim-output">
        <div className="output-head">
          <div>
            <span>Memória de cálculo</span>
            <h3>{tab === "flash" ? "Flash Capital" : "SDC Giro"}</h3>
          </div>
          <span className="status-pill">
            {tab === "flash" ? "PRICE · 2,5% a.m." : "BULLET · 4,5% a.m."}
          </span>
        </div>

        <div className={`output-content${unlocked ? "" : " locked"}`} aria-live="polite">
          {tab === "flash" ? (
            <FlashOutput data={displayFlash} />
          ) : (
            <SdcOutput data={displaySdc} />
          )}
        </div>

        {!unlocked && (
          <div className="gate">
            <span className="lock">◆</span>
            <h4>Memória protegida</h4>
            <p>
              Preencha razão social, WhatsApp e autorize a consulta SCR/Registrato para destravar a
              memória de cálculo e registrar o lead.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function FlashOutput({ data }: { data: FlashMockResult }) {
  const margin =
    data.mmn.holding_retained_from_fee != null
      ? Number(data.mmn.holding_retained_from_fee)
      : Number(data.platform_fee) -
        (data.mmn.commission_pool ? Number(data.mmn.commission_pool) : 0);

  return (
    <>
      <div className="primary-result">
        <span>Crédito base · LTV 40%</span>
        <strong>{brl.format(Number(data.principal))}</strong>
      </div>
      <div className="result-grid">
        <div>
          <span>Fee de estruturação</span>
          <b>{brl.format(Number(data.platform_fee))}</b>
        </div>
        <div>
          <span>Provisão ITBI</span>
          <b>{brl.format(Number(data.itbi_provision))}</b>
        </div>
        <div>
          <span>Saque líquido estimado</span>
          <b className="green">{brl.format(Number(data.net_payout))}</b>
        </div>
        <div>
          <span>Comissão de canal</span>
          <b>
            {data.mmn.commission_pool ? brl.format(Number(data.mmn.commission_pool)) : "—"}
          </b>
        </div>
      </div>
      <div className="result-bar">
        <span>Margem institucional estimada</span>
        <b>{Number.isFinite(margin) ? brl.format(margin) : "—"}</b>
      </div>
      <MmnNote mmn={data.mmn} />
    </>
  );
}

function SdcOutput({ data }: { data: SdcMockResult }) {
  return (
    <>
      <div className="primary-result">
        <span>Principal estruturado</span>
        <strong>{brl.format(Number(data.output.principal))}</strong>
      </div>
      <div className="result-grid">
        <div>
          <span>Juros no período</span>
          <b>{brl.format(Number(data.output.total_interest))}</b>
        </div>
        <div>
          <span>Taxa de abertura</span>
          <b>{brl.format(Number(data.output.start_fee_total))}</b>
        </div>
        <div>
          <span>Total na maturidade</span>
          <b className="green">{brl.format(Number(data.output.maturity_total))}</b>
        </div>
        <div>
          <span>Comissão de captação</span>
          <b>{brl.format(Number(data.output.capital_commission))}</b>
        </div>
      </div>
      <div className="result-bar">
        <span>Intermediação estimada</span>
        <b>{brl.format(Number(data.output.intermediation_fee))}</b>
      </div>
      <MmnNote mmn={data.mmn} />
    </>
  );
}

function MmnNote({ mmn }: { mmn: MmnPreview }) {
  if (mmn.configured) return null;
  return (
    <p className="legal-copy" style={{ marginTop: 16 }}>
      Rede comercial: {mmn.message ?? "Regra não configurada na plataforma."}
    </p>
  );
}

export function SiteNav() {
  return (
    <nav className="nav-shell" aria-label="Navegação principal">
      <Link href="/" className="logo" aria-label="LETTER — início">
        <Image
          className="logo-image"
          src="/brand/letter-logo-oficial.png"
          alt="LETTER — O Shopping do Crédito Seguro e Inteligente"
          width={1200}
          height={550}
          priority
        />
      </Link>
      <div className="nav-links">
        <a href="#atendimento">Atendimento</a>
        <a href="#solucoes">Soluções</a>
        <a href="#simulador">Simuladores</a>
        <a href="#nina">Nina Engine</a>
        <a href="#flash-invest">Flash Invest</a>
        <a href="#leilao">Leilão</a>
      </div>
      <Link href="/login" className="button button-small">
        Deal Room <span>→</span>
      </Link>
    </nav>
  );
}
