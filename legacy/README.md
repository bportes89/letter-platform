# Migração — sistema legado (v1)

Pasta local para os arquivos recebidos do cliente **antes** do ETL para a plataforma v0.24.

## O que colocar aqui

| Arquivo | Origem | Uso |
|---------|--------|-----|
| `letter.zip` | Paulo / WhatsApp | Código-fonte e documentação do sistema antigo |
| `letter_banco_new.sql` | Paulo / WhatsApp | Dump do banco de dados legado |

Copie os dois arquivos do WhatsApp para esta pasta:

```
letter-platform/legacy/
  letter.zip
  letter_banco_new.sql
  README.md
```

## Por que não vai para o GitHub

Os arquivos são grandes (~43 MB) e podem conter **dados sensíveis** (CPF, e-mail, senhas hash). Ficam só na sua máquina ou em storage privado — nunca commitados.

## Próximo passo (após colocar os arquivos)

1. Análise do schema SQL → `docs/LEGACY_MIGRATION_MAP.md`
2. Script `backend/scripts/export_legacy_v1.py` → gera JSON no formato do dry-run
3. Validar com `POST /api/v1/admin/migration/dry-run`
4. Apply incremental em staging

## Comandos no Windows (PowerShell)

O repositório fica em `letter-platform-v0.24.0\letter-platform\` (não existe `backend` na pasta pai).

```powershell
# Opção 1 — scripts prontos (a partir de letter-platform/)
cd C:\Users\user\Downloads\letter-platform-v0.24.0\letter-platform
.\export-legacy.ps1

# Opção 2 — comando direto
cd C:\Users\user\Downloads\letter-platform-v0.24.0\letter-platform
py backend\scripts\export_legacy_v1.py

# Dry-run após export
.\dry-run-migration.ps1
# ou
py backend\scripts\migrate_legacy.py --file legacy\export\bundle.json --dry-run
```

Export parcial (teste):

```powershell
py backend\scripts\export_legacy_v1.py --limit-quotas 100 --limit-customers 50
```
