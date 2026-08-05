# NINA avançada e BI executivo

## Underwriting

Políticas são versionadas por produto e definem score mínimo, faixa de revisão manual, LTV máximo e comprometimento máximo de renda. Cada avaliação preserva a versão da política, entradas, score, faixa de risco, recomendação e fatores que explicam o resultado.

O motor atual é determinístico e auditável. Ele considera score externo informado, KYC, completude documental, LTV e comprometimento. A recomendação nunca substitui a decisão humana: aprovação ou rejeição exige step-up e registra autor e justificativa.

## Ranking de cotas

A NINA combina até três cotas disponíveis da mesma categoria e administradora. O ranking prioriza menor desvio em relação ao crédito alvo e menor complexidade da combinação, retornando score e explicação.

## BI executivo

O painel consolida funil comercial, valores faturados e recebidos, saldo aberto, encargos de inadimplência, avaliações de risco, decisões pendentes, funding e recuperação por leilão. O relatório executivo pode ser exportado em CSV UTF-8.

## Limites e produção

Scores externos e valores patrimoniais são entradas simuladas. Produção exige fontes autorizadas, governança de modelo, monitoramento de viés e drift, validação de políticas, revisão jurídica, segregação de funções e mecanismos formais de contestação e decisão humana.
