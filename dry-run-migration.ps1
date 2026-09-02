# Dry-run da migracao usando legacy/export/bundle.json
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
py backend\scripts\migrate_legacy.py --file legacy\export\bundle.json --dry-run @args
exit $LASTEXITCODE
