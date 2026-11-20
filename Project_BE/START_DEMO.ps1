$ErrorActionPreference = 'Stop'
$ProjectDir = $PSScriptRoot
$Python = [System.IO.Path]::GetFullPath((Join-Path $ProjectDir '..\..\.venv\Scripts\python.exe'))
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Không tìm thấy Python trong .venv.' }
$TempDir = [System.IO.Path]::GetFullPath($env:TEMP)
$DemoDb = [System.IO.Path]::GetFullPath((Join-Path $TempDir 'ministay_business_e2e_manual_demo.sqlite3'))
if ([System.IO.Path]::GetDirectoryName($DemoDb) -ne $TempDir) { throw 'Đường dẫn database demo không hợp lệ.' }
$env:DATABASE_URL = 'sqlite:///' + $DemoDb.Replace('\','/')
$env:MINISTAY_US16_TRIAL = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONIOENCODING = 'utf-8'
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $bytes = New-Object byte[] 48; $rng.GetBytes($bytes); $env:JWT_SECRET = [Convert]::ToBase64String($bytes) }
finally { $rng.Dispose() }
Push-Location $ProjectDir
try {
    & $Python (Join-Path $ProjectDir 'demo_setup.py')
    if ($LASTEXITCODE -ne 0) { throw 'Không thể chuẩn bị database demo; không khởi động server.' }
    Write-Host 'Đăng nhập: http://127.0.0.1:8016/register/login.html'
    & $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8016
} finally { Pop-Location }
