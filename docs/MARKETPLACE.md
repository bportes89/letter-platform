# Marketplace — Cartas contempladas

Duas esteiras operacionais para parceiros e clientes.

## Fonte das regras

A análise do robô / Nina lê **sempre** as regras internas da administradora (`Administrator.rules_json` no painel).

- Sync Bacen (botão ou cron) **pode atualizar** esse JSON, mas **não roda** na Esteira 1/2 nem na varredura Nina.
- Campos relevantes: `max_asset_age_years`, `allowed_categories`, `accepts_dirty_name`, `accepts_zero_km`, `min_income_to_installment_ratio` (padrão **3**), `products_enabled`, `credit_utilization_rules`.

## Esteira 1 — Escolha do parceiro (`SELF_SELECT`)

1. Parceiro seleciona a carta/cota no inventário.
2. Nina executa **varredura cadastral** (se ainda não estiver `CLEARED`) — regras internas.
3. Nina valida **perfil do cliente** contra as regras da administradora da cota + lastro do bem.
4. **Renda comprovada ≥ N × parcela** da cota (N = `min_income_to_installment_ratio`, padrão 3).
5. Se o cliente **não tiver perfil** para aquela carta, Nina retorna **alternativas compatíveis** ranqueadas por desvio de crédito.
6. Parceiro trava a cota por **60 minutos** e segue em **Propostas** → contrato.

**API:** `POST /api/v1/marketplace/esteira-1/assess`

## Esteira 2 — Curadoria Nina (`NINA_CURATED`)

1. Parceiro ou cliente informa: **valor desejado**, **categoria**, **ano do bem**, perfil financeiro, SPC/Serasa e zero km.
2. Nina entrega **opções ranqueadas** do inventário filtradas pelas regras internas.
3. Parceiro trava a opção escolhida e segue em Propostas.

**API:** `POST /api/v1/marketplace/esteira-2/match`

## Regras de perfil (operacionais)

| Regra | Fonte |
|-------|--------|
| Idade máxima do bem (veículo) | `max_asset_age_years` da administradora |
| Categorias aceitas | `allowed_categories` |
| Nome sujo / SPC | só se `accepts_dirty_name` |
| Zero km | só se `accepts_zero_km` |
| Renda × parcela | `monthly_income >= ratio × installment_value` |
| Lastro | crédito alvo ≤ valor do bem |
| Teto de crédito / combo | `credit_utilization_rules` |

## Inventário

Cada cota deve ter **valor da parcela** (`installment_value`) para o filtro de renda funcionar.

## Fluxo completo

```
Cadastro (admin/Inventário + regras Administradoras) → Varredura Nina → Marketplace (Esteira 1 ou 2) → Trava 60 min → Proposta → Contrato (SOLD)
```

## UI

- **COMERCIAL (parceiros)** no menu lateral:
  - **Cartas contempladas** → Marketplace (esteiras) | Inventário (admin, interno)
  - **Propostas e simulações** → cadastro comercial unificado (Marketplace, SDC, Flash)
- **SDC — estrutura interna** (menu PRODUTOS, só admin/staff/franqueadora) → pré-análise fiduciária
