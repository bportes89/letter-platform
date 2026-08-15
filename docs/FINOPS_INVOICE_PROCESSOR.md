# FinOps — Motor de Recibos V3

Motor lógico: `LETTER_FINOPS_INVOICE_AUTOMATION_ENGINE_2026_V3`

## Fluxo D+0

1. Webhook BaaS confirma compensação (`POST /invoices/{id}/mock-payment-webhook`)
2. `apply_payment()` marca fatura como **PAID**
3. `MotorFaturamentoEFiscalLETTERV3` gera recibo com desmembramento:
   - **Fruição (juros)** — base tributável Lucro Presumido 11,33%
   - **Amortização da recompra** — isenta
4. PDF salvo em duas rotas:
   - Área logada: `customer-vault/contracts/{id}/receipts/`
   - Vault SPE: `company-vault/partners/{partner}/contracts/{id}/receipts/`
5. E-mail/push transacional: `SENT_D+0` / `ACTIVE` (sandbox)

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/finops/billing/invoice-processor` | Processamento manual por `invoice_id` |
| GET | `/contracts/{id}/receipts` | Histórico de recibos |
| GET | `/customer/dashboard/contracts/{id}/receipts` | Espelho área logada cliente |
| GET | `/contracts/{id}/receipts/{receipt_id}/pdf` | Download PDF |

## Variáveis de ambiente

- `LETTER_VAULT_BUCKET` — bucket privado (default: `letter-vault-private`)
- `LETTER_VAULT_PREFIX` — prefixo corporativo (default: `company-vault`)
