# A12 — dispara imports legado via API (SQL deve existir no host da API).
# Uso:
#   $env:LETTER_API_BASE = "https://sua-api.onrender.com/api/v1"
#   $env:LETTER_ACCESS_TOKEN = "<jwt admin>"
#   .\deploy\import-a12-api.ps1

$ErrorActionPreference = "Stop"
$base = ($env:LETTER_API_BASE ?? "http://localhost:8001/api/v1").TrimEnd("/")
$token = $env:LETTER_ACCESS_TOKEN
if (-not $token) {
    Write-Error "Defina LETTER_ACCESS_TOKEN (JWT do admin)."
}

$headers = @{
    Authorization = "Bearer $token"
    "Content-Type" = "application/json"
}

function Invoke-LetterPost($path) {
    $uri = "$base$path"
    Write-Host "POST $uri"
    Invoke-RestMethod -Method Post -Uri $uri -Headers $headers | ConvertTo-Json -Depth 6
}

Invoke-LetterPost "/marketplace/quota-categories/import-legacy"
Invoke-LetterPost "/admin/org-settings/import-legacy"
Invoke-LetterPost "/cms/texts/import-legacy"
Invoke-LetterPost "/sdc/partner-qualification-tiers/import-legacy"
Invoke-LetterPost "/cms/texts/ensure-marketplace-emails"
Invoke-LetterPost "/marketplace/suppliers/ensure-defaults"

Write-Host "OK — imports SQL concluídos. Para cotas/admins/rede, use admin/migration/apply com bundle JSON."
