export type DeskPipelineStatusOption = { value: string; label: string };

export type DeskPipelineBucket = { count: number; total: number };

export function deskPipelineAmount(item: Record<string, unknown>, amountKeys: string[]): number {
  for (const key of amountKeys) {
    const raw = item[key];
    if (raw === null || raw === undefined || raw === "") continue;
    const n = Number(raw);
    if (!Number.isNaN(n)) return n;
  }
  return 0;
}

export function computeDeskPipelineSummary(
  items: { status: string; amount: number }[],
  statusOptions: readonly DeskPipelineStatusOption[],
): { buckets: Record<string, DeskPipelineBucket>; totalCount: number; totalAmount: number } {
  const buckets: Record<string, DeskPipelineBucket> = {};
  for (const s of statusOptions) {
    buckets[s.value] = { count: 0, total: 0 };
  }
  let totalCount = 0;
  let totalAmount = 0;
  for (const item of items) {
    totalCount += 1;
    totalAmount += item.amount;
    const b = buckets[item.status];
    if (b) {
      b.count += 1;
      b.total += item.amount;
    }
  }
  return { buckets, totalCount, totalAmount };
}
