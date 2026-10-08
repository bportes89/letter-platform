/** Opções de ano máximo de fabricação (espelho do admin legado / módulo Administradoras). */
export const MAX_VEHICLE_AGE_OPTIONS = [
  { value: "", label: "(sem restrição)" },
  { value: "0", label: "Somente Zero KM" },
  ...Array.from({ length: 30 }, (_, i) => ({ value: String(i + 1), label: `Até ${i + 1} ano(s)` })),
];

export function maxVehicleAgeLabel(years: number | null | undefined): string {
  if (years === undefined || years === null) return "(sem restrição)";
  if (years === 0) return "Somente Zero KM";
  return `Até ${years} ano(s)`;
}
