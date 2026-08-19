# QuitCon — LETTER_FINOPS_QUITCON_ENGINE_2026_V1

Motor: `EngineQuitConLetter`

Produto de **quitação de cota de consórcio** com multas doc252, SLA e tokenização RWA.

> **Importante:** QuitCon **não possui** LTV assimétrico por tipologia nem remuneração de **0,4% a.m.** — ambos são **exclusivos do Lease Equity**.

## Base financeira

- **Saldo devedor bruto da cota** = meta de captação / lastro de tokenização
- Avaliação do bem (quando informada) = referência opcional, **não** aplica matriz LTV
- Pool investidor: **1,6% a.m.** sobre o saldo devedor (meta de captação)

## TAPAF

- Valor fixo: **R$ 1.500,00** (não reembolsável)

## SLA

- Prazo médio estimado de conclusão: **45 dias**

## Multas (doc252)

| Evento | Regra |
|--------|-------|
| Inadimplência cessionário (>15d pós-aprovação adm.) | Taxa sucesso **10%** retida integralmente em Escrow |
| Desistência cedente (pós-aprovação) | Multa **10%** sobre saldo devedor + reembolso cessionário |

## Estados da esteira

```
AGUARDANDO_TAPAF → … → GRAVAME_CONCLUIDO → ATIVO_OK_EM_PRODUCAO
```

Gatilho OK: captação ≥ **30%** do saldo devedor ou ativação manual.

## API

- `POST /finops/quitcon/simulate` — simulação por saldo devedor
- `POST /finops/quitcon/operacoes` — abrir operação
- Demais endpoints: TAPAF, vistoria, multas, tokenização RWA
