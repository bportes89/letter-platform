# Valid-Stamp — API Prismafy (consultas)

Documentação completa do fornecedor: **`docs/source/integracao-letter.html`** (export Prisma Studio / Prismafy para LETTER FRANQUEADORA).

## API

| Item | Valor |
|------|--------|
| Base URL padrão | `https://api.prismafy.com.br` |
| Autenticação | `Authorization: Bearer psk_live_…` |
| Execução | `POST /api/v1/executions/<template_id>/run/` |
| Resultado (async) | `GET /api/v1/executions/<id>/result/` |
| PDF | `GET /api/v1/executions/<id>/pdf/` |

Templates liberados para LETTER (IDs no HTML e em `backend/app/prismafy_templates.py`):

- Gravame, RENAJUD, FIPE, roubo/furto, histórico proprietários  
- CND federais, CNDT, PGFN, FGTS  
- CPR CPF/CNPJ, Pefin, ações judiciais PF, TJSP  

## Variáveis (Render — `letter-api`)

| Variável | Descrição |
|----------|-----------|
| `LETTER_VALID_STAMP_API_KEY` | Chave `psk_live_…` (painel Prismafy) |
| `LETTER_VALID_STAMP_API_BASE_URL` | Opcional; default `https://api.prismafy.com.br` |

**Nunca** expor a chave no frontend nem no Git.

## Código

- `backend/app/valid_stamp_consult_client.py` — `run_template()`, `consult("gravame", {"placa": "…"})`
- `backend/app/prismafy_templates.py` — mapa slug → `template_id`

## Selo visual na plataforma

- **Gráfico:** componente `ValidStamp` (anel VALID STAMP) — módulo **LSS** e **Pré-análise** após emissão.
- **Rodapé público:** selo **Asaas BaaS** (pagamentos), não Prismafy.

## Pendências de produto

1. Ligar consultas obrigatórias (ex.: gravame SDC veículo) na esteira TAPAF antes de `issue_stamp`.
2. Webhook Prismafy `execution.finished` (opcional) para evitar polling.
3. e-notariado: upload manual até API do fornecedor.
