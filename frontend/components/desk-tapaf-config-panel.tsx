"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type TapafConfig = {
  SDC: string;
  FLASH: string;
  QUITCON_ALIENACAO: string;
};

export function DeskTapafConfigPanel() {
  const [cfg, setCfg] = useState<TapafConfig>({ SDC: "1500", FLASH: "1500", QUITCON_ALIENACAO: "1500" });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<TapafConfig>("/desk/tapaf-config")
      .then(setCfg)
      .catch(() => setError("Não foi possível carregar valores TAPAF."));
  }, []);

  async function save() {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const saved = await api<TapafConfig>("/desk/tapaf-config", {
        method: "PUT",
        body: JSON.stringify({
          SDC: cfg.SDC.replace(",", "."),
          FLASH: cfg.FLASH.replace(",", "."),
          QUITCON_ALIENACAO: cfg.QUITCON_ALIENACAO.replace(",", "."),
        }),
      });
      setCfg(saved);
      setNotice("Valores TAPAF atualizados.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ padding: 12, border: "1px solid var(--line)", borderRadius: 10, background: "#f7fbf9", marginTop: 12 }}>
      <b style={{ fontSize: 12 }}>Valores TAPAF (operação LETTER)</b>
      <p className="muted" style={{ fontSize: 10, margin: "6px 0 10px" }}>
        SDC, Flash Capital e TAPAF do bem alienado (QuitCon). Alterações valem para novos checkouts gerados.
      </p>
      <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(3, 1fr)" }}>
        {(["SDC", "FLASH", "QUITCON_ALIENACAO"] as const).map((key) => (
          <label key={key} style={{ fontSize: 11, fontWeight: 700 }}>
            {key === "QUITCON_ALIENACAO" ? "QuitCon alienação" : key}
            <input
              value={cfg[key]}
              disabled={busy}
              onChange={(e) => setCfg((prev) => ({ ...prev, [key]: e.target.value }))}
              style={{ width: "100%", marginTop: 4, padding: 8, borderRadius: 8, fontWeight: 400 }}
            />
          </label>
        ))}
      </div>
      {error && <div className="error" style={{ fontSize: 11, marginTop: 8 }}>{error}</div>}
      {notice && <div className="notice" style={{ fontSize: 11, marginTop: 8 }}>{notice}</div>}
      <button type="button" className="admin-button" style={{ marginTop: 10 }} disabled={busy} onClick={() => void save()}>
        Salvar TAPAF
      </button>
    </div>
  );
}
