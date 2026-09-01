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

  if (!items.length) return null;

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
          Manuais e contratos
          <br />
          <em>acesso exclusivo para contas LETTER.</em>
        </h2>
        <p>
          Consulte os templates jurídicos por produto. A visualização e download completos exigem login na Deal Room.
        </p>
      </div>
      <div className="manuals-grid">
        {Object.entries(grouped).map(([category, rows]) => (
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
                    <LockKeyhole size={14} /> Abrir conta para acessar
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
          <strong>Biblioteca jurídica na área logada</strong>
          <p>Após criar sua conta, acesse <b>Plataforma → Manuais e contratos</b> para baixar os arquivos .docx.</p>
        </div>
        <Link className="button" href="/login?next=/modules/legal-manuals">
          Entrar na Deal Room <span>→</span>
        </Link>
      </div>
    </section>
  );
}
