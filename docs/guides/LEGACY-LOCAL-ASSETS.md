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

- Cotas: campo `quota_category_id` no inventário + export `legacy_quota_category_id` na migração
- Robô Esteira 2: réguas **10% crédito / 20% entrada / 5% combo**, até **2+2** opções por lane

- Robô/Esteira 2: filtro `quota_category_id` + perfil admin (`is_bank`, correntista, nome sujo, alienações)
- UI Administradoras: alienações (categoria + ano máx.) e flags marketplace; Esteira 2 / Venda Direta Robô com subcategoria e bancos do cliente
- CMS `cms_texts`: API `/api/v1/cms/texts`, import `.../import-legacy` (`texts` + `z_text`), UI **Textos e e-mails**; páginas públicas `GET /api/v1/public/site/cms/pages/{slug}`
- Chat público: subcategoria + bancos do cliente antes do crédito; Esteira 2 usa os mesmos filtros do admin
- **Qualificação SDC** (`partner_qualification_tiers`): API `/api/v1/sdc/partner-qualification-tiers`, import legado `affiliates_qualification`, apuração preview/apply; bônus `%` somado à franquia em comissões SDC; UI `/modules/sdc-partner-qualifications`

Próximos blocos: contrato admin (x_settings id 11), multi-seleção de bancos no widget do chat, e-mails marketplace via `cms_texts`.
