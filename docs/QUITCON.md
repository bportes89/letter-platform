# QuitCon — Manual do Produto (doc253)

Módulo: `LETTER_QUITCON_PRODUTO_2026_DOC253`

## Posicionamento

Solução LETTER para **quitação de bens adquiridos via consórcio** com arbitragem e assunção de dívida:

- **Cedente:** quita saldo com desconto (VP 1% a.m.) e libera alienação
- **Cessionário:** capital de giro mais barato assumindo parcelas restantes

## Taxas doc253

| Taxa | Base | Observação |
|------|------|------------|
| Deflacionamento | 1% a.m. | `VP = SB / (1 + 0.01 × n)` |
| Intermediação | 3% | Saldo devedor bruto |
| Serviço operacional | 2% (opcional) | Valor líquido cedente |
| Plataforma cessionário | 5% | Valor liberado (VP) |
| TAPAF | R$ 1.500 | Não reembolsável |
| Taxa sucesso Escrow | 10% | Valor liberado — **100% devolvida** se ADM reprovar |

## Elegibilidade

- Cota **contemplada** e **bem faturado**
- Parcelas **em dia**
- Administradora na **whitelist:** Âncora, HS, Embracon, Ademicon, Tradição, Recon, Groscon, Roma, Reserva

## Jornada (4 fases)

1. **Simulação e envio** — Super App, site ou SDC integrado
2. **Análise e entradas** — TAPAF + taxa sucesso 10% em Escrow
3. **Administradora** — SLA médio **45 dias**
4. **Desbloqueio** — pagamento cedente em Escrow (48h úteis pós-aprovação) + liberação final

## API

| Método | Rota |
|--------|------|
| POST | `/public/quitcon/simulate` — simulador site (sem login) |
| POST | `/finops/quitcon/simulate` — simulador autenticado doc253 |
| POST | `/finops/quitcon/operacoes` — abrir esteira |
| POST | `/finops/quitcon/success-fee-payment-webhook` — Escrow 10% |
| POST | `/finops/quitcon/cedente-payment-webhook` — pagamento cedente travado |
| POST | `/finops/quitcon/administrator-rejection` — reprova ADM + reembolso fee |

## Frontend

- **FinOps → QuitCon** — esteira operacional
- **`/simulador/quitcon`** — simulador público

## Relação SDC

SDC usa QuitCon apenas como **simulador de quitação** (doc256). A esteira QuitCon permanece **independente**.
