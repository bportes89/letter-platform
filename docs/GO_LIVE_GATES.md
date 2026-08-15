# Gates de go-live de fornecedores

## Fluxo operacional

1. Configurar a integração, allowlist, credencial e perfil de onboarding.
2. Validar saúde, circuito, conciliação e evidências de homologação.
3. Executar `POST /api/v1/system/integrations/{id}/certify`.
4. Registrar decisões de Segurança, Jurídico, Compliance e Operações.
5. Executar a avaliação formal de go-live.
6. Tratar todos os blockers e repetir a avaliação.

## Critérios obrigatórios

| Gate | Condição de aprovação |
|---|---|
| Ambiente | Integração configurada como `PRODUCTION` |
| Adaptador | Implementação oficial do fornecedor registrada no código |
| Certificação | Última execução com todos os oito controles aprovados |
| Aprovações | Segurança, Jurídico, Compliance e Operações em `APPROVED` |
| Incidentes | Nenhum incidente aberto ou reconhecido |
| Saúde | Provedor `UP` e circuit breaker `CLOSED` |

Toda avaliação gera um snapshot, lista de bloqueadores, responsável, data e hash SHA-256. A plataforma não interpreta uma aprovação administrativa como autorização para movimentar dinheiro: a trava financeira geral e os demais controles regulatórios continuam válidos.
