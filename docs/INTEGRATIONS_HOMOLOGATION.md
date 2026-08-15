# Integrações homologáveis

## Objetivo

A v0.14.0 introduz uma camada única para homologar fornecedores externos sem acoplar as regras da LETTER a SDKs proprietários. As configurações são isoladas por organização e ambiente.

## Recursos entregues

- Cadastro de provedores por categoria: BaaS, KYC, assinatura, comunicações, fiscal ou customizado.
- Separação explícita entre SANDBOX e PRODUCTION.
- Credenciais e secrets armazenados de forma cifrada e nunca retornados pela API.
- Health check com latência, estado de saúde e data da última verificação.
- Circuit breaker persistente nos estados CLOSED, OPEN e HALF_OPEN.
- Webhooks assinados com HMAC-SHA256 sobre `timestamp.payload_canônico`.
- Tolerância de cinco minutos na verificação, mitigando replay de mensagens antigas.
- Idempotência por endpoint e `event_id`.
- Retentativas exponenciais, limite configurável e dead letter.
- Painel para configurar sandboxes, executar probes, simular falhas e acompanhar entregas.

## Cabeçalho lógico de assinatura

O valor gerado usa o formato:

```text
t=<unix_timestamp>,v1=<hmac_sha256>
```

O consumidor deve serializar o payload com chaves ordenadas e sem espaços, concatenar o timestamp, um ponto e o JSON canônico, e comparar o digest em tempo constante.

## Circuit breaker

Após três falhas consecutivas, por padrão, o circuito passa para OPEN e bloqueia novas chamadas. Depois do cooldown configurado, a próxima tentativa entra em HALF_OPEN. Uma resposta bem-sucedida fecha o circuito; uma nova falha volta a abri-lo.

Variáveis disponíveis:

- `LETTER_INTEGRATION_CIRCUIT_FAILURE_THRESHOLD`
- `LETTER_INTEGRATION_CIRCUIT_COOLDOWN_SECONDS`

## Gate para produção

O suporte a PRODUCTION não significa que um fornecedor esteja juridicamente ou tecnicamente homologado. Antes de habilitar transações financeiras são obrigatórios: contrato do fornecedor, credenciais produtivas, allowlist de destinos, testes de conciliação, evidências de segurança, plano de incidentes e aprovação jurídica.
