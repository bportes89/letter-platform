# SDC + QuitCon — Integração UI (doc256)

Módulo: `LETTER_SDC_QUITCON_UI_INTEGRATION_2026`

## Escopo

Projeção deflacionada **1% a.m.** sobre o saldo devedor simulado do SDC, exibida:

1. **Pós-simulação** — tabela comparativa 6/12/18/24/36/48 meses em `ProposalsModule`
2. **Contrato SDC ativo** — card com saldo bruto, VP à vista e modal explicativo em `ContractsModule`

## Fórmula

```
VP = SB / (1 + 0.01 * n)
```

- `SB` = `maturity_total` da memória SDC (principal + juros bullet)
- `n` = meses de projeção (6–48 na tabela; prazo do contrato no card)

## API

| Método | Rota | Uso |
|--------|------|-----|
| POST | `/finops/sdc/quitcon-projection` | Projeção standalone |
| POST | `/finops/sdc/start-quitcon` | Simulação SDC → abre operação QuitCon (`AGUARDANDO_TAPAF`) |
| GET | `/contracts/{id}/sdc-quitcon-card` | Card em contrato `ACCEPTED`/`SIGNED` |
| POST | `/proposals/{id}/calculate-sdc` | Retorna `quitcon_sdc` embutido |

## Arquivos

- `backend/app/quitcon_engine.py` — `gerar_tabela_projecao_quitcon`, `gerar_integracao_sdc_quitcon`
- `frontend/components/sdc-quitcon-card.tsx` — card + tabela + modal
- `docs/source/doc256_extract.txt` — especificação original

## Fluxo “Quero avançar”

1. Cliente vê projeção QuitCon (pós-simulação SDC ou card no contrato ativo).
2. Marca confirmação e clica **Quero avançar com QuitCon**.
3. `POST /finops/sdc/start-quitcon` abre operação na esteira (`AGUARDANDO_TAPAF`) com saldo bruto da memória SDC.
4. Cliente segue em **FinOps → QuitCon** para TAPAF, administradora e demais etapas.

## Compliance

Rodapé obrigatório sobre valores estimados e reajustes INCC/IPCA da administradora.
