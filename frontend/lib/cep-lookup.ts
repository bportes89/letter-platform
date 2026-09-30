export type CepAddress = {
  zipcode: string;
  street: string;
  neighborhood: string;
  city: string;
  uf: string;
  ibge?: string;
};

export async function lookupCep(cep: string): Promise<CepAddress | null> {
  const digits = cep.replace(/\D/g, "");
  if (digits.length !== 8) return null;
  const res = await fetch(`https://viacep.com.br/ws/${digits}/json/`);
  if (!res.ok) return null;
  const data = (await res.json()) as {
    erro?: boolean;
    logradouro?: string;
    bairro?: string;
    localidade?: string;
    uf?: string;
    ibge?: string;
  };
  if (data.erro) return null;
  return {
    zipcode: digits,
    street: data.logradouro || "",
    neighborhood: data.bairro || "",
    city: data.localidade || "",
    uf: (data.uf || "").toUpperCase(),
    ibge: data.ibge || undefined,
  };
}

/** População municipal estimada (SIDRA / IBGE), quando disponível. */
export async function lookupMunicipalityPopulation(ibgeCode: string): Promise<number | null> {
  const code = ibgeCode.replace(/\D/g, "");
  if (code.length < 6) return null;
  try {
    const res = await fetch(
      `https://apisidra.ibge.gov.br/values/t/6579/n6/${code}/v/9324/p/last%201`,
    );
    if (!res.ok) return null;
    const rows = (await res.json()) as Array<{ V?: string }>;
    if (!Array.isArray(rows) || rows.length < 2) return null;
    const raw = String(rows[1]?.V ?? "").replace(/\D/g, "");
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? n : null;
  } catch {
    return null;
  }
}
