# Qualificação de parceiros — legado × LETTER

**Fonte legado:** `docs/source/paulo-marketplace/letter-zip/z_docs/system/qualificacoes.md`  
**Menus PHP:** 1039 (faixas), 1040 (apuração SDC), 1041 (histórico)

---

## O que o legado tem (e o que **não** tem)

| Legado | LETTER |
|--------|--------|
| Menu **1039** — CRUD `affiliates_qualification` (faixas + `price_bonus` %) | `/modules/sdc-partner-qualifications` → aba **Faixas** + `POST /sdc/partner-qualification-tiers/import-legacy` |
| Menu **1040** — apuração por período, vendas **SDC** (`categories = 27`, concluídas) | Aba **Apuração SDC** + `preview` / `apply` / `clear-preview` |
| Menu **1041** — histórico `affiliates_qualification_historical` | `GET /sdc/partner-qualifications/appraisal/history` |
| Bônus de qualificação na **% da franquia** só em venda **SDC** | `compute_chain_commissions(..., is_sdc=True)` soma `qualification_bonus_pct` |
| Vendas **cartas / marketplace / chat** (não-SDC) | Comissão em cadeia **sem** bônus de qualificação (igual `SalesFinalizeService::__resolve_porc_franquia`) |

**Não existe no legado:** menu ou apuração de “gratificação marketplace” separada. Qualificação + apuração são **exclusivas do SDC**.

---

## APIs LETTER (admin)

| Ação | Método e rota |
|------|----------------|
| Listar / criar faixas | `GET/POST /api/v1/sdc/partner-qualification-tiers` |
| Import SQL `affiliates_qualification` | `POST /api/v1/sdc/partner-qualification-tiers/import-legacy` |
| Listar franquias (preview no usuário) | `GET /api/v1/sdc/partner-qualifications/appraisal/franchises` |
| Calcular preview | `POST /api/v1/sdc/partner-qualifications/appraisal/preview` |
| Aplicar (promove faixa + histórico) | `POST /api/v1/sdc/partner-qualifications/appraisal/apply` |
| Limpar preview (modo sem período) | `POST /api/v1/sdc/partner-qualifications/appraisal/clear-preview` |
| Histórico | `GET /api/v1/sdc/partner-qualifications/appraisal/history` |

---

## Homologação rápida

1. Importar faixas do SQL legado ou cadastrar manualmente.
2. Ter SDCs **aprovados** no período com `partner_user_id` na cadeia de franquia.
3. Apuração → calcular → conferir valor e faixa preview → aplicar.
4. Nova venda SDC da franquia deve refletir `porc_qualification_bonus_pct` no cálculo de comissão.
5. Venda marketplace (não-SDC): bônus de qualificação deve permanecer **0**.
