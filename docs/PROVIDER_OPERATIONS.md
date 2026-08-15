# Operação de fornecedores externos

## Controles do conector HTTP

Cada integração possui uma base URL fixa e uma allowlist de hosts. As chamadas aceitam apenas GET e POST, exigem caminho relativo iniciado por `/`, não seguem redirecionamentos e utilizam timeout configurável. Em produção, somente HTTPS é aceito e endereços locais ou IPs privados literais são bloqueados.

Configuração:

- `LETTER_INTEGRATION_HTTP_TIMEOUT_SECONDS`: timeout de cada chamada.
- `LETTER_INTEGRATION_CIRCUIT_FAILURE_THRESHOLD`: falhas para abrir o circuito.
- `LETTER_INTEGRATION_CIRCUIT_COOLDOWN_SECONDS`: espera antes do estado HALF_OPEN.

## Credenciais

As credenciais são cifradas em repouso, nunca aparecem nas respostas e são enviadas ao fornecedor no header Authorization. A rotação exige step-up authentication, incrementa a versão da credencial e registra data e auditor responsável.

## SLA e incidentes

Cada health check atualiza o total de verificações, sucessos, uptime observado e latência. São abertos incidentes para indisponibilidade do fornecedor, circuito aberto, latência acima do SLA e falha de entrega de webhook.

O operador pode reconhecer ou resolver o incidente. A recuperação confirmada por health check resolve automaticamente incidentes técnicos relacionados.

## Dead letter

Entregas que esgotam as tentativas permanecem em `DEAD_LETTER`. O reprocessamento em lote aceita no máximo 100 IDs, respeita o isolamento da organização e devolve apenas itens elegíveis à fila de retentativa.

## Checklist antes de produção

1. Confirmar host e caminhos fornecidos pelo contrato técnico.
2. Registrar allowlist mínima, sem curingas.
3. Configurar credencial produtiva e validar a primeira rotação.
4. Definir SLA de latência e janela de disponibilidade.
5. Executar health check, chamada controlada e webhook assinado.
6. Simular indisponibilidade, abertura do circuito e recuperação.
7. Validar incidente, auditoria, conciliação e reprocessamento da dead letter.
