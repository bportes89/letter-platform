"use client";

import Link from "next/link";
import { Suspense } from "react";
import "./site.css";
import { AttendanceBotSection } from "@/components/public-site/attendance-bot";
import { AuctionSection, FlashInvestSection } from "@/components/public-site/gated-vitrine-section";
import { PublicSimulatorSection, SiteNav } from "@/components/public-site/simulator-section";

export default function PublicHomePage() {
  return (
    <div className="site-root">
      <main>
        <SiteNav />

        <header id="top" className="hero">
          <div className="hero-grid">
            <div className="hero-copy">
              <p className="eyebrow">
                <span /> Infraestrutura fiduciária · 2026
              </p>
              <h1>
                Capital estruturado para empresas que precisam <em>avançar.</em>
              </h1>
              <p className="hero-lead">
                Tecnologia fiduciária, engenharia financeira e ativos reais em uma infraestrutura B2B
                desenhada para decisões de alta governança.
              </p>
              <div className="hero-actions">
                <a className="button" href="#simulador">
                  Simular operação <span>→</span>
                </a>
                <a className="text-link" href="#solucoes">
                  Conhecer o ecossistema <span>↓</span>
                </a>
              </div>
            </div>

            <div className="ledger-card">
              <div className="ledger-head">
                <span>LETTER_SPE_LEDGER</span>
                <span className="live">
                  <i /> SISTEMA ONLINE
                </span>
              </div>
              <div className="ledger-main">
                <span>Pipeline corporativo bruto</span>
                <strong>R$ 297 mi</strong>
                <small>em ativos sob análise estruturada</small>
              </div>
              <div className="ledger-stats">
                <div>
                  <span>Crivo estimado</span>
                  <strong>60,00%</strong>
                  <small>capacidade elegível</small>
                </div>
                <div>
                  <span>LTV máximo</span>
                  <strong className="blue">40,00%</strong>
                  <small>mitigação de risco</small>
                </div>
              </div>
              <div className="ledger-foot">
                <span>◆ AUDIT TRAIL ATIVO</span>
                <span>HASH 8F2…9A1…C04</span>
              </div>
            </div>
          </div>

          <div className="trust-row">
            <span>Arquitetura orientada a</span>
            <b>Governança</b>
            <b>Auditoria</b>
            <b>Compliance</b>
            <b>RWA</b>
          </div>
        </header>

        <AttendanceBotSection />

        <section id="solucoes" className="section solutions">
          <div className="section-kicker">01 · Ecossistema</div>
          <div className="section-heading">
            <h2>
              Duas esteiras.
              <br />
              Uma infraestrutura.
            </h2>
            <p>
              A LETTER conecta ativos patrimoniais a estruturas de capital com regras claras,
              rastreabilidade e gestão centralizada.
            </p>
          </div>
          <div className="solution-grid">
            <article className="solution-card featured">
              <div className="card-index">01</div>
              <div className="icon-box">↗</div>
              <h3>Flash Capital</h3>
              <p>
                Pacto de retrovenda com liquidez baseada em imóvel, LTV conservador e estruturação
                fiduciária.
              </p>
              <ul>
                <li>
                  <span>Taxa estrutural</span>
                  <b>2,5% a.m.</b>
                </li>
                <li>
                  <span>Limite de LTV</span>
                  <b>até 40%</b>
                </li>
                <li>
                  <span>Modelo</span>
                  <b>Tabela Price</b>
                </li>
              </ul>
              <a href="#simulador">
                Simular Flash Capital <span>→</span>
              </a>
            </article>

            <article className="solution-card">
              <div className="card-index">02</div>
              <div className="icon-box emerald">◎</div>
              <h3>SDC Giro</h3>
              <p>
                Capital de giro estruturado por consórcio, com cupom mensal e maturidade bullet final.
              </p>
              <ul>
                <li>
                  <span>Taxa estrutural</span>
                  <b>4,5% a.m.</b>
                </li>
                <li>
                  <span>Amortização</span>
                  <b>Bullet final</b>
                </li>
                <li>
                  <span>Modelo</span>
                  <b>Juros simples</b>
                </li>
              </ul>
              <a href="#simulador">
                Simular SDC Giro <span>→</span>
              </a>
            </article>
          </div>
        </section>

        <section id="simulador" className="section simulator-section">
          <div className="section-kicker">02 · FinOps Engine</div>
          <div className="section-heading">
            <h2>
              Engenharia financeira,
              <br />
              <em>sem caixa-preta.</em>
            </h2>
            <p>
              Simule cenários e visualize a memória de cálculo da operação. Valores indicativos, sujeitos
              à análise e validação jurídica.
            </p>
          </div>
          <Suspense fallback={<div className="simulator-shell">Carregando simulador…</div>}>
            <PublicSimulatorSection />
          </Suspense>
        </section>

        <section id="nina" className="section nina-section">
          <div className="nina-orbit">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="nina-core">
              N<span>◆</span>
            </div>
          </div>
          <div className="nina-copy">
            <div className="section-kicker">03 · Intelligence Layer</div>
            <h2>
              Nina Engine.
              <br />
              <em>Decisão aumentada.</em>
            </h2>
            <p>
              Uma camada de inteligência para organizar sinais operacionais, acompanhar a esteira e apoiar
              a análise de oportunidades com rastreabilidade.
            </p>
            <div className="nina-features">
              <span>Qualificação de leads</span>
              <span>Auditoria de dados</span>
              <span>Monitoramento de carteira</span>
            </div>
          </div>
        </section>

        <FlashInvestSection />
        <AuctionSection />

        <section id="contato" className="section cta-section">
          <div>
            <span className="section-kicker">Próximo movimento</span>
            <h2>
              Estruture capital.
              <br />
              <em>Preserve valor.</em>
            </h2>
          </div>
          <Link href="/login" className="button light">
            Abrir conta / Deal Room <span>→</span>
          </Link>
        </section>

        <footer className="site-footer">
          <Link href="/" className="logo" aria-label="LETTER — início">
            <img
              className="logo-image logo-image-footer"
              src="/brand/letter-logo-oficial.png"
              alt="LETTER — O Shopping do Crédito Seguro e Inteligente"
            />
          </Link>
          <p>Infraestrutura fiduciária e tecnologia para operações empresariais.</p>
          <div>
            <span>© 2026 LETTER</span>
            <Link href="/simulador/quitcon">Quitação consórcio</Link>
            <Link href="/login">Deal Room</Link>
          </div>
        </footer>
      </main>
    </div>
  );
}
