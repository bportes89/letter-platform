"use client";

import Link from "next/link";
import {
  DEMO_AUCTION_LOTS,
  DEMO_FLASH_INVEST,
  type PublicAuctionItem,
  type PublicFlashInvestItem,
} from "@/lib/public-gated-vitrine";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function GatedSensitiveBlock({
  label,
  lines,
  loginHint,
}: {
  label: string;
  lines: string[];
  loginHint: string;
}) {
  return (
    <div className="gated-sensitive">
      <span className="gated-label">{label}</span>
      <div className="gated-blur" aria-hidden="true">
        {lines.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>
      <div className="gated-wall">
        <span className="lock">◆</span>
        <p>{loginHint}</p>
        <Link href="/login" className="gated-cta">
          Abrir conta / Entrar <span>→</span>
        </Link>
      </div>
    </div>
  );
}

function FlashInvestCard({ item }: { item: PublicFlashInvestItem }) {
  const pct = Math.min(100, Math.round((item.funded_amount / item.target_amount) * 100));

  return (
    <article className="gated-card">
      <div className="gated-card-head">
        <span className={`status-pill${item.status === "CAPTANDO" ? "" : " amber"}`}>{item.status}</span>
        <span>{item.ref}</span>
      </div>
      <h3>{item.title}</h3>
      <p className="gated-card-meta">
        {item.product === "FLASH_POOL" ? "Flash Invest · Pool" : "Flash Invest · SDC Pool"} ·{" "}
        {item.term_months} meses
      </p>

      <div className="gated-metrics">
        <div>
          <span>Meta de captação</span>
          <b>{brl.format(item.target_amount)}</b>
        </div>
        <div>
          <span>Aporte mínimo (1 token)</span>
          <b>{brl.format(item.min_investment)}</b>
        </div>
      </div>

      <div className="funding-progress">
        <i style={{ width: `${pct}%` }} />
      </div>
      <small className="gated-progress-note">
        {brl.format(item.funded_amount)} captados ({pct}%) · {item.rate_reference}
      </small>

      <GatedSensitiveBlock
        label="Dados da operação (protegidos)"
        lines={[item.sensitive.borrower, item.sensitive.collateral, item.sensitive.registry, item.sensitive.operation_id]}
        loginHint="Tomador, lastro, matrícula e memória completa disponíveis após abrir conta e login no Deal Room."
      />
    </article>
  );
}

function AuctionCard({ item }: { item: PublicAuctionItem }) {
  return (
    <article className="gated-card gated-card-auction">
      <div className="gated-card-visual">
        <span>{item.ref}</span>
        <div className="building">
          <i />
          <i />
          <i />
          <i />
        </div>
      </div>
      <div className="gated-card-body">
        <div className="gated-card-head">
          <span className={`status-pill${item.status === "ABERTO" ? "" : " amber"}`}>{item.status}</span>
          <span>{item.ref}</span>
        </div>
        <h3>{item.title}</h3>
        <div className="gated-metrics">
          <div>
            <span>Valor AVM</span>
            <b>{brl.format(item.avm)}</b>
          </div>
          <div>
            <span>Lance inicial</span>
            <b>{brl.format(item.opening_price)}</b>
          </div>
        </div>
        <small className="gated-progress-note">
          LTV indicativo {item.ltv_percent}% · {item.ends_label}
        </small>

        <GatedSensitiveBlock
          label="Ficha do lote (protegida)"
          lines={[item.sensitive.address, item.sensitive.registry, item.sensitive.owner]}
          loginHint="Endereço, matrícula RGI e partes relacionadas exigem conta habilitada e login autenticado."
        />
      </div>
    </article>
  );
}

export function FlashInvestSection() {
  return (
    <section id="flash-invest" className="section vitrine-section">
      <div className="section-kicker">04 · Flash Invest</div>
      <div className="section-heading">
        <h2>
          Oportunidades de pool.
          <br />
          <em>Dados sob governança.</em>
        </h2>
        <p>
          Vitrine pública com indicadores de captação. Detalhes do tomador, lastro e memória da operação
          permanecem ofuscados até abertura de conta e login.
        </p>
      </div>
      <div className="gated-grid">
        {DEMO_FLASH_INVEST.map((item) => (
          <FlashInvestCard key={item.id} item={item} />
        ))}
      </div>
      <p className="vitrine-footnote">
        Após login, investidores habilitados acessam reservas, posições e documentação no módulo{" "}
        <strong>Funding e investimentos</strong> do Deal Room.
      </p>
    </section>
  );
}

export function AuctionSection() {
  return (
    <section id="leilao" className="section vitrine-section vitrine-auction">
      <div className="section-kicker">05 · Campo de Leilão</div>
      <div className="section-heading">
        <h2>
          Ativos recuperados.
          <br />
          <em>Anti-bypass ativo.</em>
        </h2>
        <p>
          Lotes derivados de inadimplência contratual com informações essenciais na vitrine. Matrícula,
          endereço e identificação do proprietário exigem autenticação.
        </p>
      </div>
      <div className="gated-grid gated-grid-auction">
        {DEMO_AUCTION_LOTS.map((item) => (
          <AuctionCard key={item.id} item={item} />
        ))}
      </div>
      <p className="vitrine-footnote">
        Participação, habilitação e lances ficam no módulo <strong>Leilões LETTER</strong>, disponível após
        login e validação de perfil.
      </p>
    </section>
  );
}
