# Suíte de qualidade e segurança

## Proteções implementadas

- Janela deslizante de requisições por IP.
- Limite específico por IP e e-mail no login.
- Registro persistente de tentativas inválidas e bloqueios.
- Quotas de jobs, comunicações, API e storage por organização.
- Bloqueio HTTP 429 quando a quota operacional é atingida.
- Consulta administrativa dos eventos de segurança.

O limitador em memória atende ao desenvolvimento local. Em produção com múltiplas réplicas, deve ser substituído por Redis ou gateway distribuído, preservando a mesma política.

## Backup e recuperação

SQLite utiliza a API de backup consistente do próprio banco. PostgreSQL utiliza `pg_dump` em formato custom. Cada backup gera manifesto com data, tamanho e SHA-256. A verificação SQLite executa `PRAGMA integrity_check` e confirma a presença das tabelas.

Exemplos:

```bash
python -m app.backup create backups/letter.db
python -m app.backup verify backups/letter.db
```

Backups de produção devem ser criptografados, enviados para conta/bucket separado, possuir retenção imutável e passar por restauração periódica.
