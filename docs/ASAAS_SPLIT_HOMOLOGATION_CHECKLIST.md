# Checklist de homologação — Split nativo Asaas (MMN na fonte)

**Projeto:** LETTER Platform  
**Escopo:** Repasse automático da grade MMN (50/35/7/5/3) no momento do pagamento via API Asaas  
**Pré-requisito:** Conta Escrow/subcontas já homologadas (`ASAAS_ESCROW_HOMOLOGATION_CHECKLIST.md`)  
**Ambiente:** Sandbox → Produção  
**Contato Asaas:** integracoes@asaas.com.br

---

## 1. Objetivo

Habilitar o **split de pagamentos** para que, ao criar uma cobrança (`POST /v3/payments`), o Asaas distribua automaticamente o pool de comissão para as carteiras (`walletId`) dos parceiros — master, vendedor e uplines — sem transferência manual posterior.

**Fora do escopo deste split:** SaaS LSS e taxas bancárias mensais (continuam com apuração dia 1–30 e pagamento dia 10 via ledger interno).

---

## 2. Documentação Asaas

| Recurso | URL |
|--------|-----|
| Split de pagamentos | https://docs.asaas.com/docs/split-de-pagamentos |
| Split em cobranças avulsas | https://docs.asaas.com/docs/split-em-cobrancas-avulsas |
| Criar cobrança (campo `split`) | https://docs.asaas.com/reference/criar-nova-cobranca |
| Webhook `PAYMENT_SPLIT_DONE` | https://docs.asaas.com/docs/webhook-para-cobrancas |

---

## 3. Checklist — Asaas (cliente LETTER)

- [ ] Solicitar habilitação de **Split via API** na conta principal (sandbox + produção)
- [ ] Confirmar compatibilidade **Split + Conta Escrow** no modelo LETTER
- [ ] Confirmar se split em **assinaturas** (`/subscriptions`) será necessário na fase 2
- [ ] Registrar webhook `PAYMENT_SPLIT_DONE` na URL da plataforma
- [ ] Sandbox com subcontas de teste (master + vendedor + 3 uplines) com `walletId` conhecido

---

## 4. Configuração na plataforma

| Variável | Descrição |
|----------|-----------|
| `LETTER_ASAAS_API_KEY` | Chave da conta emissora |
| `LETTER_ASAAS_WALLET_ID` | Carteira da conta emissora (não entra no array `split`) |
| `LETTER_ASAAS_SPLIT_ENABLED` | `true` após homologação sandbox |
| `LETTER_ASAAS_WEBHOOK_ACCESS_TOKEN` | Token do webhook Asaas |

**Migration:** `alembic upgrade head` (tabela `payment_split_instructions`)

---

## 5. Endpoints LETTER (fase 1)

| Método | Rota | Uso |
|--------|------|-----|
| POST | `/api/v1/finops/mmn/split-preview` | Prévia da grade + `walletId` elegíveis |
| POST | `/api/v1/finops/mmn/payments` | Cria cobrança Asaas com split (produção/sandbox) |
| POST | `/api/v1/finops/mmn/payments/mock` | Simulação local sem API |
| GET | `/api/v1/finops/mmn/split-instructions` | Auditoria por `reference` |
| POST | `/api/v1/webhooks/asaas` | Recebe `PAYMENT_SPLIT_DONE` |

---

## 6. Critérios de aceite (sandbox)

- [ ] Prévia retorna 5 camadas com valores 50/35/7/5/3 sobre o pool informado
- [ ] Beneficiário sem subconta BANK aparece em `skipped` (residual absorvido pelo master na grade)
- [ ] Cobrança criada com `split[]` e `payment_id` retornado
- [ ] Webhook `PAYMENT_SPLIT_DONE` marca instrução como `SETTLED`
- [ ] Hold fiscal (`PENDING_FISCAL`) permanece até NF-e — split credita carteira, saque segue bloqueado pelo fluxo existente

---

## 7. Go-live produção

- [ ] `LETTER_ASAAS_SPLIT_ENABLED=true` no Render
- [ ] Webhook produção apontando para `https://letter-api-fobc.onrender.com/api/v1/webhooks/asaas`
- [ ] Piloto com um produto (ex.: TAPAF ou conclusão SDC)
- [ ] Monitoramento de instruções `SUBMITTED` sem `SETTLED` após 48h

---

*LETTER Platform — homologação split nativo Asaas*
