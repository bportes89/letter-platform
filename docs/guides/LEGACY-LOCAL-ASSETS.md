# Ativos legados no workspace (referência local)

Material do sistema antigo disponível na máquina de desenvolvimento — **não versionar dumps com PII**.

| Local | Conteúdo |
|-------|----------|
| `legacy/letter_banco_new.sql` | Dump MariaDB (~7,5 MB): `quotas`, `quotas_categories`, `texts`, `affiliates_qualification`, menus, etc. |
| `legacy/export/bundle.json` | Export ETL (`export_legacy_v1.py`) para dry-run/apply de migração |
| `docs/source/paulo-marketplace/letter-zip/` | Código Laravel/Vue extraído + `z_docs/system/*.md` |
| `docs/LEGACY_MIGRATION_MAP.md` | Mapeamento entidades legado → LETTER |

## Categorias de cotas na LETTER

- Tabela: `quota_categories` (API `/api/v1/marketplace/quota-categories`)
- UI: **Cartas contempladas → Categorias de cotas**
- Import idempotente: `POST .../quota-categories/import-legacy` lê `legacy/letter_banco_new.sql` quando o arquivo existe no host da API

Próximos blocos sugeridos: vínculo `quotas.legacy_category_id`, templates `texts`, qualificação de parceiros.
