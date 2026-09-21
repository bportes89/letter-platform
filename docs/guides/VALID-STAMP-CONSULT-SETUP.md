# Valid-Stamp — API de consultas (homologação)

## Segurança

- A **API Key** (`psk_live_…`) fica **apenas** em variáveis de ambiente do Render (serviço `letter-api`).
- **Não** commitar no Git, WhatsApp público, Vercel, nem no frontend (`NEXT_PUBLIC_*`).
- Se a chave vazar, pedir **revogação/rotação** imediata ao Paulo.

## Variáveis (backend)

| Variável | Descrição |
|----------|-----------|
| `LETTER_VALID_STAMP_API_KEY` | Chave `psk_live_…` |
| `LETTER_VALID_STAMP_API_BASE_URL` | URL base da API (confirmar com Paulo — Postman/Swagger) |

Código: `backend/app/valid_stamp_consult_client.py` (`consult()`).

## Pendências

1. **Base URL** e paths de cada consulta (Bacen, Serasa, CND, DETRAN, etc.).
2. Formato JSON de request/response por tipo de consulta.
3. Encaixe na esteira TAPAF / `pre_analysis_service` antes de `issue_stamp`.
4. **e-notariado**: sem API ainda — manter upload manual `MATRICULA_ENOTARIADO`.

## e-notariado

Até a API sair, matrícula continua como documento manual no Flash Capital / SDC.
