"use client";

import { Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, apiForm } from "@/lib/api";

const URBAN_ROOMS = [
  { key: "SALA", label: "Sala" },
  { key: "COZINHA", label: "Cozinha" },
  { key: "BANHEIRO", label: "Banheiro" },
  { key: "QUARTO", label: "Quarto" },
  { key: "SUITE", label: "Suíte" },
  { key: "AREA_LAZER", label: "Área de lazer" },
  { key: "AREA_GOURMET", label: "Área gourmet" },
] as const;

type PropertyRow = {
  matricula: string;
  zone?: string;
  lot_type?: string;
};

type Props = {
  desk: "sdc" | "flash";
  solicitationId: string;
  properties: PropertyRow[];
  disabled?: boolean;
};

export function DeskPropertyInspectionPanel({ desk, solicitationId, properties, disabled }: Props) {
  const base = desk === "sdc" ? "/sdc/desk" : "/flash/desk";
  const [blocks, setBlocks] = useState<Record<string, Record<string, unknown>>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const mats = properties.map((p) => p.matricula.trim()).filter(Boolean);

  const load = useCallback(async () => {
    if (!solicitationId) return;
    const row = await api<Record<string, unknown>>(`${base}/solicitations/${solicitationId}`);
    const insp = (row.property_inspections_json as Array<Record<string, unknown>>) || [];
    const map: Record<string, Record<string, unknown>> = {};
    for (const b of insp) {
      const m = String(b.matricula || "").trim();
      if (m) map[m] = b;
    }
    setBlocks(map);
  }, [base, solicitationId]);

  useEffect(() => {
    void load().catch(() => undefined);
  }, [load]);

  async function saveBlock(matricula: string, patch: Record<string, unknown>) {
    setError("");
    setBusy(true);
    try {
      const prop = properties.find((p) => p.matricula.trim() === matricula);
      const zone = String(prop?.zone || "URBANO").toUpperCase();
      await api(`${base}/solicitations/${solicitationId}/property-inspection`, {
        method: "PATCH",
        body: JSON.stringify({ matricula, zone, ...patch }),
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar autovistoria");
    } finally {
      setBusy(false);
    }
  }

  async function capturePhoto(matricula: string, photoKey: string, file: File) {
    setError("");
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("matricula", matricula);
      fd.append("photo_key", photoKey);
      fd.append("camera_native", "true");
      await apiForm(`${base}/solicitations/${solicitationId}/property-inspection/photo`, fd);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao enviar foto");
    } finally {
      setBusy(false);
    }
  }

  if (!mats.length) return null;

  return (
    <div className="stack-form" style={{ gridColumn: "1 / -1", borderTop: "1px solid var(--line)", paddingTop: 12 }}>
      <b style={{ fontSize: 12 }}>Autovistoria por matrícula (fotos na hora)</b>
      <small className="muted" style={{ fontSize: 10 }}>
        Informe área e cômodos antes das fotos. Use a câmera do celular — não envie da galeria. Fotos alimentarão o laudo de autovistoria após análise e TAPAF.
      </small>
      {error && <div className="error" style={{ fontSize: 11 }}>{error}</div>}
      {mats.map((mat) => {
        const prop = properties.find((p) => p.matricula.trim() === mat);
        const zone = String(prop?.zone || "URBANO").toUpperCase();
        const block = blocks[mat] || { matricula: mat, zone, rooms: {}, photos: {} };
        const rooms = (block.rooms as Record<string, number>) || {};
        const photos = (block.photos as Record<string, unknown[]>) || {};
        const lotType = String(block.lot_type || prop?.lot_type || "").toUpperCase();
        return (
          <div key={mat} style={{ padding: 12, border: "1px solid var(--line)", borderRadius: 10, background: "#fafcfb" }}>
            <b style={{ fontSize: 11 }}>Matrícula {mat}</b>
            {zone === "URBANO" && (
              <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                <label style={{ fontSize: 11, fontWeight: 700 }}>
                  Tipo
                  <select
                    value={lotType}
                    disabled={disabled || busy}
                    onChange={(e) => void saveBlock(mat, { lot_type: e.target.value, zone: "URBANO" })}
                    style={{ width: "100%", marginTop: 4, padding: 8, borderRadius: 8, fontWeight: 400 }}
                  >
                    <option value="">Imóvel completo</option>
                    <option value="LOTE">Lote urbano (mín. 5 fotos + rua)</option>
                  </select>
                </label>
                {lotType !== "LOTE" && (
                  <>
                    <label style={{ fontSize: 11, fontWeight: 700 }}>
                      Área construída (m²)
                      <input
                        type="number"
                        min={1}
                        disabled={disabled || busy}
                        value={String(block.built_area_m2 ?? "")}
                        onChange={(e) => setBlocks((prev) => ({
                          ...prev,
                          [mat]: { ...block, built_area_m2: e.target.value },
                        }))}
                        onBlur={() => void saveBlock(mat, {
                          built_area_m2: block.built_area_m2,
                          rooms,
                          zone: "URBANO",
                          lot_type: lotType,
                        })}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </label>
                    <div style={{ display: "grid", gap: 6, gridTemplateColumns: "repeat(3, 1fr)" }}>
                      {URBAN_ROOMS.map((r) => (
                        <label key={r.key} style={{ fontSize: 10, fontWeight: 700 }}>
                          {r.label}
                          <input
                            type="number"
                            min={0}
                            disabled={disabled || busy}
                            value={rooms[r.key] ?? ""}
                            onChange={(e) => {
                              const next = { ...rooms, [r.key]: Number(e.target.value) || 0 };
                              void saveBlock(mat, { rooms: next, zone: "URBANO", built_area_m2: block.built_area_m2, lot_type: lotType });
                            }}
                            style={{ width: "100%", marginTop: 2 }}
                          />
                        </label>
                      ))}
                    </div>
                  </>
                )}
                {["EXTERNA", "RUA", ...(lotType === "LOTE" ? [] : ["SALA", "COZINHA"])].map((slot) => (
                  <PhotoSlotRow
                    key={slot}
                    label={slot.replace(/_/g, " ")}
                    count={(photos[slot] as unknown[])?.length || 0}
                    disabled={disabled || busy}
                    onCapture={(f) => void capturePhoto(mat, slot, f)}
                  />
                ))}
                {!lotType && (rooms.QUARTO || 0) > 0 && Array.from({ length: Number(rooms.QUARTO) }, (_, i) => (
                  <PhotoSlotRow
                    key={`q${i}`}
                    label={`QUARTO ${i + 1}`}
                    count={(photos[`QUARTO_${i + 1}`] as unknown[])?.length || 0}
                    disabled={disabled || busy}
                    onCapture={(f) => void capturePhoto(mat, `QUARTO_${i + 1}`, f)}
                  />
                ))}
              </div>
            )}
            {zone === "RURAL" && (
              <div style={{ display: "grid", gap: 8, marginTop: 8, fontSize: 11 }}>
                <p className="muted" style={{ margin: 0 }}>Rural: informe melhorias e áreas antes das fotos (mín. 5 da fazenda).</p>
                {[
                  { key: "has_improvements", label: "Há melhorias (currais, resfriadores…)" },
                  { key: "has_productive_areas", label: "Possui áreas produtivas" },
                  { key: "has_headquarters", label: "Imóvel construído / sede na área" },
                ].map((flag) => (
                  <label key={flag.key} style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 700 }}>
                    <input
                      type="checkbox"
                      disabled={disabled || busy}
                      checked={Boolean((block.rural as Record<string, unknown>)?.[flag.key])}
                      onChange={(e) => {
                        const rural = { ...(block.rural as Record<string, unknown>), [flag.key]: e.target.checked };
                        void saveBlock(mat, { zone: "RURAL", rural });
                      }}
                    />
                    {flag.label}
                  </label>
                ))}
                {["FAZENDA", "MELHORIAS", "AREA_PRODUTIVA", "SEDE"].map((slot) => (
                  <PhotoSlotRow
                    key={slot}
                    label={slot}
                    count={(photos[slot] as unknown[])?.length || 0}
                    disabled={disabled || busy}
                    onCapture={(f) => void capturePhoto(mat, slot, f)}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function PhotoSlotRow({
  label,
  count,
  disabled,
  onCapture,
}: {
  label: string;
  count: number;
  disabled?: boolean;
  onCapture: (file: File) => void;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
      <span style={{ fontSize: 11, fontWeight: 700, minWidth: 120 }}>{label}</span>
      <span className="muted" style={{ fontSize: 10 }}>{count} foto(s)</span>
      <label className="table-action" style={{ cursor: disabled ? "not-allowed" : "pointer" }}>
        <Plus size={14} />
        Câmera
        <input
          type="file"
          accept="image/*"
          capture="environment"
          disabled={disabled}
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onCapture(f);
            e.target.value = "";
          }}
        />
      </label>
    </div>
  );
}
