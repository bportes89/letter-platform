# NINA Real Assets — imóveis estruturados v0.21.0

## Roteamento

O onboarding classifica cada caso em:

- `CLEAN_GUARANTEE`: garantia sem dívida e sem construção pendente;
- `INTERVENING_PAYOFF`: existe dívida/gravame e exige interveniente quitante;
- `UNREGISTERED_CONSTRUCTION`: construção ainda não integrada à matrícula.

## Memória de cálculo

Todos os valores usam `Decimal` com duas casas:

- payout bruto máximo = AVM futuro × 40%;
- Fase 1 para construção não averbada = valor do lote × 40%;
- Fase 2 = payout bruto − Fase 1;
- caso a dívida estimada seja igual ou superior ao payout bruto, a operação é rejeitada.

O cálculo produz snapshot SHA-256 e trilha de eventos idempotente.

## Interveniente quitante

Quando há dívida, o documento de quitação entra em quarentena e exige revisão com step-up. A aprovação apenas prepara uma liquidação sandbox; não dispara Pix real.

## Payout em fases e averbação

Após o gate da Fase 1, a plataforma abre uma janela de 90 dias e agenda avisos no início, D-30, D-7 e D-1. O cliente envia a matrícula atualizada; a Fase 2 só chega a `PHASE2_SANDBOX_READY` após revisão humana.

O vencimento muda o caso para `EXPIRED_MANUAL_REVIEW`. Não ocorre perda automática do saldo, amortização, confisco ou payout. A Fase 2 permanece bloqueada sob `legal_hold` até decisão jurídica/operacional registrada.

## Requerimento cartorial

O endpoint PDF gera uma minuta técnica com referência e hash do caso. O documento declara explicitamente que depende de conferência de propriedade, poderes de representação, anexos registrais, assinatura ICP-Brasil e protocolo pelo cartório competente.

## Limites de produção

Eventos de pagamento, quitação, registro e comunicação continuam em sandbox enquanto não existirem BaaS, cartório/registrador, OCR, assinatura, storage e mensageria oficialmente homologados.

