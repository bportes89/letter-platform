# Implantação controlada

## Execução sem Docker

A API e o worker usam o mesmo código e configurações de ambiente, mas executam em processos separados:

```bash
cd backend
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m app.worker
```

Para processar apenas um ciclo durante testes ou tarefas agendadas, use `python -m app.worker --once`.

## PostgreSQL

Configure `LETTER_DATABASE_URL=postgresql+psycopg://...`. O worker aplica `FOR UPDATE SKIP LOCKED`, permitindo múltiplas instâncias sem selecionar o mesmo job. SQLite permanece apenas para desenvolvimento local.

## Storage

`LETTER_STORAGE_BACKEND=LOCAL` mantém documentos no disco local. Em staging/produção, `S3` utiliza bucket privado, criptografia AES-256 e endpoint opcional compatível com S3. Credenciais são obtidas pela cadeia padrão do SDK e nunca devem ser gravadas no repositório.

## Logs e serviços

API e worker emitem logs JSON. Exemplos de unidades systemd e proxy Nginx estão em `deploy/`. Os arquivos precisam ser revisados com domínio, usuário, caminhos e política TLS do ambiente real.

## CI e homologação

O pipeline em `.github/workflows/ci.yml` testa migrações e backend contra PostgreSQL, executa testes, auditoria npm e build do frontend. O endpoint `/api/v1/system/homologation` informa bloqueios de configuração e fornecedores ainda simulados. O checklist operacional está em `deploy/STAGING_CHECKLIST.md`.
