# Mapa de migração — sistema legado LETTER (v1)

Fontes analisadas em `legacy/`:

| Arquivo | Conteúdo |
|---------|----------|
| `letter_banco_new.sql` | Dump MariaDB/phpMyAdmin (02/09/2026) — banco `letter_banco_new` |
| `letter.zip` | Laravel (`..laravel/`), frontend Vue, docs (`z_docs/system/`) |

> **Dados sensíveis:** arquivos em `legacy/` não são versionados. Este documento contém apenas metadados e mapeamento.

---

## Stack do sistema antigo

- **Backend:** Laravel (PHP 8.4), Sanctum, models em `..laravel/app/Models/`
- **Frontend:** Vue (`vue/`) + `public_html/`
- **Banco:** MariaDB 10.11 — 35 tabelas no dump

---

## Volumes estimados (dump 02/09/2026)

| Tabela legado | Registros ~ | Destino v0.24 | Prioridade |
|---------------|------------:|-----------------|------------|
| `quotas` | **21.090** | `quotas` | Alta |
| `customers` | **4.195** | `leads` (+ eventual `users` CLIENT) | Alta |
| `affiliates` | **196** | `users` + `network_nodes` | Alta |
| `customers_documents` | 265 | `documents` (fase 2) | Média |
| `administrators` | 30 | `administrators` | Alta |
| `suppliers` | 20 | `users` (QUOTA_SELLER) | Média |
| `customers_sdc` | 48 | módulo SDC / leads específicos | Média |
| `users` | 12 | `users` (staff admin) | Alta |
| `customers_sdc_documents` | (ver dump) | `documents` | Baixa |

**Total crítico:** ~25.500 registros de negócio (cotas + clientes + rede).

---

## Mapeamento entidade a entidade

### 1. `administrators` → `administrators`

| Legado | Novo |
|--------|------|
| `id` | `legacy_id_map` |
| `name` | `name` |
| `active` | regras Bacen / homologação |
| `email`, `phone` | metadados opcionais |
| — | `code` — gerar slug do nome (ex.: `HS_CONSORCIOS`) |
| — | `document` — vazio se não existir no legado |

### 2. `affiliates` → `users` + `network_nodes`

Parceiros, vendedores, supervisores, gestores e regionais da rede MMN.

| Legado `type` | Role v0.24 sugerida |
|---------------|---------------------|
| `partners` | `PARTNER` |
| `sellers` | `QUOTA_SELLER` |
| `supervisors` | `MANAGER` |
| `managers` | `MANAGER` |
| `regionais` | `MASTER_FRANCHISEE` |

| Campo legado | Campo novo |
|--------------|------------|
| `id` | `legacy_id` |
| `name` / `razao_social` | `name` |
| `email` | `email` |
| `cpf` / `cnpj` | `document` / `company_cnpj` |
| `phone` | `phone` |
| `password` (bcrypt) | **não migrar** — convite / reset |
| `url` | slug de convite / referência rede |
| flags `supervisors`, `managers`, `regionais` | árvore `network_nodes` |

**Rede:** patrocínio MMN não está explícito em coluna simples — validar no código Laravel (`Affiliates.php`, docs `z_docs/system/1_admin__parceiros_*.md`) e tabelas auxiliares.

### 3. `users` (legado) → `users` (staff)

Usuários do **painel admin** (12 registros), não confundir com `affiliates`.

| Legado | Novo |
|--------|------|
| `permissions` (JSON menu) | `Role.INTERNAL_STAFF` ou `PLATFORM_ADMIN` se `permissions_all=1` |
| `password` | reset obrigatório |

### 4. `suppliers` → `users` (fornecedores de cotas)

Fornecedores que alimentam estoque (`quotas.suppliers` → `suppliers.id`).

| Legado | Novo |
|--------|------|
| `id` | `legacy_id` + `users` com role `QUOTA_SELLER` |
| API URL em `api` | metadado / integração futura |

### 5. `customers` → `leads`

Clientes finais / pipeline comercial (4.195 registros).

| Legado | Novo |
|--------|------|
| `id` | `legacy_id` |
| `name` | `name` |
| `email`, `phone` | `email`, `phone` |
| `partners` | `owner_id` via mapa do affiliate |
| `status`, `type` | `status`, `product_interest` |
| `price`, `quotas` (JSON) | metadados / proposta |
| `cpf`/`cnpj` | campos extras ou KYC |

### 6. `quotas` → `quotas`

Maior volume (**21.090**).

| Legado | Novo |
|--------|------|
| `id` | `legacy_id` |
| `administrators` | `administrator_id` via mapa |
| `suppliers` | `seller_id` via mapa suppliers→users |
| `quotas_categories` | `category` (mapear tabela `quotas_categories`) |
| `price` | `credit_value` |
| `price_entrada` | `premium_value` |
| `price_parcela` × `parcelas` | `outstanding_balance` (calcular) |
| `date_vencimento` | `installment_due_date` |
| `status` / `active` | `status` (`AVAILABLE`, etc.) |
| `api` | referência externa (FragaeBitello etc.) |

**Atenção:** grupo/cota (`group_code`, `quota_code`) no legado parece estar em `api` / integração externa — confirmar no Laravel antes do apply.

### 7. `customers_sdc` → leads/proposals SDC

Operações SDC (48) — migrar na **fase 2** após marketplace base.

### 8. Não migrar na fase 1

| Tabela | Motivo |
|--------|--------|
| `cache`, `jobs`, `failed_jobs` | infra Laravel |
| `migrations`, `personal_access_tokens` | tokens novos |
| `x_settings`, `y_menu_*`, `z_text`, `texts` | config CMS |
| `logs`, `newsletter`, `metatags` | operacional / marketing |

---

## Ordem de carga (ETL)

```
administrators → suppliers → affiliates (users) → network_nodes
              → customers (leads) → quotas → proposals (derivadas)
```

Staff admin (`users` legado) pode entrar em paralelo após `organizations/branches`.

---

## Formato de exportação (já suportado pelo dry-run)

Script alvo: `backend/scripts/export_legacy_v1.py` (a implementar)

Entrada: `legacy/letter_banco_new.sql` ou MariaDB importado localmente  
Saída: `legacy/export/bundle.json`

---

## Riscos / decisões pendentes

1. **Senhas bcrypt Laravel** — não reutilizar; fluxo de convite + reset
2. **21k cotas** — apply em lotes (batch 500–1000) com progresso em `legacy_migration_runs`
3. **E-mails duplicados** — dry-run já detecta; definir regra (mesclar vs. pular)
4. **Single-tenant** — dump parece uma franqueadora (FPS / Letter); criar 1 `organization` + 1 `branch` default
5. **Patrocínio MMN** — confirmar no código legado antes de `network_nodes`
6. **Documentos PDF** — `customers_documents` (265) exige migração de arquivos, não só SQL

---

## Comandos úteis

```bash
# Análise rápida do dump
py backend/scripts/analyze_legacy_sql.py

# Dry-run (após export)
py backend/scripts/migrate_legacy.py --file legacy/export/bundle.json --dry-run
```

---

## Próximo passo de implementação

1. **`export_legacy_v1.py`** — parser do SQL → `bundle.json`
2. **Apply** de `administrators`, `affiliates`→`users`, `customers`→`leads`, `quotas`
3. Dry-run com dump real em staging
4. Relatório de volumes para Paulo (este doc)
