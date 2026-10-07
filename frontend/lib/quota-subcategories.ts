export type QuotaCategoryOption = {
  id: string;
  name: string;
  legacy_type: number;
  parent_id: string | null;
  title_sub: string | null;
  asset_class?: string | null;
  active?: boolean;
};

function inferAssetClass(
  row: QuotaCategoryOption,
  parents: Map<string, QuotaCategoryOption>,
): "REAL_ESTATE" | "VEHICLE" | null {
  if (row.asset_class === "REAL_ESTATE" || row.asset_class === "VEHICLE") {
    return row.asset_class;
  }
  const parent = row.parent_id ? parents.get(row.parent_id) : undefined;
  if (parent?.asset_class === "REAL_ESTATE" || parent?.asset_class === "VEHICLE") {
    return parent.asset_class;
  }
  const title = (parent?.title_sub || parent?.name || row.title_sub || row.name || "").toLowerCase();
  if (title.includes("imóvel") || title.includes("imovel")) return "REAL_ESTATE";
  if (title.includes("veículo") || title.includes("veiculo")) return "VEHICLE";
  return null;
}

/** Subcategorias (legacy_type=1) filtradas por tipo de bem (imóvel / veículo). */
export function subcategoriesForAssetClass(
  categories: QuotaCategoryOption[],
  category: "REAL_ESTATE" | "VEHICLE",
): QuotaCategoryOption[] {
  const parents = new Map(
    categories.filter((c) => c.legacy_type === 0).map((p) => [p.id, p]),
  );
  return categories
    .filter((c) => c.legacy_type === 1 && (c.active ?? true))
    .filter((c) => {
      const asset = inferAssetClass(c, parents);
      return !asset || asset === category;
    })
    .sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
}
