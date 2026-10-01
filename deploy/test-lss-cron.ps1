# Dispara manualmente o job de avaliação LSS (renovação Inter + status PAST_DUE/SUSPENDED).
# No Render, o cron letter-lss-billing-evaluation roda isso 1x/dia.
#
# Pré-requisito: LETTER_CRON_SECRET no Render e o mesmo valor abaixo.

param(
    [string] $ApiBase = "https://letter-api-fobc.onrender.com/api/v1",
    [string] $CronSecret = ""
)

if (-not $CronSecret) {
    Write-Host "Informe o secret: .\deploy\test-lss-cron.ps1 -CronSecret 'seu-letter-cron-secret'" -ForegroundColor Yellow
    exit 1
}

$uri = "$ApiBase/system/cron/lss-billing-evaluation"
Write-Host "POST $uri" -ForegroundColor Cyan

try {
    $resp = Invoke-RestMethod -Method Post -Uri $uri -Headers @{ "X-Cron-Secret" = $CronSecret }
    Write-Host "OK" -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 6
} catch {
    Write-Host "Falha: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
    exit 1
}
