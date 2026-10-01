# Simula webhook Banco Inter (RECEBIDO) — LSS, TAPAF ou Marketplace.
# Uso:
#   .\deploy\test-lss-inter-webhook.ps1 -CodigoSolicitacao "uuid-do-boleto" -Valor 199.90
#
# Onde pegar CodigoSolicitacao:
#   LSS: painel LSS / Cobranças → assinatura PENDING_PAYMENT (campo last_payment_id na API)
#        ou link do boleto contém a assinatura; o código é o UUID da cobrança Inter.
#   Marketplace: modal Cadastro → linha do boleto INTER (uuid após "INTER -")
#   TAPAF: checkout pré-análise / asaas_payment_id quando checkout_mode=INTER

param(
    [Parameter(Mandatory = $true)]
    [string] $CodigoSolicitacao,

    [Parameter(Mandatory = $true)]
    [decimal] $Valor,

    [string] $SeuNumero = "TESTE-LETTER",

    [string] $ApiBase = "https://letter-api-fobc.onrender.com/api/v1",

    [string] $WebhookToken = "letter-render-inter-webhook-2026"
)

$uri = "$ApiBase/webhooks/inter"
$body = @{
    situacao           = "RECEBIDO"
    codigoSolicitacao  = $CodigoSolicitacao.Trim()
    seuNumero          = $SeuNumero
    valorTotalRecebido = [double]$Valor
} | ConvertTo-Json

Write-Host "POST $uri" -ForegroundColor Cyan
Write-Host $body

try {
    $resp = Invoke-RestMethod -Method Post -Uri $uri -Headers @{
        "x-inter-webhook-token" = $WebhookToken
        "Content-Type"          = "application/json"
    } -Body $body
    Write-Host "OK" -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 6
    if ($resp.paid -ge 1) {
        Write-Host "Pagamento processado (paid=$($resp.paid)). Confira LSS / Cadastros / TAPAF no painel." -ForegroundColor Green
    } else {
        Write-Host "paid=0 — veja results[] (valor divergente, já pago, código não encontrado)." -ForegroundColor Yellow
    }
} catch {
    Write-Host "Falha: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
    exit 1
}
