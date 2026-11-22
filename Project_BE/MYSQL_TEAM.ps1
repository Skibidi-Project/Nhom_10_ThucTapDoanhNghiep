param([ValidateSet('check','preflight','migrate','start')][string]$Action = 'check')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not $env:DATABASE_URL) { throw 'Set DATABASE_URL to the intended MySQL database first.' }
$db = Read-Host 'Enter exact target database name'
if (-not $db) { throw 'A target database name is required.' }
python migrations/inspect_mysql_schema.py $db
if ($LASTEXITCODE -ne 0) { throw 'Connection or target validation failed.' }
if ($Action -eq 'check') { exit 0 }
if ($Action -eq 'preflight' -or $Action -eq 'migrate') {
    python migrations/apply_mysql_migrations.py --confirm-database $db
    if ($LASTEXITCODE -ne 0) { throw 'Preflight failed; do not execute migration.' }
}
if ($Action -eq 'migrate') {
    Write-Host 'MySQL DDL commits implicitly. Verify a backup by restoring it elsewhere; see MYSQL_SETUP.md.'
    if ((Read-Host 'Type BACKUP VERIFIED') -cne 'BACKUP VERIFIED') { throw 'Stopped: backup not confirmed.' }
    if ((Read-Host 'Type MANAGER APPROVED') -cne 'MANAGER APPROVED') { throw 'Stopped: approval not confirmed.' }
    if ((Read-Host "Type the exact database name again to change schema ($db)") -cne $db) { throw 'Stopped: database not confirmed.' }
    python migrations/apply_mysql_migrations.py --confirm-database $db --execute
    if ($LASTEXITCODE -ne 0) { throw 'Migration failed. Stop and investigate partial DDL; do not blindly retry.' }
}
if ($Action -eq 'start') {
    Write-Host 'Starting backend. Login: http://127.0.0.1:8000/register/login.html'
    Write-Host 'A successful startup displays Application startup complete. Stop with Ctrl+C.'
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    if ($LASTEXITCODE -ne 0) { throw 'Backend failed to start.' }
}
