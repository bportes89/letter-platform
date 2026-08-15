# Hardening operacional

## Fila durável

Jobs operacionais são persistidos no banco com organização, tipo, payload, chave idempotente, tentativas e resultado. Falhas transitórias usam agendamento com backoff exponencial; o esgotamento das tentativas envia o job para `DEAD_LETTER`. Reenvios da mesma chave não duplicam trabalho.

O processador desta versão é acionado pela API para facilitar o desenvolvimento local sem Docker. Em produção, a mesma tabela deve ser consumida por worker separado, com lock transacional e `SKIP LOCKED` no PostgreSQL.

## Observabilidade e disponibilidade

- `X-Request-ID` recebido ou gerado em toda requisição.
- Tempo de resposta retornado em `X-Response-Time-Ms`.
- Endpoint de readiness com teste real do banco.
- Métricas de jobs pendentes, concluídos, retries, tentativas e dead letter.
- Fila e métricas isoladas por organização.

## Segurança HTTP

A API envia proteção contra MIME sniffing, clickjacking, vazamento de referrer e acesso indevido a câmera, microfone e geolocalização. A política CSP da API bloqueia conteúdo por padrão.

## Próximos gates

Homologação ainda requer PostgreSQL gerenciado, secrets manager, worker separado, logs estruturados, OpenTelemetry, rate limiting distribuído, backup testado, SAST/DAST, pentest, testes de carga e fornecedores externos homologados.
