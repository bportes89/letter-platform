const ASAAS_SEAL_URLS = {
  positivo:
    "https://baas.asaas.com/selos/Servicos_financeiros_Asaas-Reduzida-Positivo.svg?id=503ea9aa-7d80-4e1a-948a-4afdd8b64f52",
  negativoPreto:
    "https://baas.asaas.com/selos/Servicos_financeiros_Asaas-Reduzida-Negativo-Preto.svg?id=503ea9aa-7d80-4e1a-948a-4afdd8b64f52",
  negativoBranco:
    "https://baas.asaas.com/selos/Servicos_financeiros_Asaas-Reduzida-Negativo-Branco.svg?id=503ea9aa-7d80-4e1a-948a-4afdd8b64f52",
} as const;

type SealVariant = keyof typeof ASAAS_SEAL_URLS;

type Props = {
  variant?: SealVariant;
};

export function AsaasBaasSeal({ variant = "negativoPreto" }: Props) {
  return (
    <a
      href="https://www.asaas.com"
      target="_blank"
      rel="noopener noreferrer"
      className="asaas-baas-seal"
      aria-label="Serviços financeiros prestados pelo Asaas — abrir site do Asaas"
    >
      <img
        src={ASAAS_SEAL_URLS[variant]}
        alt="Serviços financeiros ASAAS"
        width={160}
        height={48}
        loading="lazy"
      />
    </a>
  );
}
