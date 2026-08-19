# QuitCon — LETTER_FINOPS_QUITCON_ENGINE_2026_V1

Motor: `EngineQuitConLetter`

Produto de quitação de cota de consórcio com colateral imobiliário/automotivo, tokenização RWA e regras de multa doc252.

## TAPAF

- Valor fixo: **R$ 1.500,00** (não reembolsável)
- Status inicial: `AGUARDANDO_TAPAF`

## Matriz LTV assimétrica

| Tipologia | LTV máx. captação | Base recompensa dono | Aluguel dono (0,4% a.m.) |
|-----------|-------------------|----------------------|--------------------------|
| Urbano residencial/comercial | 60% | 40% AVM | base × 0,4% |
| Lote / Galpão | 40% | 25% AVM | base × 0,4% |
| Rural | 30% | 20% AVM | base × 0,4% |

Pool investidor: **1,6% a.m.** sobre valor alavancado.

## SLA

- Prazo médio estimado de conclusão: **45 dias** (`sla_estimated_completion_at`)

## Multas e cancelamentos (doc252)

### Inadimplência pós-aprovação administradora (cessionário)

- Após aprovação da administradora, responsabilidade das parcelas é do **cessionário**
- Atraso **> 15 dias** → cancelamento + **taxa de sucesso 10% retida integralmente** em Escrow

### Desistência do cedente

- Após aprovação final, se o cedente desistir ou não depositar quitação em **48h úteis**
- **Multa 10%** sobre saldo devedor bruto + reembolso ao cessionário (vistoria/parcelas antecipadas)

## Estados da esteira

```
AGUARDANDO_TAPAF → TAPAF_LIQUIDADA → EM_AUDITORIA_RISCO → AGUARDANDO_ASSINATURA
→ PRONTO_PARA_CARTORIO → EM_ANALISE_NO_RGI → GRAVAME_CONCLUIDO → ATIVO_OK_EM_PRODUCAO
→ LIBERADO_PARA_ANTECIPACAO
```

Estados terminais de penalidade: `CANCELADO_INADIMPLENCIA_CESSIONARIO`, `CANCELADO_DESISTENCIA_CEDENTE`

## API principal

| Endpoint | Descrição |
|----------|-----------|
| `POST /finops/quitcon/operacoes` | Abrir operação |
| `POST /finops/quitcon/tapaf-payment-webhook` | Liquidar TAPAF R$ 1.500 |
| `POST /finops/quitcon/inspection-photos` | Vistoria nativa |
| `POST /finops/quitcon/administrator-approval` | Marcar aprovação administradora |
| `POST /finops/quitcon/cancel-inadimplencia` | Multa cessionário |
| `POST /finops/quitcon/cancel-desistencia` | Multa cedente |
| `POST /finops/quitcon/tokenization-processor` | Tokenização RWA ERC-3643 |

## Antecipação

- Taxa desconto Price: **2,5% a.m.**
- Carência mínima: **6 meses**
- Gatilho OK: captação ≥ **30%** do teto LTV ou ativação manual
