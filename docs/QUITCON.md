# QuitCon — Manual do Produto (doc253)

Módulo: `LETTER_QUITCON_PRODUTO_2026_DOC253`

## Posicionamento

Solução LETTER para **quitação de bens adquiridos via consórcio** com arbitragem e assunção de dívida:

- **Cedente:** quita saldo com desconto (VP 1% a.m.) e libera alienação
- **Cessionário:** capital de giro mais barato assumindo parcelas restantes

## Custos de entrada (início da operação)

| Item | Valor | Observação |
|------|-------|------------|
| **TAPAF** | R$ 1.500 | Obrigatório · não reembolsável |
| **Taxa serviço LETTER** | 2% × VP | **Opcional** — só se a LETTER conduzir junto à administradora |
| **Taxa sucesso Escrow** | 10% × VP | Obrigatório · 100% reembolsável se ADM reprovar |

A API e o simulador expõem o bloco `custos_entrada` com TAPAF, taxa 2% (quando contratada) e Escrow 10%.

## Taxas doc253 (regra comercial corrigida)

| Taxa | Base | Momento | Observação |
|------|------|---------|------------|
| Deflacionamento | 1% a.m. | Simulação | `VP = SB / (1 + 0.01 × n)` |
| Intermediação | 3% | Quitação | Sobre o **VP** — pago **junto** na liquidação: **VP + 3%** |
| Serviço operacional | 2% (opcional) | Abertura | Sobre o **VP** — se o cliente **não** conduzir junto à administradora |
| Plataforma cessionário | 5% | Liberação | Descontado sobre o **VP** na liberação ao cessionário: **VP − 5%** |
| TAPAF | R$ 1.500 | Abertura | Não reembolsável |
| Taxa sucesso Escrow | 10% | Abertura | Sobre o VP — **100% devolvida** se ADM reprovar |

### Exemplo canônico (VP = R$ 400.000,00)

| Parte | Cálculo | Valor |
|-------|---------|-------|
| Cedente paga quitação | 400.000 + 3% | **R$ 412.000,00** |
| Taxa serviço LETTER (se contratada) | 2% × 400.000 | R$ 8.000,00 (na abertura) |
| Cessionário recebe capital de giro | 400.000 − 5% | **R$ 380.000,00** |

## Elegibilidade

- Cota **contemplada** e **bem faturado**
- Parcelas **em dia**
- Administradora na **whitelist:** Âncora, HS, Embracon, Ademicon, Tradição, Recon, Groscon, Roma, Reserva

## Jornada (4 fases)

1. **Simulação e envio** — Super App, site ou SDC integrado
2. **Análise e entradas** — TAPAF + taxa serviço 2% (se contratada) + taxa sucesso 10% em Escrow
3. **Administradora** — SLA médio **45 dias**
4. **Desbloqueio** — cedente paga **VP + 3%** em Escrow (48h úteis pós-aprovação) + liberação final **VP − 5%** ao cessionário

## API

| Método | Rota |
|--------|------|
| POST | `/public/quitcon/simulate` — simulador site (sem login) |
| POST | `/finops/quitcon/simulate` — simulador autenticado doc253 |
| POST | `/finops/quitcon/operacoes` — abrir esteira |
| POST | `/finops/quitcon/operational-service-payment-webhook` — taxa serviço 2% |
| POST | `/finops/quitcon/success-fee-payment-webhook` — Escrow 10% |
| POST | `/finops/quitcon/cedente-payment-webhook` — pagamento cedente (VP + 3%) |
| POST | `/finops/quitcon/administrator-rejection` — reprova ADM + reembolso fee |

## Frontend

- **FinOps → QuitCon** — esteira operacional
- **`/simulador/quitcon`** — simulador público

## Relação SDC

SDC usa QuitCon apenas como **simulador de quitação** (doc256). A esteira QuitCon permanece **independente**.
