/** VP de parcelas restantes — PMT × ((1 − (1+i)^−n) / i), i = 1% a.m. (doc253). */

export function parseMoneyInput(value: string): number {
  const raw = String(value || "").trim();
  if (!raw) return 0;
  if (raw.includes(",")) return Number(raw.replace(/\./g, "").replace(",", ".")) || 0;
  return Number(raw) || 0;
}

export function quitconVpFromInstallments(installmentValue: number, meses: number): number {
  if (!installmentValue || !Number.isFinite(meses) || meses < 1) return 0;
  const pmt = installmentValue;
  const i = 0.01;
  const n = meses;
  const factor = (1 - Math.pow(1 + i, -n)) / i;
  return Math.round(pmt * factor * 100) / 100;
}

export function quitconNominalBalance(installmentValue: number, meses: number): number {
  if (!installmentValue || !Number.isFinite(meses) || meses < 1) return 0;
  return installmentValue * meses;
}
