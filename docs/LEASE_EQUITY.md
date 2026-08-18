# Lease Equity — LETTER_FINOPS_LEASE_EQUITY_ENGINE_2026_V1

Motor: `EngineLeaseEquityLetter`

## Matriz LTV (simulador cliente)

| Tipologia | LTV captação | Remuneração proprietário |
|-----------|--------------|--------------------------|
| Urbano (exceto lote e galpão) | **40%** do AVM | **0,4% a.m.** sobre o valor captado (LTV) |
| Urbano (lote e galpão) | **25%** do AVM | **0,4% a.m.** sobre o valor captado |
| Rural | **20%** do AVM | **0,4% a.m.** sobre o valor captado |

Exemplo (imóvel R$ 600.000, prazo 36 meses):

| Tipologia | LTV | Saque mensal dono | Ganho total 36m |
|-----------|-----|-------------------|-----------------|
| Urbano | R$ 240.000 | R$ 960 | R$ 34.560 |
| Lote/galpão | R$ 150.000 | R$ 600 | R$ 21.600 |
| Rural | R$ 120.000 | R$ 480 | R$ 17.280 |

Pool investidor: **1,6% a.m.** sobre valor alavancado (LTV).

## Comissão parceiro (MMN)

- **Pool total:** 2% sobre o valor presente da antecipação (Price 2,5% a.m., 36 parcelas).
- Base MMN = `saque_total_antecipado_vp` — distribuída nos 5 níveis da rede conforme regra ativa do produto `LEASE_EQUITY`.

## Vistoria fotográfica nativa (SDC, Flash Capital e Lease Equity)

Componente anti-fraude compartilhado:
- Câmera nativa obrigatória — **galeria bloqueada**
- EXIF: timestamp Unix + coordenadas GPS
- Armazenamento: `s3://letter-vault-private/collateral-inspections/{produto}/{id}/`
- **Uso em inadimplência:** fotos vinculadas automaticamente ao caso NINA Asset e ao ativo de leilão

| Produto | Endpoint |
|---------|----------|
| SDC / Flash Capital | `POST /contracts/{id}/native-inspection` |
| Lease Equity | `POST /finops/lease-equity/inspection-photos` |

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
