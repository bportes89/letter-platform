import Link from "next/link";

export type DeskSourceFields = {
  source_channel: string | null;
  source_channel_label: string | null;
  lead_id: string | null;
};

function channelPillClass(channel: string | null): string {
  if (channel === "SITE_CHAT") return "cleared";
  if (channel?.endsWith("_DESK")) return "pending";
  return "new";
}

export function DeskSourceBadge({
  channel,
  label,
}: {
  channel: string | null;
  label: string | null;
}) {
  if (!label) return null;
  return (
    <span className={`pill pill-${channelPillClass(channel)}`} style={{ fontSize: 10 }}>
      {label}
    </span>
  );
}

export function DeskLeadLink({ leadId }: { leadId: string | null }) {
  if (!leadId) return null;
  return (
    <Link
      href={`/modules/crm?lead_id=${encodeURIComponent(leadId)}`}
      className="table-action"
      style={{ fontSize: 11, padding: 0 }}
    >
      Lead {leadId.slice(0, 8)}…
    </Link>
  );
}

export function DeskSourceMetaRow({
  channel,
  label,
  leadId,
}: {
  channel: string | null;
  label: string | null;
  leadId: string | null;
}) {
  if (!label && !leadId) return null;
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginTop: 4 }}>
      <DeskSourceBadge channel={channel} label={label} />
      <DeskLeadLink leadId={leadId} />
    </div>
  );
}
