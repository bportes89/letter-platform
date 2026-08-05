# Matriz de evidências de homologação

## Integrações externas — v0.15.0

| Controle | Evidência técnica | Critério de aceite |
|---|---|---|
| Allowlist | Teste rejeita base URL fora do host autorizado | Retorno 422, sem chamada externa |
| Rotação | Versão e timestamp da credencial + auditoria | Secret não aparece na API |
| Conector HTTP | Transporte simulado inspeciona URL e Authorization | Método, host e credencial corretos |
| SLA | Health check acima do limite cria incidente | Status DEGRADED e incidente aberto |
| Circuit breaker | Três falhas abrem o circuito | Novas entregas recebem 503 |
| Dead letter | Entrega esgotada é reprocessada em lote | Item retorna para RETRY_SCHEDULED |

## Controles gerais

| Controle | Evidência automatizada | Situação |
|---|---|---|
| Autenticação e RBAC | Testes de login, escopos e perfis | Implementado |
| Isolamento multi-tenant | Teste com segunda organização | Implementado |
| MFA e step-up | Testes de ativação e ações críticas | Implementado |
| Idempotência financeira | Webhooks, ledger, lances e jobs | Implementado |
| Rate limiting | Teste da janela deslizante e HTTP 429 | Implementado |
| Brute force | Evento persistente de login inválido | Implementado |
| Quotas por tenant | Configuração e bloqueio diário de jobs | Implementado |
| Migrações | `alembic upgrade head` e `alembic check` | Implementado |
| Backup | Manifesto SHA-256 e integrity check | Implementado |
| Dependências frontend | `npm audit --omit=dev` | Implementado |
| Build frontend | Next.js + TypeScript | Implementado |
| PostgreSQL | Pipeline CI com PostgreSQL 16 | Implementado |
| Carga e pentest externo | Relatórios de ferramenta independente | Pendente |
| Fornecedores reais | Termos, sandbox e homologação | Pendente |
| Jurídico e compliance | Pareceres e contratos aprovados | Pendente |
