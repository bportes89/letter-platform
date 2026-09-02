# Exporta legacy/letter_banco_new.sql -> legacy/export/bundle.json
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
py backend\scripts\export_legacy_v1.py @args
exit $LASTEXITCODE
