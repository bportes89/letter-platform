# Apply local da migracao (banco configurado no backend / DATABASE_URL)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
py backend\scripts\migrate_legacy.py --file legacy\export\bundle.json --apply @args
exit $LASTEXITCODE
