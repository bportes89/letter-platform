# Adaptadores de fornecedores — v0.18.0

## Objetivo

A camada de adaptadores separa as regras de negócio dos protocolos de cada fornecedor. BaaS/escrow, KYC, assinatura eletrônica, WhatsApp/comunicações e NFS-e compartilham um contrato de execução, catálogo de capacidades, idempotência e trilha auditável.

## Catálogo sandbox

| Categoria | Capacidades |
|---|---|
| BaaS/escrow | `create_account`, `create_charge`, `get_transaction` |
| KYC/KYB | `start_verification`, `get_result` |
| Assinatura | `create_envelope`, `get_status` |
| Comunicações | `send_template`, `get_delivery` |
| NFS-e | `issue_document`, `get_status` |

O endpoint `GET /api/v1/system/adapter-catalog` publica esse contrato. A execução ocorre em `POST /api/v1/system/integrations/{id}/adapter/execute`, e o histórico pode ser consultado em `GET /api/v1/system/adapter-executions`.

## Controles implementados

- Chave de idempotência única por integração.
- Reutilização da chave somente com a mesma operação e o mesmo payload.
- Hash SHA-256 da entrada canônica.
- Identificador externo determinístico para repetição segura no sandbox.
- Persistência do adaptador, versão, operação, status e resultado.
- Mascaramento do destino na resposta de comunicações.
- Isolamento por organização e auditoria administrativa.
- Bloqueio de execução produtiva sem implementação oficial.

## Como registrar um fornecedor oficial

1. Receber contrato, documentação técnica, credenciais de sandbox e matriz de eventos do fornecedor.
2. Implementar uma classe compatível com `ProviderAdapter`, preservando as capacidades de negócio.
3. Mapear autenticação, mTLS, códigos de erro, retries, webhooks e reconciliação.
4. Registrar a implementação no factory por fornecedor e ambiente.
5. Executar testes de contrato e ponta a ponta no sandbox oficial.
6. Gerar evidências, concluir pentest, aprovações jurídica/compliance e decisão de go-live.

## Limite desta entrega

Os adaptadores incluídos são simuladores funcionais e não realizam chamadas a instituições reais. Nenhum fluxo financeiro produtivo deve ser habilitado até que os fornecedores sejam escolhidos e seus adaptadores oficiais sejam homologados.

## Certificação e decisão de go-live

A v0.18.0 adiciona uma matriz com oito controles: contrato registrado, capacidades declaradas, credencial, allowlist, saúde, circuit breaker, perfil de onboarding e evidências de homologação. O relatório é persistido com hash SHA-256.

O gate de produção exige também quatro aprovações independentes — Segurança, Jurídico, Compliance e Operações —, integração produtiva saudável, ausência de incidentes abertos, certificação aprovada e adaptador oficial implementado. Enquanto o código específico do fornecedor não estiver registrado, a decisão retorna `BLOCKED` com `official_adapter_not_registered`.
