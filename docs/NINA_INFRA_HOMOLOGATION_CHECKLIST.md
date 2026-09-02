# Checklist de homologação — Inventário Infra NINA v4.0

**Projeto:** LETTER Platform  
**Referência:** Inventário Infraestrutural Integrado v4.0 (TAPAF, Valid-Stamp, APIs)  
**Complementa:** `ASAAS_ESCROW_HOMOLOGATION_CHECKLIST.md`

---

## Status na plataforma (v0.24+)

| Capacidade | Código | Status |
|------------|--------|--------|
| Split TAPAF R$ 300 + R$ 1.200 | `tapaf_settlement_service.py` | Implementado (ledger sandbox) |
| Inventário pós-TAPAF | `infra_inventory_service.py` | Implementado |
| **ONR / SERP** | `infra_clients.py` + `onr_client.py` | **HTTP produção** via InfoSimples (`onr/mapa-registro-imoveis`) ou OAuth direto |
| **Serasa QSA** | `infra_clients.py` + `serasa_client.py` | **HTTP produção** (IAM + Relatório Avançado PJ) |
| InfoSimples CNDs (PGFN + FGTS + TST) | `infra_clients.py` | **HTTP produção** (mesmo token SEFAZ) |
| Fipe API Cloud (placa) | `infra_clients.py` | **HTTP produção** |
| InfoSimples SEFAZ/NF-e | `sefaz_client.py` | HTTP produção |
| DataZap, Judis, SERPRO, Molicar, INCRA | `infra_clients.py` | Sandbox + credencial → `PRODUCTION_PENDING` |
| Política split | `GET /finops/tapaf/split-policy` | Implementado |
| Catálogo provedores | `GET /finops/tapaf/infra-catalog` | Implementado (`production_ready`) |
| Liquidações | `GET /finops/tapaf/settlements` | Implementado |
| ZapSign | `zapsign_signature_service.py` | Homologado produção |
| Asaas Escrow | `asaas_escrow_service.py` | Homologado produção |

Variáveis de ambiente: ver `backend/.env.example` (seção Inventário infra TAPAF).

---

## Checklist por provedor

### P0 — Esteira imobiliária core

- [ ] **ONR / SERP** — `LETTER_ONR_CLIENT_ID`, `LETTER_ONR_CLIENT_SECRET`
- [ ] **DataZap** — `LETTER_DATAZAP_API_TOKEN`
- [ ] **Serasa Experian** — `LETTER_SERASA_API_KEY`
- [ ] **InfoSimples CNDs** — `LETTER_INFOSIMPLES_API_TOKEN`
- [ ] **Judis / Digivox** — `LETTER_JUDIS_API_KEY`

### P1 — Veículos

- [ ] **SERPRO Denatran** — `LETTER_SERPRO_API_KEY`
- [ ] **Fipe API Cloud** — `LETTER_FIPE_API_TOKEN`
- [ ] **Molicar B2B** — `LETTER_MOLICAR_API_TOKEN`

### P2 — Especializações

- [ ] **e-Notariado** (RGI Flash Capital PJ) — credenciamento CNB
- [ ] **Meta WhatsApp Cloud** — app + BM verificada
- [ ] **INCRA PIGT** — `LETTER_INCRA_API_KEY`

---

## Validação técnica após credenciais

1. Pagar TAPAF sandbox (pré-análise, QuitCon ou Lease Equity)
2. Consultar `GET /finops/tapaf/settlements/lookup?entity_type=...&entity_id=...`
3. Confirmar Lote A = R$ 300 e Lote B = R$ 1.200 (proporcional se valor ≠ 1.500)
4. Confirmar `inventory.providers[].mode` = `PRODUCTION` após configurar tokens
5. Revisar ledger (`/ledger/transactions`) com referências `tapaf-settlement-*`

---

*Documento LETTER Platform — homologação inventário NINA v4.0*
