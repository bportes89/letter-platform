"use client";

import { CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { API_URL } from "@/lib/api";
import "../site.css";

type TapafUi = {
  valor_nominal_taxa: string;
  checkbox_obrigatorio_01: string;
  checkbox_obrigatorio_02: string;
  manifesto_html: string;
  checkout_url?: string | null;
  checkout_mode?: string;
  botao_label?: string;
  botao_habilitado?: boolean;
};

function TapafFlashForm() {
  const searchParams = useSearchParams();
  const solicitationId = searchParams.get("solicitation_id") || "";
  const token = searchParams.get("token") || "";
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [contactName, setContactName] = useState("");
  const [ui, setUi] = useState<TapafUi | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [scrollDone, setScrollDone] = useState(false);
  const [cb1, setCb1] = useState(false);
  const [cb2, setCb2] = useState(false);
  const [busy, setBusy] = useState(false);

  const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

  useEffect(() => {
    if (!solicitationId || !token) {
      setError("Link incompleto. Solicite um novo link ao seu consultor LETTER.");
      setLoading(false);
      return;
    }
    fetch(`${API_URL}/public/flash-desk/tapaf/${solicitationId}/${token}`)
      .then(async (r) => {
        const body = await r.json();
        if (!r.ok) throw new Error(body.detail || "Link inválido");
        setContactName(body.contact_name || "");
        setUi(body.interface_checkout_tapaf || null);
        setAccepted(Boolean(body.checkout_accepted));
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar TAPAF"))
      .finally(() => setLoading(false));
  }, [solicitationId, token]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await fetch(`${API_URL}/public/flash-desk/tapaf/${solicitationId}/${token}/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scroll_completed: scrollDone, checkbox_1: cb1, checkbox_2: cb2 }),
      });
      const body = await r.json();
      if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : body.detail?.message || "Falha no aceite");
      setUi(body.interface_checkout_tapaf || ui);
      setAccepted(true);
      setNotice("Aceite registrado. Use o botão abaixo para abrir o boleto ou Pix da TAPAF.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no aceite TAPAF");
    } finally {
      setBusy(false);
    }
  }

  function openPayment() {
    const url = ui?.checkout_url || "";
    const mode = (ui?.checkout_mode || "").toUpperCase();
    if (url.startsWith("http")) {
      window.open(url, "_blank", "noopener,noreferrer");
      return;
    }
    setNotice("Aguarde: a cobrança está sendo gerada. Atualize a página em alguns instantes ou contate a LETTER.");
  }

  if (loading) return <p className="muted" style={{ padding: 24 }}>Carregando TAPAF…</p>;

  return (
    <main style={{ maxWidth: 560, margin: "40px auto", padding: "0 20px" }}>
      <h1 style={{ fontSize: "1.35rem" }}>TAPAF — Flash Capital</h1>
      <p className="muted" style={{ lineHeight: 1.5 }}>
        {contactName ? <>Olá, <b>{contactName}</b>. </> : null}
        O tomador do crédito deve ler o manifesto e aceitar a taxa de abertura (TAPAF) antes do pagamento.
      </p>
      {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}
      {notice && <div className="notice" style={{ marginTop: 12 }}><CheckCircle2 />{notice}</div>}
      {ui && (
        <form className="stack-form" style={{ marginTop: 20 }} onSubmit={(e) => void submit(e)}>
          <p><b>Valor:</b> {brl.format(Number(ui.valor_nominal_taxa))}</p>
          <div className="manifest-scroll" style={{ maxHeight: 200, border: "1px solid var(--line)", padding: 12, borderRadius: 8 }} dangerouslySetInnerHTML={{ __html: ui.manifesto_html }} />
          {!accepted ? (
            <>
              <label className="tapaf-check">
                <input type="checkbox" checked={scrollDone} onChange={(e) => setScrollDone(e.target.checked)} />
                <span>Li o manifesto TAPAF até o final.</span>
              </label>
              <label className="tapaf-check">
                <input type="checkbox" checked={cb1} onChange={(e) => setCb1(e.target.checked)} />
                <span>{ui.checkbox_obrigatorio_01}</span>
              </label>
              <label className="tapaf-check">
                <input type="checkbox" checked={cb2} onChange={(e) => setCb2(e.target.checked)} />
                <span>{ui.checkbox_obrigatorio_02}</span>
              </label>
              <button type="submit" className="admin-button" disabled={busy || !scrollDone || !cb1 || !cb2}>
                Aceitar TAPAF
              </button>
            </>
          ) : (
            <button type="button" className="admin-button" onClick={openPayment}>
              {ui.botao_label || "Abrir boleto / Pix TAPAF"}
            </button>
          )}
        </form>
      )}
      <p style={{ marginTop: 24, fontSize: 12 }}>
        <Link href="/">Voltar ao site LETTER</Link>
      </p>
    </main>
  );
}

export default function TapafFlashPage() {
  return (
    <Suspense fallback={<p style={{ padding: 24 }}>Carregando…</p>}>
      <TapafFlashForm />
    </Suspense>
  );
}
