# Upload de legacy/export/bundle.json para dry-run ou apply na API (producao/staging).
# Exemplo:
#   .\apply-migration-remote.ps1 -DryRun
#   .\apply-migration-remote.ps1 -Email admin@letter.com.br
#   $env:LETTER_ADMIN_PASSWORD = '...'; .\apply-migration-remote.ps1
param(
    [string]$ApiBaseUrl = "https://letter-api-fobc.onrender.com/api/v1",
    [string]$BundlePath = "legacy\export\bundle.json",
    [string]$Email = $env:LETTER_ADMIN_EMAIL,
    [string]$Password = $env:LETTER_ADMIN_PASSWORD,
    [string]$AccessToken = $env:LETTER_ACCESS_TOKEN,
    [switch]$DryRun,
    [int]$MaxRetries = 4,
    [int]$TimeoutSec = $(if ($DryRun) { 600 } else { 3600 }),
    [string]$OutDir = "artifacts"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-RetryableError {
    param($Exception)
    if ($Exception -is [System.Net.WebException]) {
        $resp = $Exception.Response
        if ($null -eq $resp) { return $true }
        $code = [int]$resp.StatusCode
        return $code -in 408, 425, 429, 500, 502, 503, 504
    }
    $httpResponseType = [Type]::GetType("Microsoft.PowerShell.Commands.HttpResponseException")
    if ($httpResponseType -and ($Exception -is $httpResponseType)) {
        $code = [int]$Exception.Response.StatusCode
        return $code -in 408, 425, 429, 500, 502, 503, 504
    }
    $msg = $Exception.Exception.Message
    return $msg -match 'timed out|timeout|connection|reset|refused|temporarily unavailable'
}

function Invoke-ApiWithRetry {
    param(
        [string]$Method,
        [string]$Uri,
        [hashtable]$Headers = @{},
        [string]$Body = $null,
        [string]$ContentType = "application/json; charset=utf-8"
    )

    $delaySec = 5
    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        try {
            Write-Progress -Activity "Chamada API" -Status "Tentativa $attempt de $MaxRetries" -PercentComplete (($attempt / $MaxRetries) * 100)
            $params = @{
                Method      = $Method
                Uri         = $Uri
                Headers     = $Headers
                TimeoutSec  = $TimeoutSec
                ErrorAction = "Stop"
            }
            if ($Body) {
                $params.Body = $Body
                $params.ContentType = $ContentType
            }
            $result = Invoke-RestMethod @params
            Write-Progress -Activity "Chamada API" -Completed
            return $result
        }
        catch {
            Write-Progress -Activity "Chamada API" -Completed
            $retryable = Test-RetryableError $_
            if (-not $retryable -or $attempt -eq $MaxRetries) {
                throw
            }
            $wait = $delaySec * $attempt
            Write-Warning "Falha na tentativa $attempt ($($_.Exception.Message)). Nova tentativa em ${wait}s..."
            Start-Sleep -Seconds $wait
        }
    }
}

function Get-AccessToken {
    if ($AccessToken) {
        Write-Step "[1/4] Usando token informado (LETTER_ACCESS_TOKEN / -AccessToken)"
        return $AccessToken
    }

    if (-not $Email) {
        $Email = Read-Host "E-mail do admin"
    }
    if (-not $Password) {
        $secure = Read-Host "Senha" -AsSecureString
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try {
            $Password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        }
        finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
    }

    Write-Step "[1/4] Login em $ApiBaseUrl"
    $loginBody = (@{ email = $Email; password = $Password } | ConvertTo-Json -Compress)
    $tokenPair = Invoke-ApiWithRetry -Method Post -Uri "$ApiBaseUrl/auth/login" -Body $loginBody
    if (-not $tokenPair.access_token) {
        throw "Login nao retornou access_token."
    }
    return $tokenPair.access_token
}

function Read-BundleWithProgress {
    param([string]$Path)
    $fullPath = Join-Path $Root $Path
    if (-not (Test-Path $fullPath)) {
        throw "Bundle nao encontrado: $fullPath`nExecute primeiro: .\export-legacy.ps1"
    }

    $file = Get-Item $fullPath
    $sizeMb = [math]::Round($file.Length / 1MB, 2)
    Write-Step "[2/4] Carregando bundle ($sizeMb MB)"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $raw = [System.IO.File]::ReadAllText($fullPath, [System.Text.Encoding]::UTF8)
    $sw.Stop()
    Write-Host ("Bundle lido em {0:N1}s" -f $sw.Elapsed.TotalSeconds)

    try {
        $parsed = $raw | ConvertFrom-Json
    }
    catch {
        throw "bundle.json invalido: $($_.Exception.Message)"
    }

    if (-not $parsed.legacy_source) {
        throw "bundle.json sem campo legacy_source."
    }

    $counts = @{}
    foreach ($prop in $parsed.entities.PSObject.Properties) {
        $entityName = $prop.Name
        $value = $prop.Value
        if ($value -is [System.Array] -or $value -is [System.Object[]]) {
            $counts[$entityName] = $value.Count
        }
    }
    if ($counts.Count -gt 0) {
        Write-Host "Entidades no bundle:"
        foreach ($key in ($counts.Keys | Sort-Object)) {
            Write-Host ("  - {0}: {1}" -f $key, $counts[$key])
        }
    }

    return $raw
}

function Show-MigrationSummary {
    param($Response)
    Write-Step "[4/4] Resultado"
    Write-Host ("Run ID:     {0}" -f $Response.id)
    Write-Host ("Modo:       {0}" -f $Response.mode)
    Write-Host ("Status:     {0}" -f $Response.status)
    if ($Response.error_message) {
        Write-Host ("Erro:       {0}" -f $Response.error_message) -ForegroundColor Red
    }
    if ($Response.started_at) { Write-Host ("Inicio:     {0}" -f $Response.started_at) }
    if ($Response.finished_at) { Write-Host ("Fim:        {0}" -f $Response.finished_at) }

    $summary = $Response.summary
    if (-not $summary) { return }

    if ($summary.ready -ne $null) {
        $color = if ($summary.ready) { "Green" } else { "Red" }
        Write-Host ("Pronto:     {0}" -f $summary.ready) -ForegroundColor $color
    }
    if ($summary.created) {
        Write-Host "Criados:"
        foreach ($key in ($summary.created.PSObject.Properties.Name | Sort-Object)) {
            Write-Host ("  - {0}: {1}" -f $key, $summary.created.$key)
        }
    }
    if ($summary.reused) {
        Write-Host "Reutilizados:"
        foreach ($key in ($summary.reused.PSObject.Properties.Name | Sort-Object)) {
            Write-Host ("  - {0}: {1}" -f $key, $summary.reused.$key)
        }
    }
    if ($summary.skipped) {
        Write-Host "Ignorados:"
        foreach ($key in ($summary.skipped.PSObject.Properties.Name | Sort-Object)) {
            Write-Host ("  - {0}: {1}" -f $key, $summary.skipped.$key)
        }
    }
    if ($summary.password_policy) {
        Write-Host ("Politica:   {0}" -f $summary.password_policy) -ForegroundColor Yellow
    }
    if ($summary.warnings -and $summary.warnings.Count -gt 0) {
        Write-Host ("Warnings:   {0}" -f $summary.warnings.Count) -ForegroundColor Yellow
    }
    if ($summary.issues -and $summary.issues.Count -gt 0) {
        Write-Host ("Issues:     {0}" -f $summary.issues.Count) -ForegroundColor Red
        $summary.issues | Select-Object -First 5 | ForEach-Object {
            Write-Host ("  - [{0}] {1}: {2}" -f $_.level, $_.entity_type, $_.message) -ForegroundColor Red
        }
        if ($summary.issues.Count -gt 5) {
            Write-Host ("  ... e mais {0} issue(s). Veja o JSON salvo em artifacts/." -f ($summary.issues.Count - 5))
        }
    }
}

$endpoint = if ($DryRun) { "dry-run" } else { "apply" }
$token = Get-AccessToken
$bundleRaw = Read-BundleWithProgress -Path $BundlePath

Write-Step "[3/4] Enviando para POST /admin/migration/$endpoint (timeout ${TimeoutSec}s)"
Write-Host "A migracao completa pode levar ~1 minuto. Aguarde..."

$headers = @{ Authorization = "Bearer $token" }
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$response = Invoke-ApiWithRetry `
    -Method Post `
    -Uri "$ApiBaseUrl/admin/migration/$endpoint" `
    -Headers $headers `
    -Body $bundleRaw
$sw.Stop()
Write-Host ("Resposta recebida em {0:N1}s" -f $sw.Elapsed.TotalSeconds)

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outFile = Join-Path $OutDir ("migration-{0}-{1}.json" -f $endpoint, $stamp)
$response | ConvertTo-Json -Depth 20 | Set-Content -Path $outFile -Encoding UTF8
Write-Host "Resposta salva em: $outFile"

Show-MigrationSummary -Response $response

if ($response.status -ne "COMPLETED") {
    Write-Host ""
    Write-Host "Migracao nao concluida com sucesso." -ForegroundColor Red
    if (-not $DryRun) {
        Write-Host "Se houve timeout, use a opcao CLI com DATABASE_URL de producao:" -ForegroundColor Yellow
        Write-Host '  $env:DATABASE_URL = "postgresql://..."' -ForegroundColor Yellow
        Write-Host '  py backend\scripts\migrate_legacy.py --file legacy\export\bundle.json --apply' -ForegroundColor Yellow
    }
    exit 2
}

Write-Host ""
Write-Host "Migracao remota concluida com sucesso." -ForegroundColor Green
exit 0
