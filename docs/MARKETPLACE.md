# Marketplace — Cartas contempladas

Duas esteiras operacionais para parceiros e clientes.

## Esteira 1 — Escolha do parceiro (`SELF_SELECT`)

1. Parceiro seleciona a carta/cota no inventário.
2. Nina executa **varredura cadastral** (se ainda não estiver `CLEARED`).
3. Nina valida **perfil do cliente** (renda, comprometimento, valor e ano do bem).
4. Se o cliente **não tiver perfil** para aquela carta, Nina retorna **alternativas compatíveis** ranqueadas por desvio de crédito.
5. Parceiro trava a cota por **60 minutos** e segue em **Propostas** → contrato.

**API:** `POST /api/v1/marketplace/esteira-1/assess`

## Esteira 2 — Curadoria Nina (`NINA_CURATED`)

1. Parceiro ou cliente informa apenas: **valor desejado**, **categoria** (imóvel/veículo), **ano do bem** e perfil financeiro.
2. Nina entrega **opções ranqueadas** do inventário disponível.
3. Parceiro trava a opção escolhida e segue em Propostas.

**API:** `POST /api/v1/marketplace/esteira-2/match`

## Regras de perfil (MVP)

| Regra | Limite |
|-------|--------|
| Comprometimento de renda | ≤ 30% da renda mensal |
| Lastro | Crédito alvo ≤ valor do bem |
| Veículo — idade do bem | ≤ 10 anos (ano fabricação) |

## Fluxo completo

```
Cadastro (admin/Inventário) → Varredura Nina → Marketplace (Esteira 1 ou 2) → Trava 60 min → Proposta → Contrato (SOLD)
```

## UI

- **COMERCIAL (parceiros)** no menu lateral:
  - **Cartas contempladas** → Marketplace (esteiras) | Inventário (admin, interno)
  - **Propostas e simulações** → cadastro comercial unificado (Marketplace, SDC, Flash)
- **SDC — estrutura interna** (menu PRODUTOS, só admin/staff/franqueadora) → pré-análise fiduciária
