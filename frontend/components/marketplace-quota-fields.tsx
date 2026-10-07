const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export type MarketplaceQuotaFieldsData = {
  administrator_name?: string | null;
  credit_value: string;
  premium_value?: string;
  entrada_final?: string | null;
  installment_value?: string | null;
  remaining_installments?: number | null;
  installment_due_date?: string | null;
};

export function formatMarketplaceDueDate(value: string | null | undefined): string {
  if (!value) return "—";
  const iso = value.length >= 10 ? value.slice(0, 10) : value;
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return value;
  return new Date(y, m - 1, d).toLocaleDateString("pt-BR");
}

export function MarketplaceQuotaFields({
  quota,
  administratorFallback,
  showAdministrator = false,
}: {
  quota: MarketplaceQuotaFieldsData;
  administratorFallback?: string | null;
  /** Parceiro comercial não vê administradora/fornecedor na esteira. */
  showAdministrator?: boolean;
}) {
  const entrada = quota.entrada_final ?? quota.premium_value ?? "0";
  const prazo =
    quota.remaining_installments != null && quota.remaining_installments > 0
      ? `${quota.remaining_installments} parcelas`
      : "—";

  const adminLabel = quota.administrator_name ?? administratorFallback;

  return (
    <dl className="marketplace-quota-fields">
      {showAdministrator ? (
        <>
          <dt>Administradora:</dt>
          <dd>{adminLabel ?? "—"}</dd>
        </>
      ) : null}
      <dt>Crédito:</dt>
      <dd>{brl.format(Number(quota.credit_value))}</dd>
      <dt>Entrada:</dt>
      <dd>{brl.format(Number(entrada))}</dd>
      <dt>Parcela:</dt>
      <dd>{brl.format(Number(quota.installment_value || 0))}</dd>
      <dt>Prazo:</dt>
      <dd>{prazo}</dd>
      <dt>Vencimento:</dt>
      <dd>{formatMarketplaceDueDate(quota.installment_due_date)}</dd>
    </dl>
  );
}
