# Marketplace — Cartas contempladas

Duas esteiras operacionais para parceiros e clientes.

## Fonte das regras

A análise lê `Administrator.rules_json` (painel), **incluindo** `approval_rules` vindas do sync Bacen (renda/SCR).

- Sync Bacen (botão ou cron) atualiza o JSON; o matching **consome** `approval_rules.min_income_margin` e `scr_clear_required`.
- LTV Bacen (`max_ltv_percent`) permanece para produtos de crédito fiduciário — no Marketplace o lastro é **crédito ≤ valor do bem**.
- Campos relevantes: `max_asset_age_years`, `allowed_categories`, `accepts_dirty_name`, `accepts_zero_km`, `min_income_to_installment_ratio` (padrão **3**), `products_enabled`, `credit_utilization_rules`, `approval_rules`.

## Esteira 1 — Escolha do parceiro (`SELF_SELECT`)

1. Parceiro seleciona a carta/cota no inventário.
2. Nina executa **varredura cadastral** (se ainda não estiver `CLEARED`).
3. Nina valida **perfil do cliente** contra regras internas + Bacen/approval_rules + lastro.
4. **Renda comprovada ≥ N × parcela** (N interno ou margem Bacen).
5. Se o cliente **não tiver perfil**, Nina retorna **alternativas** ranqueadas.
6. Parceiro trava a cota por **60 minutos** e segue em **Propostas** → contrato.

**API:** `POST /api/v1/marketplace/esteira-1/assess`

## Esteira 2 — Robô Nina (`NINA_CURATED`) — regras Paulo Stutz

1. Informe **crédito alvo**, **entrada alvo** (opcional), categoria, ano do bem e perfil.
2. **Régua de corte 5%** em crédito e em entrada.
3. Entrega até **2 opções na lane crédito** + **2 na lane entrada** (dedupe).
4. Combinação de cotas (junção) só na mesma administradora (até `max_combined_quotas`).
5. **Rollover 7 dias:** se `installment_due_date` ≤ 7 dias, reduz 1 em `remaining_installments` e soma a parcela na entrada.
6. **Markup na entrada** (% do crédito), conforme `supplier_source`:
   - Fraga / Bittelo / Lance → **+3%**
   - Uni Contemplados / Contemplado SP / Lume → **+10%**
7. Parceiro trava a opção e segue em Propostas.

**API:** `POST /api/v1/marketplace/esteira-2/match`  
Payload extra: `target_entrada` (opcional).  
Resposta: `matches`, `credit_matches`, `entrada_matches`, `band_percent`.

## Regras de perfil (operacionais)

| Regra | Fonte |
|-------|--------|
| Idade máxima do bem (veículo) | `max_asset_age_years` |
| Categorias aceitas | `allowed_categories` |
| Nome sujo / SPC | `accepts_dirty_name` + `approval_rules.scr_clear_required` |
| Zero km | `accepts_zero_km` |
| Renda × parcela | `min_income_to_installment_ratio` / `approval_rules.min_income_margin` |
| Lastro | crédito alvo ≤ valor do bem |
| Teto de crédito / combo | `credit_utilization_rules` |
| Banda 5% / lanes / rollover / markup | motor Esteira 2 |

## Inventário

Cada cota deve ter:

- `installment_value` — filtro de renda
- `installment_due_date` — rollover 7 dias
- `remaining_installments` — prazo ajustado no rollover
- `supplier_source` — chave do fornecedor (`source_key` em **Fornecedores**)
- `premium_value` — entrada/ágio base

## Fornecedores (admin)

CRUD em `GET/POST/PATCH /api/v1/marketplace/suppliers` (+ `POST .../ensure-defaults`).

- `source_key` único por org (FRAGA, BITTELO, LANCE, UNI_CONTEMPLADOS, CONTEMPLADO_SP, LUME…)
- `markup_percent` — % do crédito somado na entrada (prevalece sobre o mapa hardcoded)
- `quem_paga_comissao` — `0` fornecedor / `1` cliente embute `platform_fee_percent` na entrada

Menu: **Cartas contempladas → Fornecedores**.

## Fluxo completo

```
Cadastro (Fornecedores + Inventário) → Sync Bacen (opcional) → Varredura Nina → Marketplace / Venda Direta Robô → Trava 60 min → Proposta → Contrato (SOLD)
```

## UI

- **COMERCIAL:** Cartas contempladas → Marketplace | Venda Direta Robô | Venda Direta Manual | Cadastros | Fornecedores | Inventário
- **Propostas e simulações** → cadastro comercial unificado

## Venda Direta Robô (admin)

Wizard de 2 passos sobre o mesmo motor da Esteira 2:

1. `POST /api/v1/marketplace/venda-direta-robo/search` — dados do cliente + filtros → cria Lead (`source=VENDA_DIRETA_ROBO`) e devolve `credit_matches` / `entrada_matches`.
2. `POST /api/v1/marketplace/venda-direta-robo/confirm` — escolhe `quota_ids` → proposta `MARKETPLACE` + trava 60 min → finalize em Propostas.

Sem match no passo 1, a API responde **404** (não deixa pré-cadastro órfão).

## Venda Direta Manual (admin)

Formulário único: parceiro opcional → categoria → **uma cota** do inventário → cliente + endereço → Gravar.

1. `GET /api/v1/marketplace/venda-direta-manual/cotas?category=`
2. `GET /api/v1/marketplace/venda-direta-manual/cadastros` / `partners`
3. `POST /api/v1/marketplace/venda-direta-manual/store` — lead + proposta + Nina + trava 60 min

Entrada exibida já aplica markup/comissão do fornecedor. **Não** embute markup de afiliado na entrada (só vínculo do parceiro para comissão na finalização).

## Cadastros (admin)

Lista operacional das vendas Marketplace (chat / venda direta):

- `GET /api/v1/marketplace/cadastros?pipeline=ALL|NOVOS|NEGOCIACAO|CONCLUIDO|INCOMPLETO|COMPRAS`
- `GET/PATCH /api/v1/marketplace/cadastros/{lead_id}`

Abas espelham o pacote Paulo: Clientes, Novos, Em negociação, Concluído, Incompleto, Compras. Compra (crédito/entrada/cotas) é somente leitura; dados do cliente são editáveis.

### Situação da venda (pós-venda)

Campo explícito em `proposal.terms_json.lifecycle` (não só heurística de cota/contrato):

| Situação | Aba | Efeito |
|----------|-----|--------|
| `AGUARDANDO_PAGAMENTO` | Novos | padrão ao criar proposta Marketplace |
| `PAGO` | Em negociação | `paid_at`; cotas `RESERVED/AVAILABLE` → `SOLD` (1ª vez) |
| `CONCLUIDO` | Concluído / Compras | exige `supplier_transfer_confirmed` **ou** `force_admin_conclude` |
| `CANCELADO` / `CANCELADO_FALTA_PAGAMENTO` | só Clientes (ALL) | se comissão ainda não liberada → `SKIPPED` |

### Liberação de comissão (Concluído)

Na **primeira** transição para `CONCLUIDO`:

1. Calcula linhas **plataforma** (`credit × QuotaSupplier.platform_fee_percent`) e **fornecedor** (`entrada − plataforma`) por cota → snapshot em `lifecycle.commission_release`
2. Se houver originador na árvore SALES (`commission_originator_id` / `partner_user_id` / `lead.owner_id`), aloca Universal MMN (`CommissionEntry`, referência `MARKETPLACE_RELEASE:{proposal_id}`, status `AVAILABLE`)
3. `commission_release_status=RELEASED` (idempotente)

Extrato admin: `GET /api/v1/marketplace/extrato` (linhas fornecedor/plataforma + afiliados).

Na mesma liberação, credita **saldo do fornecedor** (`QuotaSupplier.balance_available` + `supplier_ledger_entries`, idempotente por `MARKETPLACE_RELEASE:{proposal_id}`).

Fora do escopo desta frente: crédito BANK/SEFAZ, scrape Uni/Lume, PIX automático Asaas.

## Portal do fornecedor (confirmar transferência + saldo/saque)

Fecha o gate de `CONCLUIDO` sem depender só do admin:

- Admin: `POST /api/v1/marketplace/suppliers/{id}/portal-token` → token `SUP-…` (uma vez) + URL `/portal-fornecedor?token=…`
- Fornecedor (`Authorization: Bearer <token>`):
  - `GET /api/v1/supplier-portal/me` (inclui `balance_available`)
  - `GET /api/v1/supplier-portal/transfers?status=pending|confirmed|all`
  - `POST /api/v1/supplier-portal/transfers/{lead_id}/confirm` → `supplier_transfer_confirmed=true` (exige `PAGO`; **não** conclui nem libera comissão)
  - `GET /api/v1/supplier-portal/ledger` · `GET/POST /api/v1/supplier-portal/withdrawals` (saque reserva saldo; status `PENDING`)
- Admin saques: `GET /api/v1/marketplace/supplier-withdrawals` · `POST .../{id}/process` com `action=PAID|CANCELLED` (cancelado devolve saldo)

Match: `normalize_supplier_key(quota.supplier_source)` = `QuotaSupplier.source_key`. UI: `/portal-fornecedor`.

## Boleto Inter (entrada)

Emissão da cobrança de entrada (boleto + PIX no Inter) e webhook **Pagou**:

- `POST /api/v1/marketplace/cadastros/{lead_id}/boleto` — emite (ou reutiliza) boleto; sem credenciais Inter → `provider=MOCK` (`DEV-{proposal_id}`)
- `GET /api/v1/marketplace/cadastros/{lead_id}/boleto/{token}` — PDF público com token HMAC
- `POST /api/v1/webhooks/inter` — `situacao=RECEBIDO` → `apply_situation_transition(PAGO)` (header `x-inter-webhook-token` se `LETTER_INTER_WEBHOOK_ACCESS_TOKEN` estiver setado)
- `POST /api/v1/marketplace/cadastros/{lead_id}/mock-inter-webhook` — simula Pagou em dev/testes

Persistência em `proposal.terms_json.boleto` (`codigo_solicitacao`, `amount`, `seu_numero`, `local_path`). Match do webhook: código + valor (± R$ 0,01) + situação `AGUARDANDO_PAGAMENTO`.

Env: `LETTER_INTER_CLIENT_ID`, `LETTER_INTER_CLIENT_SECRET`, `LETTER_INTER_CONTA_CORRENTE`, `LETTER_INTER_CERT_PATH`, `LETTER_INTER_KEY_PATH`, `LETTER_INTER_WEBHOOK_ACCESS_TOKEN`, `LETTER_INTER_BOLETO_VENCIMENTO_DIAS`.

## Chat público nativo (site)

Substitui o proxy `letter.app.br` quando `LETTER_CHAT_NATIVE_ENABLED=true` (padrão).

Jornada no site (`POST /api/v1/public/site/chat/home` e `.../home/{step}`):

1. Nome → e-mail (cria Lead `source=SITE_CHAT`) → WhatsApp → categoria
2. Ano (veículo) / restrição SPC → crédito → entrada → renda → valor do bem
3. Match **Esteira 2** (mesmo motor do admin) → escolha → proposta + trava 60 min (`10013`)
4. Handoff pós-match (`10014–10018` + dados `10030–10034`):
   - `10014` resumo (crédito / entrada / cotas)
   - `10030–10037` PF/PJ → CPF/CNPJ (+ razão social PJ) → CEP → número → profissão/atividade → renda/faturamento → comprovação (Holerite/IR/Decore/Extrato)
   - `10038–10040` dúvida? → lista FAQ (admin `/modules/chat-faq`, seed Paulo) → resposta + mais dúvidas / contrato (decline do contrato volta a `10038`)
   - `10015` contrato templated (HTML com dados do comprador/cota/renda; ack em `terms_json.contract_html` + `contract_ack`)
   - `10016` senha in-chat → `register_public_client` + bind; se e-mail já existe → CTA login
   - `10017` emite boleto Inter com pagador real (documento/endereço do snapshot)
   - `10018` encerramento

Resposta compatível com o widget legado (`OBJ.chat_next` + `OBJ.info` + `OBJ.lead_id`). Fallback legado: `LETTER_CHAT_NATIVE_ENABLED=false`.

### FAQ do chat (admin)

CRUD org-scoped em `marketplace_chat_faqs` (seed Paulo ids `23`, `24`, `25`, `40–42`):

- Admin UI: `/modules/chat-faq`
- `GET/POST /api/v1/marketplace/chat-faq`
- `PATCH/DELETE /api/v1/marketplace/chat-faq/{id}`
- `POST /api/v1/marketplace/chat-faq/ensure-defaults`

O chat lista só `active=true`; `public_id` = `legacy_key` (Paulo) ou UUID. Auto-seed na primeira listagem do chat se a org estiver vazia.

### Chat — Capital de Giro (SDC)

No passo de categoria, **Capital de Giro** abre a faixa `10020–10028` (paralela ao Marketplace):

1. Tipo do bem → ano (se veículo/máquina) → valor → quitado → pendência → docs  
2. `evaluate_sdc_desk` → card `sdc_result`  
3. Confirmar → `store_solicitation` (mesa SDC, status `AWAITING_DOCS`, canal `SITE_CHAT`)

Lead fica com `product_interest=SDC` / `source=SITE_CHAT`. Visibilidade operacional: **mesa SDC** (não Cadastros Marketplace).

### Chat — Flash Capital

Categoria **Flash Capital** abre a faixa `10050–10058`:

1. Tipo do bem → ano (se veículo/máquina) → valor → quitado → pendência → docs → prazo 36/60  
2. `evaluate_flash_desk` → card `flash_result` (principal LTV 40% / parcela / líquido)  
3. Confirmar → `store_solicitation` Flash (mesa, status `AWAITING_DOCS`, canal `SITE_CHAT` em `evaluation_json`)

Lead: `product_interest=FLASH_CREDIT`. Sem venda/TAPAF pelo chat nesta frente.

## Escritório do cliente — Minhas compras

Após criar conta (ou login) a partir do chat, o lead `SITE_CHAT` é vinculado (`client_user_id` + `proposal.client_user_id`):

- Cadastro público: `POST /public/site/auth/register` com `chat_lead_id` (também tenta match por e-mail do snapshot)
- Conta existente: `POST /marketplace/me/bind-chat-lead`
- Lista/detalhe: `GET /marketplace/me/compras` · `GET /marketplace/me/compras/{lead_id}`
- Boleto: `POST /marketplace/me/compras/{lead_id}/boleto` (PDF público com token HMAC)
- Contrato do chat: `GET /marketplace/me/compras/{lead_id}/contrato.pdf` (auth; exige aceite `SITE_CHAT_ACK`)
- Finalizar: `POST /marketplace/me/compras/{lead_id}/finalize` → `CONCLUIDO` (exige `PAGO` + confirmação do fornecedor; sem `force_admin`)
- Docs: `GET/POST /marketplace/me/compras/{lead_id}/documents` · `GET .../documents/{id}` (`entity_type=marketplace_lead`)

Admin Cadastros: `GET /marketplace/cadastros/{lead_id}/contrato.pdf` · `GET .../documents` · `GET .../documents/{id}` · detalhe inclui `has_site_contract` + `contract_ack`.

UI: `/modules/minhas-compras` (nav CLIENT). PATCH admin `/marketplace/cadastros/{id}` fica **403** para `CLIENT`.

## Sync de inventário (fornecedores API)

Porta do cron Paulo (`QuotasApiCronsController`) para estoque vivo:

1. No fornecedor: `sync_mode=JSON` + `api_url` (lista JSON com `id`, `valor_credito`, `entrada`, `parcelas`, `valor_parcela`, `administradora`, `categoria`, `reserva`).
2. `POST /api/v1/marketplace/suppliers/{id}/sync` — um fornecedor.
3. `POST /api/v1/marketplace/inventory/sync` — todos os JSON ativos da org.
4. Cron: `POST /api/v1/system/cron/marketplace-quota-sync` (header `x-cron-secret` se configurado).

Comportamento:

- Upsert por `(supplier_source, external_ref)`; `sync_origin=JSON`
- Someu do JSON → `INACTIVE` (não mexe em `RESERVED` / `SOLD`)
- Lista vazia ou GET com falha → **não** zera o estoque daquele fornecedor
- Markup **não** é somado no sync (Esteira 2 aplica no match)
- `SCRAPE` (Uni/Lume HTML) reservado — ainda não portado
