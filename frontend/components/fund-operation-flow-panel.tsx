"use client";

import { CheckCircle2, Clock3, Hourglass } from "lucide-react";

export type FundOperationFlowStep = {
  code: string;
  title: string;
  description: string;
  status: "COMPLETED" | "IN_PROGRESS" | "PENDING";
};

export type FundOperationFlow = {
  version?: number;
  deadline_days?: number;
  disclaimer?: string;
  steps: FundOperationFlowStep[];
  updated_at?: string;
};

function statusLabel(status: string) {
  if (status === "COMPLETED") return "Concluído";
  if (status === "IN_PROGRESS") return "Em andamento · próximo passo";
  return "Pendente";
}

function StatusIcon({ status }: { status: string }) {
  if (status === "COMPLETED") return <CheckCircle2 size={18} color="#16a34a" />;
  if (status === "IN_PROGRESS") return <Clock3 size={18} color="#2563eb" />;
  return <Hourglass size={18} color="#94a3b8" />;
}

export function FundOperationFlowPanel({
  title,
  subtitle,
  flow,
  canEdit,
  busy,
  onMarkCompleted,
}: {
  title?: string;
  subtitle?: string;
  flow: FundOperationFlow | null | undefined;
  canEdit?: boolean;
  busy?: boolean;
  onMarkCompleted?: (stepCode: string) => void | Promise<void>;
}) {
  if (!flow?.steps?.length) {
    return (
      <div className="notice" style={{ marginTop: 12 }}>
        Acompanhamento da operação disponível para cadastros com origem de capital <b>Institucional (fundo)</b>.
      </div>
    );
  }

  return (
    <section className="panel" style={{ marginTop: 14, padding: 16 }}>
      <span className="eyebrow dark">ESCRITÓRIO DO FUNDO</span>
      <h3 style={{ margin: "6px 0 4px", fontSize: 16 }}>{title || "Fluxo e status da operação"}</h3>
      {subtitle ? <p className="muted" style={{ fontSize: 12, margin: "0 0 12px" }}>{subtitle}</p> : null}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {flow.steps.map((step, index) => {
          const active = step.status === "IN_PROGRESS";
          return (
            <article
              key={step.code}
              style={{
                display: "grid",
                gridTemplateColumns: "36px 1fr auto",
                gap: 12,
                alignItems: "start",
                padding: "12px 14px",
                borderRadius: 10,
                border: active ? "2px solid #2563eb" : "1px solid var(--line)",
                background: active ? "#f0f7ff" : "#fff",
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: "#0f172a",
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 800,
                  fontSize: 13,
                }}
              >
                {index + 1}
              </div>
              <div>
                <strong style={{ fontSize: 13, letterSpacing: "0.02em" }}>{step.title.toUpperCase()}</strong>
                <p className="muted" style={{ fontSize: 11, margin: "6px 0 0", lineHeight: 1.45 }}>{step.description}</p>
                {canEdit && step.status === "IN_PROGRESS" && onMarkCompleted ? (
                  <button
                    type="button"
                    className="table-action"
                    style={{ marginTop: 8 }}
                    disabled={busy}
                    onClick={() => void onMarkCompleted(step.code)}
                  >
                    Marcar etapa como concluída
                  </button>
                ) : null}
              </div>
              <div style={{ textAlign: "right", minWidth: 120 }}>
                <StatusIcon status={step.status} />
                <small style={{ display: "block", marginTop: 4, fontSize: 10, fontWeight: 700, color: "var(--muted)" }}>
                  {statusLabel(step.status)}
                </small>
              </div>
            </article>
          );
        })}
      </div>
      <div style={{ marginTop: 14, display: "grid", gap: 8 }}>
        {flow.deadline_days ? (
          <div className="notice" style={{ fontSize: 11 }}>
            <b>Prazo total:</b> até {flow.deadline_days} dias para conclusão da operação (estimativa).
          </div>
        ) : null}
        {flow.disclaimer ? (
          <div className="notice" style={{ fontSize: 10, lineHeight: 1.45 }}>
            <b>Importante:</b> {flow.disclaimer}
          </div>
        ) : null}
      </div>
    </section>
  );
}
