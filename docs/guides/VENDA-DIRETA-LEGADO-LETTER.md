# Checklist — Venda Direta (Manual + Robô): legado × LETTER v0.24

Referência para espelhar regras da **plataforma antiga (Paulo / `039_Letter`)** nas esteiras **Venda Direta Manual** e **Venda Direta Robô** da LETTER.

**Fontes legado no repositório (local):**

| Tipo | Caminho |
|------|---------|
| Manuais | `docs/source/paulo-marketplace/letter-zip/z_docs/system/1_admin__venda_direta.md` |
| Manuais | `docs/source/paulo-marketplace/letter-zip/z_docs/system/1_admin__venda_direta - robo.md` |
| Robô (motor) | `docs/source/paulo-marketplace/letter-zip/..laravel/app/Support/chat.php` (`CHAT_FLOW_ROBOT`) |
| Venda direta (serviço) | `docs/source/paulo-marketplace/letter-zip/..laravel/app/Services/SalesDirectService.php` |
| API Robô admin | `docs/source/paulo-marketplace/letter-zip/..laravel/app/Http/Controllers/Admin/SalesDirectRoboController.php` |
| Front Robô | `docs/source/paulo-marketplace/letter-zip/vue/src/pages_admin/new/z/venda_direta_robo.vue` |
| Dump / ETL | `legacy/letter_banco_new.sql`, `legacy/export/bundle.json`, `docs/LEGACY_MIGRATION_MAP.md` |

**Implementação LETTER hoje:**

| Área | Caminho |
|------|---------|
| Motor Esteira 2 / matching | `backend/app/marketplace_service.py` |
| Venda Direta Robô | `backend/app/sales_direct_robo_service.py` + `frontend/components/venda-direta-robo-module.tsx` |
| Venda Direta Manual | `backend/app/sales_direct_manual_service.py` + `frontend/components/venda-direta-manual-module.tsx` |
| Resumo produto | `docs/MARKETPLACE.md` |

**Legenda de status**

| Status | Significado |
|--------|-------------|
| **OK** | Comportamento equivalente (ou aceito como evolução documentada) |
| **Parcial** | Mesma intenção, diferença numérica ou de UX |
| **Gap** | Legado faz X; LETTER ainda não espelha |
| **LETTER+** | LETTER exige/entrega mais que o legado (ex.: Nina, Bacen) |
| **N/A** | Modelo diferente (subcategorias legado vs Imóvel/Veículo LETTER) |

---

## 1. Motor do robô (crédito / entrada / junção)

Fonte legado: `chat.php` — `CRUZAMENTOS_PORC_1` (10), `CRUZAMENTOS_PORC_1_ENTRADA` (20), `CRUZAMENTOS_PORC_2` (5), `CONTAS_POR_PRECO` / `CONTAS_POR_ENTRADA` (2).

| # | Regra (legado) | LETTER hoje | Status | Onde ajustar (se Gap) |
|---|----------------|-------------|--------|------------------------|
| 1.1 | Tolerância **crédito** 10% | `ESTEIRA2_BAND_PERCENT = 10` | **OK** | `marketplace_service.py` |
| 1.2 | Tolerância **entrada** 20% | Mesma régua 10% para crédito e entrada | **Gap** | `ESTEIRA2_BAND_PERCENT` ou constante separada `ENTRADA` |
| 1.3 | Junção de cotas tolerância **5%** | Combo usa banda 10% | **Gap** | `_eligible_combo_candidate` / banda dedicada combo |
| 1.4 | Até **2** opções lane crédito + **2** entrada | Limite **1** + **1** (`ESTEIRA2_*_LANE_LIMIT`) | **Gap** | `ESTEIRA2_CREDIT_LANE_LIMIT`, `ESTEIRA2_ENTRADA_LANE_LIMIT` |
| 1.5 | Junção só **mesma administradora** | Mesma regra | **OK** | `marketplace_service.py` |
| 1.6 | Máx cotas na junção (legado até 30 no pool) | Combo até 3 cotas | **Parcial** | `max_combo_size` |
| 1.7 | Rollover parcela vencendo (7 dias) | `INSTALLMENT_ROLLOVER_DAYS = 7` | **OK** | `pricing_for_quota` |
| 1.8 | Markup fornecedor (+3% / +10%) na entrada | `quota_supplier_service` + `pricing_for_quota` | **OK** | CRUD Fornecedores |
| 1.9 | `porc_a_mais` afiliado na entrada (robô/chat) | Chat: `affiliate_markup_service`; **Robô admin: não aplica** | **Gap** | `sales_direct_robo_service.search` + `pricing_for_quota` |
| 1.10 | SDC zera markup afiliado | N/A em cartas contempladas | **N/A** | — |
| 1.11 | Filtro administradoras por categoria/ano (`CHAT_FLOW_ROBOT__admins_categorias`) | Bacen `approval_rules` + categoria Imóvel/Veículo | **Parcial** | Espelhar matriz admin×categoria se cliente exigir paridade 1:1 |
| 1.12 | Filtro bancos correntista / bancos problema | Não exposto na UI Robô LETTER | **Gap** | Front robo + payload + motor (se ainda usado no legado ativo) |
| 1.13 | Nome sujo (Sim/Não) | `has_credit_restriction` + `accepts_dirty_name` / SCR | **Parcial** | UI já tem checkbox; alinhar mensagens com legado |
| 1.14 | Renda comprovável (holerite, IR, …) | Robô LETTER: não coleta checkboxes | **Gap** | Só se cliente ainda exige no admin |
| 1.15 | Perfil Bacen (renda × parcela, lastro, idade bem) | `admin_profile_blockers` | **LETTER+** | Já na Manual e no match Esteira 2 |
| 1.16 | Varredura Nina antes de vender | Manual: obrigatória; Robô: exige `CLEARED` no pool opcional | **LETTER+** | `sales_direct_manual_service`, inventário |

---

## 2. Venda Direta Robô — fluxo e API

Legado: `SalesDirectRoboController` + doc `1_admin__venda_direta - robo.md`.  
LETTER: `POST /marketplace/venda-direta-robo/search` e `/confirm`.

| # | Regra / fluxo | LETTER | Status |
|---|----------------|--------|--------|
| 2.1 | Wizard 2 passos (buscar → confirmar) | 3 passos UI (form → escolha → sucesso) | **OK** |
| 2.2 | Sem match: apaga pré-cadastro | Search sem match: lead não criado / vazio (`lead_id` "") | **OK** |
| 2.3 | Com match: cria Lead antes de confirmar | Cria Lead no search | **OK** |
| 2.4 | Confirmação trava cota 60 min + proposta | `reserve_quota` + `Proposal` MARKETPLACE | **OK** |
| 2.5 | Mesmo motor que chat público | `esteira2_nina_curated_match` (chat usa o mesmo) | **Parcial** | Ver gaps §1 (10/20/5 e 2+2) |
| 2.6 | Parceiro opcional (Franquia) | Não no form Robô LETTER | **Gap** | `venda-direta-robo-module.tsx` + store |
| 2.7 | Atalho cadastros existentes | `GET .../venda-direta-manual/cadastros` | **OK** |
| 2.8 | CPF/CNPJ validado | `br-validation` + API | **OK** |
| 2.9 | E-mail template 1017 + senha cliente | Fluxo cadastro/conta LETTER (não template 1017) | **Parcial** | Produto/conta unificado |
| 2.10 | Snapshot JSON cotas no disco | `terms_json` + proposta / lifecycle | **Parcial** | Equivalente lógico, não arquivo `json/cotas/{id}.json` |

---

## 3. Venda Direta Manual — listagem de cotas

Legado: `SalesDirectService::cotas_options` + doc `1_admin__venda_direta.md`.  
LETTER: `GET /marketplace/venda-direta-manual/cotas`.

| # | Filtro / regra | LETTER | Status |
|---|----------------|--------|--------|
| 3.1 | Subcategoria + ano (veículos) | Categoria `REAL_ESTATE` / `VEHICLE` + ano no form cliente | **Parcial** | Modelo simplificado |
| 3.2 | `active`, status disponível, fornecedor ativo | `AVAILABLE` (+ reservada opcional); fornecedor via inventário | **Parcial** | Sem `status_api` legado |
| 3.3 | Vencimento parcela válido | Exige `installment_due_date`; bloqueia venda se falta | **OK** | Inventário |
| 3.4 | Administradora compatível categoria (`admins_categorias`) | Não filtra lista por matriz admin | **Gap** | `list_cotas_options` |
| 3.5 | `api > 0` ou admin na lista permitida | Não espelhado | **Gap** | Se ainda relevante com APIs fornecedor |
| 3.6 | Ordenação por crédito crescente | Sim | **OK** |
| 3.7 | Label com crédito, entrada, parcelas, admin | `commercialQuotaDisplay` / label API | **OK** |
| 3.8 | Refino UI ±10% crédito/entrada | `SEARCH_BAND = 0.1` no front | **Parcial** | Legado manual **não** busca por valor (só dropdown) |
| 3.9 | Junção manual N cotas mesma admin | `quota_ids` + `pricing_for_combo` | **OK** | `sales_direct_manual_service.store` |
| 3.10 | Entrada na lista já com markup/comissão | `entrada_final` em `pricing_for_quota` | **OK** |

---

## 4. Venda Direta Manual — gravar venda

Legado: `SalesDirectService::store_manual` + `aggregate_cotas`.

| # | Regra | LETTER | Status |
|---|--------|--------|--------|
| 4.1 | Parceiro opcional; manual **sem** `porc_a_mais` na entrada | `partner_user_id`; sem markup afiliado na entrada | **OK** |
| 4.2 | `quem_paga_comissao`: comissão plataforma sobre **soma créditos** | `platform_fee_percent` por fornecedor em `pricing_for_combo` | **Parcial** | Conferir “qualquer fornecedor cobra cliente” |
| 4.3 | Totais: crédito soma, entrada soma ajustada, parcelas = MAX | `pricing_for_combo` | **OK** |
| 4.4 | Gate renda, bem, ano veículo, SCR/Bacen | `admin_profile_blockers` antes de gravar | **LETTER+** |
| 4.5 | Nina na cota se não `CLEARED` | `run_nina_quota_scan` | **LETTER+** |
| 4.6 | Trava 60 min + proposta SUBMITTED | `reserve_quota` + `Proposal` | **OK** |
| 4.7 | Endereço completo obrigatório | Sim | **OK** |
| 4.8 | PJ: razão social, ramo, faturamento | LETTER: PF/PJ documento; campos PJ limitados no form | **Parcial** | Ampliar form se cliente exigir |

---

## 5. Pós-venda e cadastros (comum)

| # | Legado | LETTER | Status |
|---|--------|--------|--------|
| 5.1 | Tudo cai em Cadastros / pipelines | `GET /marketplace/cadastros` + abas | **OK** | `cadastro_service.py` |
| 5.2 | Cadastros atalho só parceiro logado | `owner_id` no manual/cadastros | **OK** |
| 5.3 | Finalização comissão fornecedor + rede | `commission_release` no lifecycle | **OK** | `docs/MARKETPLACE.md` |
| 5.4 | Situação Aguardando Pagamento → Pago → Concluído | `lifecycle.sale_status` | **OK** |

---

## 6. Prioridade sugerida para “espelhar e ganhar tempo”

Ordem recomendada para o cliente aprovar implementação:

1. **Réguas do robô (§1.1–1.4)** — crédito 10%, entrada **20%**, junção **5%**, **2+2** opções (impacto direto em “achou no legado e não acha na LETTER”).
2. **Markup afiliado no Robô admin (§1.9)** — alinhar com chat quando houver parceiro.
3. **Listagem manual (§3.4–3.5)** — só se ainda usarem matriz administradora×categoria do legado; senão manter Bacen sync.
4. **Bancos correntista/problema no Robô (§1.12)** — confirmar com cliente se ainda filtram operação.
5. Documentar na UI as réguas reais (hoje vários textos citam só “10%”).

---

## 7. Testes de regressão sugeridos

Após cada item **Gap** fechado:

- `backend/tests/test_api.py`: `test_venda_direta_robo_search_and_confirm`, `test_venda_direta_manual_store`
- Casos manuais com payload espelhando legado: crédito alvo R$ 500.000, entrada alvo com desvio **15%** (deve passar no legado, falhar na LETTER até §1.2).
- Combo duas cotas mesma admin com desvio de crédito **7%** na soma (legado 5% vs LETTER 10%).

---

## 8. O que não está neste repositório remoto

- `docs/source/paulo-marketplace/` e `legacy/*.sql` costumam ficar **apenas na máquina de desenvolvimento** (volume / dados sensíveis). O checklist assume que esses arquivos **existem localmente** como hoje.
- Produção LETTER **não** executa PHP legado; espelhamento é **reimplementação** em `marketplace_service` e módulos de venda direta.

---

*Última revisão: alinhada ao código LETTER `main` e aos z_docs do `letter-zip` no workspace.*
