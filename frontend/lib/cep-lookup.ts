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

/** População municipal (estimativa IBGE via Brasil API), quando disponível. */
export async function lookupMunicipalityPopulation(ibgeCode: string): Promise<number | null> {
  const code = ibgeCode.replace(/\D/g, "");
  if (code.length < 6) return null;
  try {
    const res = await fetch(`https://brasilapi.com.br/api/ibge/municipios/v1/${code}`);
    if (!res.ok) return null;
    const data = (await res.json()) as { populacao?: number };
    return typeof data.populacao === "number" && data.populacao > 0 ? data.populacao : null;
  } catch {
    return null;
  }
}
