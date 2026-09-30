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

- **Configurações gerais** (`organization_settings` / legado `x_settings`): `/api/v1/admin/org-settings`, import legado, `GET /api/v1/public/site/org-info`; contrato marketplace prioriza `marketplace_contract_html`; UI `/modules/org-settings`

- Chat público: **multi-seleção de bancos** (conta corrente e banco com problema) no passo 10071/10073, padrão comprovação de renda

- E-mails marketplace (boleto/pagamento): slugs CMS `email-marketplace-boleto`, `email-marketplace-payment-client`, `email-marketplace-payment-partner` (`kind=EMAIL`, placeholders `{{client_name}}`, etc.)
- Chat público: HTML de `sdc_flow_html` / `venda_direta_*` em `org_settings` no gate de produtos logados (campo `info_html`)

- Import legado `texts` → slugs canônicos (ids 1001/1005/1007/1009/1013–1017/1019–1020); placeholders `{nome_cliente}` convertidos para `{{client_name}}` no envio
- Gatilhos transacionais: boleto, pagamento, boas-vindas (conta chat), documento enviado (cliente), conclusão (cliente/fornecedor/parceiro/plataforma)

Próximos blocos: ver checklist completo em `docs/guides/PAULO-ENTREGA-BACKLOG.md`.

A5b/A6: cards na escolha do chat + vídeo `chat_robo_video_url` (org-settings). A9: CMS **Textos e e-mails** → «Criar e-mails marketplace (padrão)» ou import SQL (`texts` 1001–1017).
