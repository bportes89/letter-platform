# Cobrança, inadimplência e conciliação

## Escopo da v0.7.0

O centro de cobrança transforma contratos assinados em agenda financeira operacional. A implementação cobre geração de parcelas, baixa idempotente de pagamentos, importação de conciliação, tratamento de divergências e acompanhamento de inadimplência.

## Geração das faturas

- Marketplace: fatura única vinculada ao contrato.
- SDC: cobrança dos marcos `START_1` e `START_2`, seguida do vencimento `BULLET`, conforme a memória de cálculo contratada.
- Flash Credit de 36 meses: parcelas mensais conforme a Tabela Price ou plano institucional persistido.
- Flash Credit de 60 meses: parcelas mensais e parcela `BALLOON` no mês 36, respeitando a memória de cálculo.

A geração é idempotente por contrato: uma agenda já criada não é duplicada.

## Pagamentos e webhooks

Cada evento externo possui identificador único do provedor. Reenvios do mesmo evento retornam o resultado existente e não duplicam a baixa. Quando o valor recebido coincide com o saldo, a fatura é atualizada; quando diverge, o evento é preservado e uma ocorrência entra na fila de conciliação.

O endpoint atual é um adaptador mock. A integração financeira real depende de assinatura do webhook, segredo por ambiente, política de retry e homologação do provedor.

## Arquivo de conciliação

O importador aceita CSV UTF-8 com o cabeçalho:

```csv
invoice_number,amount,payment_date,external_id
SDC-000001-START_1,1500.00,2026-08-02,provider-event-001
```

O hash do arquivo impede importação duplicada. Cada linha é classificada como conciliada ou divergente. Divergências incluem fatura ausente e diferença de valor. A resolução manual exige step-up e registra usuário, decisão e observação na trilha operacional.

## Inadimplência e régua

Na simulação atual, faturas vencidas recebem multa de 2% e juros de mora de 1% ao mês calculados proporcionalmente aos dias em atraso. Contratos Flash Credit com atraso superior a 60 dias ficam elegíveis à caducidade e geram ações de cobrança conforme os marcos da régua.

Esses parâmetros são premissas técnicas configuradas para a sandbox. Caducidade, cobrança jurídica, comunicação ao cliente e execução de garantias nunca são automáticas em produção: dependem do contrato homologado, revisão jurídica, consentimentos e aprovação operacional.

## Gate de produção

Antes de ativar dinheiro real, são obrigatórios provedor contratado, autenticação forte dos webhooks, conciliação homologada, segregação de funções, templates jurídicos aprovados, observabilidade, testes de recuperação, pentest e plano de incidentes.
