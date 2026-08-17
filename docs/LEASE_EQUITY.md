# Lease Equity — LETTER_FINOPS_LEASE_EQUITY_ENGINE_2026_V1

Motor: `EngineLeaseEquityLetter`

## Matriz LTV assimétrica

| Tipologia | LTV máx. | Base recompensa dono | Aluguel dono (0,4% a.m.) |
|-----------|----------|----------------------|--------------------------|
| Urbano residencial/comercial | 60% | 40% AVM | base × 0,4% |
| Lote / Galpão | 40% | 25% AVM | base × 0,4% |
| Rural | 30% | 20% AVM | base × 0,4% |

Pool investidor: **1,6% a.m.** sobre valor alavancado.

## TAPAF Lease Equity

- Valor fixo: **R$ 750,00** (não reembolsável)
- Status inicial: `AGUARDANDO_TAPAF`
- Webhook BaaS → `TAPAF_LIQUIDADA` + dossiê S3

## Estados da esteira

```
AGUARDANDO_TAPAF → TAPAF_LIQUIDADA → EM_AUDITORIA_RISCO → AGUARDANDO_ASSINATURA
→ PRONTO_PARA_CARTORIO → EM_ANALISE_NO_RGI → GRAVAME_CONCLUIDO → ATIVO_OK_EM_PRODUCAO
→ LIBERADO_PARA_ANTECIPACAO
```

## Tokenização RWA

- Cota nominal: **R$ 100,00**
- Padrão: ERC-3643
- Endpoint: `POST /finops/lease-equity/tokenization-processor`

## Antecipação

- Taxa desconto Price: **2,5% a.m.**
- Carência mínima: **6 meses** de vigência/adimplência
- Gatilho OK: captação ≥ **30%** do teto LTV ou ativação manual admin
