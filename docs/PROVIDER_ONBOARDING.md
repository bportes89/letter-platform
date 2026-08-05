# Onboarding de fornecedores

## Cofre de segredos

O cadastro suporta `LOCAL_ENCRYPTED`, cifrado pela chave da aplicação, e `ENV_REFERENCE`, que armazena somente o nome da variável externa. Valores secretos nunca são retornados pela API. Criação e rotação exigem autenticação reforçada e geram auditoria.

## mTLS

Certificado, chave privada e CA são referenciados por IDs do cofre. A configuração é isolada por organização e integração, permite verificação obrigatória do peer e pode permanecer desabilitada até o sandbox oficial estar disponível.

## Perfil técnico

Cada fornecedor recebe um perfil com versão da API, autenticação, health path, modo de conciliação e checklist contratual. Os estados são `DRAFT`, `BLOCKED` e `READY_FOR_HOMOLOGATION`.

## Conciliação BaaS/escrow

O importador aceita CSV UTF-8 com as colunas:

```text
external_id,event_type,amount,status
```

Cada linha é comparada com eventos internos de escrow e pagamentos. Ausência e diferença de valor geram divergência explícita. O hash do arquivo impede reprocessamento duplicado.

## Evidências

O pacote verifica allowlist, credencial, health check, circuito, mTLS quando exigido e última conciliação. Cada resultado possui JSON canônico, SHA-256, executor e timestamp. O perfil somente fica pronto quando todos os controles passam.

## Limite desta versão

A infraestrutura está pronta, mas a homologação real depende dos nomes dos fornecedores, contratos técnicos, credenciais sandbox, certificados válidos e arquivos oficiais. Esses dados não devem ser inventados nem substituídos por mocks no aceite final.
