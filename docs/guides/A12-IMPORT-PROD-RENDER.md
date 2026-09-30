# A12 — Import dados prod (Paulo / homologação)

**Objetivo:** popular staging/prod com categorias, textos, settings, administradoras, cotas e rede — a partir do dump legado `letter_banco_new.sql`.

**Não commitar** o SQL nem bundles com PII no git. Mantenha o dump só no host seguro (dev ou volume Render).

---

## O que o A12 cobre

| Bloco | Origem SQL | LETTER |
|-------|------------|--------|
| Categorias / subcategorias | `quotas_categories` | `POST .../quota-categories/import-legacy` |
| Configurações gerais | `x_settings` + `z_text` | `POST .../admin/org-settings/import-legacy` |
| Textos / e-mails CMS | `texts` + `z_text` | `POST .../cms/texts/import-legacy` |
| Qualificação SDC (1039) | `affiliates_qualification` | `POST .../sdc/partner-qualification-tiers/import-legacy` |
| Administradoras + alienações, cotas, parceiros, rede | bundle JSON | `export_legacy_v1.py` → `apply_bundle` / `POST .../admin/migration/apply` |
| E-mails marketplace (opcional) | seeds | `POST .../cms/texts/ensure-marketplace-emails` |
| Fornecedores padrão (opcional) | — | `POST .../marketplace/suppliers/ensure-defaults` |

Ordem recomendada: **categorias → settings → texts → qualificação → bundle (admins/cotas)**.

---

## Caminho 1 — Shell no Render (recomendado)

1. Envie o SQL para o serviço API (volume persistente ou one-off upload), por exemplo:
   - `/app/legacy/letter_banco_new.sql` (ajuste conforme imagem/deploy).

2. Abra **Shell** do serviço `letter-api` no Render.

3. Dry-run do bundle (opcional, na sua máquina antes):
   ```bash
   cd backend
   py scripts/export_legacy_v1.py --sql ../legacy/letter_banco_new.sql --output ../legacy/export/bundle.json
   py scripts/migrate_legacy.py --file ../legacy/export/bundle.json --dry-run
   ```

4. No Render, com `LETTER_DATABASE_URL` já configurado:
   ```bash
   cd /app/backend   # ajuste ao WORKDIR da imagem
   python scripts/import_a12_prod.py \
     --sql /app/legacy/letter_banco_new.sql \
     --ensure-marketplace-emails \
     --ensure-suppliers
   ```

5. Se tiver o `bundle.json` no mesmo host:
   ```bash
   python scripts/import_a12_prod.py \
     --sql /app/legacy/letter_banco_new.sql \
     --bundle /app/legacy/export/bundle.json \
     --apply-bundle
   ```

6. Confira na UI:
   - Categorias de cotas, org-settings, Textos e e-mails
   - Administradoras (liberações), inventário de cotas
   - SDC → Qualificação de parceiros

---

## Caminho 2 — API (admin logado)

Com token JWT de um usuário com escopo admin (`inventory:write`, `admin:users`):

```http
POST /api/v1/marketplace/quota-categories/import-legacy
POST /api/v1/admin/org-settings/import-legacy
POST /api/v1/cms/texts/import-legacy
POST /api/v1/sdc/partner-qualification-tiers/import-legacy
POST /api/v1/cms/texts/ensure-marketplace-emails
POST /api/v1/marketplace/suppliers/ensure-defaults
POST /api/v1/admin/migration/dry-run   { "legacy_source": "...", "entities": { ... } }
POST /api/v1/admin/migration/apply     { mesmo body }
```

O SQL precisa existir **no filesystem do container API** para os imports `*-legacy` que leem o dump diretamente.

Script PowerShell (token + URL): `deploy/import-a12-api.ps1`.

---

## Caminho 3 — Só máquina local (cuidado)

Apontar `LETTER_DATABASE_URL` para **prod** a partir do PC só se a política do time permitir.

```powershell
cd letter-platform\backend
$env:LETTER_DATABASE_URL = "postgresql://..."
py scripts\import_a12_prod.py --sql ..\legacy\letter_banco_new.sql --apply-bundle --bundle ..\legacy\export\bundle.json
```

---

## Pós-import (checklist Paulo)

- [ ] Categorias/subcategorias batem com menu legado (ordem D4 na UI)
- [ ] 1 administradora com liberações do print
- [ ] Cotas ativas visíveis no marketplace / esteira
- [ ] E-mails marketplace no CMS (A9)
- [ ] Chat e robô com subcategorias e bancos

---

## Referências

- `docs/guides/LEGACY-LOCAL-ASSETS.md`
- `docs/LEGACY_MIGRATION_MAP.md`
- `backend/scripts/export_legacy_v1.py`, `migrate_legacy.py`, `import_a12_prod.py`
