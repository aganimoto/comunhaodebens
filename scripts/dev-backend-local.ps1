# Sobe o backend + WhatsApp service em modo dev sem Docker.
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Backend = Join-Path $Root "backend"
$WhatsappService = Join-Path $Root "whatsapp-service"
$DbPath = Join-Path (Join-Path $Backend "dev_data") "local.db"
$MediaPath = Join-Path (Join-Path $Backend "dev_data") "media"

# ── Variáveis de ambiente do backend ──────────────────────────────────
$env:DEV_MODE = "true"
$env:DEV_USE_REAL_SHEETS = "true"
$env:DATABASE_URL = "sqlite+aiosqlite:///$($DbPath -replace '\\','/')"
$env:JWT_SECRET_KEY = "dev-jwt-secret-change-me-64-chars-minimum-for-hs256"
$env:WHATSAPP_WEBHOOK_SECRET = "dev-webhook-secret-32-chars-long!!"
$env:DEV_RELATORIOS_PATH = Join-Path (Join-Path $Backend "dev_data") "relatorios"
$env:DEV_BACKUP_PATH = Join-Path (Join-Path $Backend "dev_data") "backups"
$env:CORS_ORIGINS = "http://localhost:5173"
$env:WHATSAPP_SERVICE_URL = "http://localhost:3000"
$env:SHARED_MEDIA_PATH = $MediaPath

# ── Cria diretórios necessários ──────────────────────────────────────
New-Item -ItemType Directory -Path $MediaPath -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Backend "dev_data\relatorios") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Backend "dev_data\backups") -Force | Out-Null

# ── Bootstrap do banco SQLite ─────────────────────────────────────────
if (-not (Test-Path $DbPath)) {
    Write-Host "Criando banco SQLite local..."
    Set-Location $Backend
    python scripts/bootstrap_local_db.py
    python scripts/create_admin.py
    Write-Host "Admin: admin@cdbshalom.local / TroqueEstaSenha123!"
}

# ── Inicia WhatsApp service em background ─────────────────────────────
$whatsappLog = Join-Path $Backend "dev_data\whatsapp-service.log"
Write-Host "Iniciando WhatsApp service na porta 3000..."
$env:PORT = "3000"
$env:SHARED_MEDIA_PATH = $MediaPath
$env:WHATSAPP_WEBHOOK_URL = "http://localhost:8000/api/v1/webhooks/whatsapp"
$env:WHATSAPP_WEBHOOK_SECRET = "dev-webhook-secret-32-chars-long!!"

if (Test-Path (Join-Path $WhatsappService "node_modules")) {
    Start-Process -FilePath "node" -ArgumentList "src/index.js" `
        -WorkingDirectory $WhatsappService `
        -RedirectStandardOutput $whatsappLog `
        -RedirectStandardError (Join-Path $Backend "dev_data\whatsapp-service-err.log") `
        -NoNewWindow -PassThru | Select-Object -First 1
    Write-Host "WhatsApp service log: $whatsappLog"
} else {
    Write-Host "AVISO: node_modules não encontrado em whatsapp-service/. Execute 'npm install' em whatsapp-service/ primeiro."
    Write-Host "  cd whatsapp-service && npm install"
}

# ── Inicia o backend ──────────────────────────────────────────────────
Set-Location $Backend
Write-Host ""
Write-Host "========================================"
Write-Host "  Backend API: http://localhost:8000"
Write-Host "  WhatsApp:    http://localhost:3000"
Write-Host "  DEV_MODE=true"
Write-Host "========================================"
Write-Host ""
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload