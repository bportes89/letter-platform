# Roteamento fiduciário NINA — v0.24.0

O motor recebe tipo de garantia, município, população, renda per capita, prenotações, flags de risco e referência de evidência da TAPAF. A política ativa é versionada e aprovada por step-up.

Pautas com negativação ou veto somente podem ser recuperadas pelo Flash Credit quando a garantia é imóvel. Veículos e pesados são bloqueados nessa rota. Bloqueios judiciais, penhoras, arrestos, sequestros e embargos fiscais bloqueiam a avaliação; hipoteca bancária, Home Equity e financiamento imobiliário ativo podem prosseguir para análise.

Se população e renda atingem simultaneamente os limites da política, a rota de capital é `FUNDS`; caso contrário, `POOL`. A referência TAPAF não substitui avaliação física, engenharia, laudo, KYB/KYC, análise jurídica ou registro.

A aprovação do comitê emite um Valid-Stamp HMAC-SHA256 de evidência. O payload declara `payout_authorized: false`. O selo não possui fé pública, não é ICP-Brasil e não libera dinheiro por si só.

## Política de dados

São permitidas integrações autorizadas com IBGE, dados agregados do Bacen, provedor ONR, bureau de crédito e documentos fornecidos pelo cliente. Consulta judicial exige fundamento legal, autorização de acesso e avaliação de impacto. Scraping massivo de PJe, extração de contatos e enriquecimento de dados pessoais sem base legal ficam bloqueados.
