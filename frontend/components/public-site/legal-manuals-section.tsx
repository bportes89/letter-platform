"use client";

import { FileText, LockKeyhole } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, LegalManualPublic } from "@/lib/api";

export function LegalManualsPublicSection() {
  const [items, setItems] = useState<LegalManualPublic[]>([]);

  useEffect(() => {
    void api<LegalManualPublic[]>("/platform/legal-manuals").then(setItems).catch(() => setItems([]));
  }, []);

  const grouped = items.reduce<Record<string, LegalManualPublic[]>>((acc, item) => {
    acc[item.category] = acc[item.category] ?? [];
    acc[item.category].push(item);
    return acc;
  }, {});

  return (
    <section id="manuais" className="section manuals-section">
      <div className="section-kicker">03 · Documentação</div>
      <div className="section-heading">
        <h2>
          Manuais operacionais
          <br />
          <em>consulta pública · download na área logada.</em>
        </h2>
        <p>
          Consulte os manuais por produto. O download completo exige login na plataforma. Contratos ficam disponíveis
          somente na área logada, após assinatura do serviço contratado.
        </p>
      </div>
      <div className="manuals-grid">
        {items.length === 0 ? (
          <p className="site-light-muted" style={{ margin: 0 }}>
            Carregando manuais… Se nada aparecer, atualize a página em instantes.
          </p>
        ) : Object.entries(grouped).map(([category, rows]) => (
          <article className="manuals-group" key={category}>
            <h3>{category}</h3>
            <ul>
              {rows.map((item) => (
                <li key={item.slug}>
                  <div>
                    <strong>{item.title}</strong>
                    <small>{item.product} · {item.audience}</small>
                  </div>
                  <Link className="manuals-lock-link" href="/login?next=/modules/legal-manuals">
                    <LockKeyhole size={14} /> Entrar para baixar
                  </Link>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
      <div className="manuals-cta">
        <FileText />
        <div>
          <strong>Biblioteca na área logada</strong>
          <p>Após criar sua conta, acesse <b>Plataforma → Manuais e contratos</b> para baixar manuais e contratos assinados.</p>
        </div>
        <Link className="button" href="/login?next=/modules/legal-manuals">
          Acessar conta <span>→</span>
        </Link>
      </div>
    </section>
  );
}
