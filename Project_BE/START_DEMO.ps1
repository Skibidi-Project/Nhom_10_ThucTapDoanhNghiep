$ErrorActionPreference = 'Stop'
$Python = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\.venv\Scripts\python.exe'))
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Không tìm thấy .venv.' }
$tempDir = [System.IO.Path]::GetFullPath($env:TEMP)
$demoDb = [System.IO.Path]::GetFullPath((Join-Path $tempDir 'ministay_us25_us27_demo.sqlite3'))
if ([System.IO.Path]::GetDirectoryName($demoDb) -ne $tempDir) { throw 'Đường dẫn demo không hợp lệ.' }
$env:DATABASE_URL = 'sqlite:///' + $demoDb.Replace('\','/')
$env:PYTHONDONTWRITEBYTECODE = '1'; $env:PYTHONIOENCODING = 'utf-8'
$rng=[System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $bytes=New-Object byte[] 48; $rng.GetBytes($bytes); $env:JWT_SECRET=[Convert]::ToBase64String($bytes) } finally { $rng.Dispose() }
Push-Location $PSScriptRoot
try {
    & $Python (Join-Path $PSScriptRoot 'demo_setup.py')
    if ($LASTEXITCODE -ne 0) { throw 'Không thể chuẩn bị schema demo.' }
    Write-Host 'Đăng nhập: http://127.0.0.1:8025/register/login.html'
    Write-Host 'API docs: http://127.0.0.1:8025/docs'
    & $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8025
} finally { Pop-Location }
