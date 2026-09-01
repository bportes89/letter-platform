"use client";

import { BookOpen, Download, FileText, LockKeyhole } from "lucide-react";
import { useEffect, useState } from "react";
import { api, LegalManual } from "@/lib/api";

const API_URL = (process.env.NEXT_PUBLIC_API_URL?.trim() || "http://localhost:8000/api/v1").replace(/\s+/g, "");

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function LegalManualsModule() {
  const [items, setItems] = useState<LegalManual[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    void api<LegalManual[]>("/legal-manuals").then(setItems).catch((e) => setMessage(e instanceof Error ? e.message : "Falha ao carregar manuais"));
  }, []);

  async function download(slug: string, title: string) {
    try {
      const token = localStorage.getItem("letter_access_token");
      const response = await fetch(`${API_URL}/legal-manuals/${slug}/download`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) throw new Error("Download indisponível");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${slug}.docx`;
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage(`Download iniciado: ${title}`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Falha no download");
    }
  }

  const grouped = items.reduce<Record<string, LegalManual[]>>((acc, item) => {
    acc[item.category] = acc[item.category] ?? [];
    acc[item.category].push(item);
    return acc;
  }, {});

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow dark">DOCUMENTAÇÃO JURÍDICA</span>
          <h1>Manuais e contratos</h1>
          <p>Templates homologados pela franqueadora para assinatura e operação na plataforma.</p>
        </div>
        <div className="operational-icon"><BookOpen /></div>
      </div>
      {message && <div className="notice"><FileText />{message}</div>}
      {Object.entries(grouped).map(([category, rows]) => (
        <section className="panel" key={category}>
          <h2>{category}</h2>
          <div className="contract-grid">
            {rows.map((item) => (
              <article className="contract-card" key={item.slug}>
                <b>{item.title}</b>
                <span className="pill pill-active">{item.product}</span>
                <small>{item.description}</small>
                <small>Público: {item.audience}</small>
                <small>{item.available ? formatSize(item.size_bytes) : "Arquivo indisponível"}</small>
                <button className="table-action" disabled={!item.available} onClick={() => void download(item.slug, item.title)}>
                  <Download /> Baixar .docx
                </button>
              </article>
            ))}
          </div>
        </section>
      ))}
    </>
  );
}
