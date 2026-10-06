# Inter — pagamentos PIX (parceiros e fornecedores)

API **separada** da cobrança (entrada marketplace / TAPAF / LSS). Especificação de negócio: `Documento (170).docx` (Paulo).

## Fluxo na LETTER

1. Comissão liberada (`AVAILABLE`) após NF/recibo (já existente).
2. Parceiro solicita saque (`POST /wallet/me/legacy-withdrawals`) com chave PIX.
3. Se `LETTER_INTER_PAYOUT_*` configurado e `LETTER_INTER_PAYOUT_AUTO_ON_WITHDRAW=true` (default), a API chama **PIX saída** no Inter.
4. Status do saque: `PROCESSING` → webhook/confirmação → `PAID` (baixa comissão).

Fornecedor: mesmo fluxo automático em `supplier_withdrawals` ao solicitar saque no portal.

## Variáveis Render (não commitar secrets)

| Variável | Descrição |
|----------|-----------|
| `LETTER_INTER_PAYOUT_CLIENT_ID` | Client ID da aplicação **pagamentos** no Inter |
| `LETTER_INTER_PAYOUT_CLIENT_SECRET` | Client secret (rotacionar se vazou no WhatsApp) |
| `LETTER_INTER_PAYOUT_CONTA_CORRENTE` | Conta PJ (pode repetir a da cobrança se for a mesma) |
| `LETTER_INTER_PAYOUT_CERT_PATH` | Ex.: `/tmp/inter-payout/Inter API_Certificado.crt` |
| `LETTER_INTER_PAYOUT_KEY_PATH` | Ex.: `/tmp/inter-payout/Inter API_Chave.key` |
| `LETTER_INTER_PAYOUT_CERT_BASE64` | Cert do zip em Base64 (boot Render) |
| `LETTER_INTER_PAYOUT_KEY_BASE64` | Chave do zip em Base64 |
| `LETTER_INTER_PAYOUT_WEBHOOK_ACCESS_TOKEN` | Token do webhook de liquidação PIX (opcional) |
| `LETTER_INTER_PAYOUT_AUTO_ON_WITHDRAW` | `true` / `false` |
| `LETTER_INTER_PAYOUT_ON_FISCAL_RELEASE` | `true` = PIX automático ao validar NF (doc 170), sem clicar em Sacar |

Escopos no painel Inter: `pagamento-pix.write`, `pagamento-pix.read`, `extrato.read`, `saldo.read`.

## Materializar cert no PC (exemplo PowerShell)

Extraia o zip `Inter_API-Chave_e_Certificado (2).zip` e gere Base64 **localmente** (não enviar no chat):

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\caminho\Inter API_Certificado.crt"))
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\caminho\Inter API_Chave.key"))
```

O `start_cloud.sh` roda `materialize_inter_certs.py`, que grava cobrança **e** pagamentos se `LETTER_INTER_PAYOUT_*_BASE64` estiverem setados.

## Webhook

- URL: `POST {LETTER_API_PUBLIC_URL}/webhooks/inter-payout`
- Header/query: mesmo padrão da cobrança (`x-inter-webhook-token` = `LETTER_INTER_PAYOUT_WEBHOOK_ACCESS_TOKEN`)
- Fecha saques em `PROCESSING` → `PAID` (parceiro baixa comissão; fornecedor já teve saldo reservado no pedido)

## Scripts

```powershell
# PC com .env payout + cert
$env:LETTER_INTER_PAYOUT_WEBHOOK_URL = "https://letter-api-fobc.onrender.com/api/v1/webhooks/inter-payout"
py backend/scripts/register_inter_payout_webhook.py

# Cron fallback (poll PROCESSING) — mesmo LETTER_CRON_SECRET do Render
py backend/scripts/cron_inter_payout_poll.py
```

Status de saque: `PROCESSING`, `AWAITING_BALANCE` (saldo Inter), `FAILED`, `PAID`.

Admin:

- `POST /marketplace/partner-withdrawals/{id}/retry-inter-payout`
- `POST /marketplace/supplier-withdrawals/{id}/retry-inter-payout`

O cron `inter-payout-poll` consulta saques **parceiro e fornecedor** em `PROCESSING` / `AWAITING_BALANCE`.

## Pendências

- Registrar webhook no Inter (`register_inter_payout_webhook.py`) e cron opcional no Render.
- Homologação E2E com conta real; ajustar payload do webhook se o Inter divergir.
