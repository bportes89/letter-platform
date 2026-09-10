# Marketplace — Cartas contempladas

Duas esteiras operacionais para parceiros e clientes.

## Fonte das regras

A análise lê `Administrator.rules_json` (painel), **incluindo** `approval_rules` vindas do sync Bacen (renda/SCR).

- Sync Bacen (botão ou cron) atualiza o JSON; o matching **consome** `approval_rules.min_income_margin` e `scr_clear_required`.
- LTV Bacen (`max_ltv_percent`) permanece para produtos de crédito fiduciário — no Marketplace o lastro é **crédito ≤ valor do bem**.
- Campos relevantes: `max_asset_age_years`, `allowed_categories`, `accepts_dirty_name`, `accepts_zero_km`, `min_income_to_installment_ratio` (padrão **3**), `products_enabled`, `credit_utilization_rules`, `approval_rules`.

## Esteira 1 — Escolha do parceiro (`SELF_SELECT`)

1. Parceiro seleciona a carta/cota no inventário.
2. Nina executa **varredura cadastral** (se ainda não estiver `CLEARED`).
3. Nina valida **perfil do cliente** contra regras internas + Bacen/approval_rules + lastro.
4. **Renda comprovada ≥ N × parcela** (N interno ou margem Bacen).
5. Se o cliente **não tiver perfil**, Nina retorna **alternativas** ranqueadas.
6. Parceiro trava a cota por **60 minutos** e segue em **Propostas** → contrato.

**API:** `POST /api/v1/marketplace/esteira-1/assess`

## Esteira 2 — Robô Nina (`NINA_CURATED`) — regras Paulo Stutz

1. Informe **crédito alvo**, **entrada alvo** (opcional), categoria, ano do bem e perfil.
2. **Régua de corte 5%** em crédito e em entrada.
3. Entrega até **2 opções na lane crédito** + **2 na lane entrada** (dedupe).
4. Combinação de cotas (junção) só na mesma administradora (até `max_combined_quotas`).
5. **Rollover 7 dias:** se `installment_due_date` ≤ 7 dias, reduz 1 em `remaining_installments` e soma a parcela na entrada.
6. **Markup na entrada** (% do crédito), conforme `supplier_source`:
   - Fraga / Bittelo / Lance → **+3%**
   - Uni Contemplados / Contemplado SP / Lume → **+10%**
7. Parceiro trava a opção e segue em Propostas.

**API:** `POST /api/v1/marketplace/esteira-2/match`  
Payload extra: `target_entrada` (opcional).  
Resposta: `matches`, `credit_matches`, `entrada_matches`, `band_percent`.

## Regras de perfil (operacionais)

| Regra | Fonte |
|-------|--------|
| Idade máxima do bem (veículo) | `max_asset_age_years` |
| Categorias aceitas | `allowed_categories` |
| Nome sujo / SPC | `accepts_dirty_name` + `approval_rules.scr_clear_required` |
| Zero km | `accepts_zero_km` |
| Renda × parcela | `min_income_to_installment_ratio` / `approval_rules.min_income_margin` |
| Lastro | crédito alvo ≤ valor do bem |
| Teto de crédito / combo | `credit_utilization_rules` |
| Banda 5% / lanes / rollover / markup | motor Esteira 2 |

## Inventário

Cada cota deve ter:

- `installment_value` — filtro de renda
- `installment_due_date` — rollover 7 dias
- `remaining_installments` — prazo ajustado no rollover
- `supplier_source` — chave do fornecedor (`source_key` em **Fornecedores**)
- `premium_value` — entrada/ágio base

## Fornecedores (admin)

CRUD em `GET/POST/PATCH /api/v1/marketplace/suppliers` (+ `POST .../ensure-defaults`).

- `source_key` único por org (FRAGA, BITTELO, LANCE, UNI_CONTEMPLADOS, CONTEMPLADO_SP, LUME…)
- `markup_percent` — % do crédito somado na entrada (prevalece sobre o mapa hardcoded)
- `quem_paga_comissao` — `0` fornecedor / `1` cliente embute `platform_fee_percent` na entrada

Menu: **Cartas contempladas → Fornecedores**.

## Fluxo completo

```
Cadastro (Fornecedores + Inventário) → Sync Bacen (opcional) → Varredura Nina → Marketplace / Venda Direta Robô → Trava 60 min → Proposta → Contrato (SOLD)
```

## UI

- **COMERCIAL:** Cartas contempladas → Marketplace (esteiras) | **Venda Direta Robô** (admin) | Inventário (admin)
- **Propostas e simulações** → cadastro comercial unificado

## Venda Direta Robô (admin)

Wizard de 2 passos sobre o mesmo motor da Esteira 2:

1. `POST /api/v1/marketplace/venda-direta-robo/search` — dados do cliente + filtros → cria Lead (`source=VENDA_DIRETA_ROBO`) e devolve `credit_matches` / `entrada_matches`.
2. `POST /api/v1/marketplace/venda-direta-robo/confirm` — escolhe `quota_ids` → proposta `MARKETPLACE` + trava 60 min → finalize em Propostas.

Sem match no passo 1, a API responde **404** (não deixa pré-cadastro órfão).
