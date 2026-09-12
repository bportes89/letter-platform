# Validação LETTER BANK — API, webhook Asaas e sincronização
# Uso:
#   .\deploy\test-wallet-webhook.ps1
#   .\deploy\test-wallet-webhook.ps1 -WebhookToken "seu-token-do-render"

param(
    [string]$ApiBase = "https://letter-api-fobc.onrender.com/api/v1",
    [string]$Frontend = "https://plataformaletter.com.br",
    [string]$WebhookToken = ""
)

$ErrorActionPreference = "Stop"
$WebhookUrl = "$ApiBase/webhooks/asaas"
$HealthUrl = "$ApiBase/health"

Write-Host "=== LETTER BANK - validacao webhook ===" -ForegroundColor Cyan
Write-Host "API:      $ApiBase"
Write-Host "Frontend: $Frontend"
Write-Host ""

$health = Invoke-RestMethod -Uri $HealthUrl
if ($health.status -ne "ok") { throw "API indisponivel" }
Write-Host 'OK API online' -ForegroundColor Green

try {
    Invoke-RestMethod -Uri $WebhookUrl -Method Post -ContentType "application/json" -Body '{"event":"PING"}' | Out-Null
    Write-Host 'WARN Webhook aceitou chamada sem token - LETTER_ASAAS_WEBHOOK_ACCESS_TOKEN pode estar vazio' -ForegroundColor Yellow
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 401) {
        Write-Host 'OK Webhook protegido (401 sem token)' -ForegroundColor Green
    } else {
        Write-Host "INFO Webhook sem token: $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}

if ($WebhookToken) {
    $headers = @{ "asaas-access-token" = $WebhookToken }
    $body = @{
        event = "ACCOUNT_DOCUMENTATION_APPROVED"
        account = @{ id = "acct_teste_inexistente_000" }
    } | ConvertTo-Json
    $result = Invoke-RestMethod -Uri $WebhookUrl -Method Post -Headers $headers -ContentType "application/json" -Body $body
    if ($result.status -eq "ok") {
        Write-Host 'OK Webhook autenticado - endpoint responde' -ForegroundColor Green
    }
} else {
    Write-Host 'SKIP Passe -WebhookToken para testar autenticacao completa' -ForegroundColor DarkYellow
}

Write-Host ""
Write-Host "=== Variaveis esperadas no Render (letter-api) ===" -ForegroundColor Yellow
Write-Host "LETTER_API_PUBLIC_URL=$ApiBase"
Write-Host "LETTER_PUBLIC_APP_URL=$Frontend"
Write-Host "LETTER_ASAAS_WEBHOOK_ACCESS_TOKEN=<token 32+ chars>"
Write-Host "LETTER_ASAAS_SUBACCOUNT_WEBHOOKS_ENABLED=true"
Write-Host ""
Write-Host "URL webhook nas subcontas Asaas:" -ForegroundColor Yellow
Write-Host $WebhookUrl
Write-Host ""
Write-Host "=== Teste manual com usuario real ===" -ForegroundColor Yellow
Write-Host "1. Cadastre usuario teste em $Frontend/cadastro"
Write-Host "2. Abra BANK e conclua verificacao"
Write-Host "3. No painel Asaas (conta matriz), confira subconta criada"
Write-Host "4. Aprove documentacao no Asaas OU envie docs pelo BANK"
Write-Host "5. Reabra o BANK (F5) - status deve atualizar sem clicar Atualizar"
Write-Host "6. Admin: GET $ApiBase/communications/deliveries"
Write-Host ""
Write-Host "Para bloquear e-mail Bem-vindo ao Asaas: habilitar BaaS com gerente Asaas." -ForegroundColor Cyan
