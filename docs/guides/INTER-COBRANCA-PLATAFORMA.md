# Cobrança da plataforma — Banco Inter

## Visão (pedido do cliente)

**Uma integração Inter para qualquer cobrança na LETTER:** assinatura do SaaS (LSS), TAPAF, entrada de carta contemplada (marketplace) e demais títulos comerciais emitidos pela plataforma.

- **Emissão:** API de cobrança Inter (boleto + PIX), centralizada em `backend/app/inter_cobranca_helpers.py` (`issue_inter_charge`).
- **Baixa:** webhook único `POST /api/v1/webhooks/inter` (`inter_webhook_service.handle_inter_webhook`), evento `situacao=RECEBIDO`, chave `codigoSolicitacao`.
- **Registro no Inter:** `backend/scripts/register_inter_webhook.py` (URL pública + token `LETTER_INTER_WEBHOOK_ACCESS_TOKEN`).

**Não substitui** o Bank legado Asaas (wallet, subcontas, KYC parceiro) — apenas o **recebível comercial** LETTER na conta Inter.

## Matriz produto × implementação

| Produto / cobrança | Kind (`inter_platform_charge`) | Emissão | Webhook |
|--------------------|--------------------------------|---------|---------|
| Entrada marketplace | `MARKETPLACE_ENTRADA` | `inter_boleto_service.issue_marketplace_boleto` | `apply_inter_payment_received` → situação **PAGO** |
| TAPAF pré-análise (SDC) | `TAPAF_PRE_ANALYSIS` | `pre_analysis_service` → Inter | `confirm_tapaf_payment_from_inter` → **TAPAF_PAID** |
| Mensalidade LSS (SaaS) | `LSS_SAAS_MONTHLY` | `lss_inter_billing` | `handle_lss_inter_payment_webhook` → **ACTIVE** |
| TAPAF QuitCon | `TAPAF_QUITCON` | `tapaf_inter_service` + `quitcon_service` | `confirm_quitcon_tapaf_from_inter` |
| TAPAF Lease Equity | `TAPAF_LEASE_EQUITY` | Aceite manifesto → `tapaf_inter_service` + `lease_equity_service` | `confirm_lease_tapaf_from_inter` (exige `TAPAF_CHECKOUT_ACCEPTED`) |
| Cobrança avulsa (Collections) | `AD_HOC` | *pendente* (hoje só cadastro manual / URL externa) | *pendente* |

Ordem de tentativa no webhook (evita colisão de `codigoSolicitacao`): marketplace → TAPAF pré-análise → LSS → QuitCon → Lease Equity.

## Variáveis de ambiente (produção)

Ver também `docs/MARKETPLACE.md`.

- `LETTER_INTER_CLIENT_ID`, `LETTER_INTER_CLIENT_SECRET`, `LETTER_INTER_CONTA_CORRENTE`
- `LETTER_INTER_CERT_PATH`, `LETTER_INTER_KEY_PATH` (ou `LETTER_INTER_*_BASE64` no boot Render)
- `LETTER_INTER_WEBHOOK_ACCESS_TOKEN`, `LETTER_API_PUBLIC_URL`
- `LETTER_INTER_BOLETO_VENCIMENTO_DIAS`

## Testes rápidos

```powershell
# Simular pagamento no webhook (ajuste codigo e valor)
.\deploy\test-lss-inter-webhook.ps1 -CodigoSolicitacao "<uuid-inter>" -Valor 52030.00
```

## Próximos passos sugeridos

1. Publicar QuitCon / Lease Equity TAPAF via Inter (código local — validar homologação).
2. Emitir cobranças avulsas (`POST /collections/ad-hoc-charges`) direto no Inter + handler `AD_HOC` no webhook.
3. Índice opcional `codigo_solicitacao` por entidade (hoje busca em JSON / scan limitado em marketplace).
