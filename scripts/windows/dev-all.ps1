# CDB Shalom - Dev Environment (PowerShell)
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CDB Shalom - Ambiente de Desenvolvimento" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# (Split-Path = scripts/windows/ → sobe 2 níveis para raiz)
$ROOT = Resolve-Path "$PSScriptRoot\..\.."
$BACKEND = Join-Path $ROOT "backend"
$FRONTEND = Join-Path $ROOT "frontend"
$WHATSAPP = Join-Path $ROOT "whatsapp-service"
$DB = Join-Path $BACKEND "dev_data\local.db"
$MEDIA = Join-Path $BACKEND "dev_data\media"

# Criar diretórios
foreach ($dir in @($MEDIA, "$BACKEND\dev_data\relatorios", "$BACKEND\dev_data\backups")) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
}

# Bootstrap do banco SQLite
if (-not (Test-Path $DB)) {
    Write-Host "[1/3] Criando banco SQLite..." -ForegroundColor Yellow
    Push-Location $BACKEND
    python scripts/bootstrap_local_db.py
    python scripts/create_admin.py
    Pop-Location
    Write-Host "  Admin: admin@cdbshalom.local / TroqueEstaSenha123!" -ForegroundColor Green
}

Write-Host "[1/3] Iniciando Backend API (porta 8000)..." -ForegroundColor Yellow
$jobBackend = Start-Job -Name "CDB-Backend" -ScriptBlock {
    param($BACKEND, $DB, $ROOT)
    Set-Location $BACKEND
    $env:DEV_MODE = "true"
    $env:DATABASE_URL = "sqlite+aiosqlite:///$($DB.Replace('\','/'))"
    $env:JWT_SECRET_KEY = "dev-jwt-secret-change-me-64-chars-minimum-for-hs256"
    $env:WHATSAPP_WEBHOOK_SECRET = "dev-webhook-secret-32-chars-long!!"
    $env:CORS_ORIGINS = "http://localhost:5173"
    $env:WHATSAPP_SERVICE_URL = "http://localhost:3000"
    $env:GOOGLE_SERVICE_ACCOUNT_JSON = "$ROOT\scripts\google_sa.json"
    $env:CELERY_BROKER_URL = ""
    $env:CELERY_RESULT_BACKEND = ""
    Write-Host "  Backend API: http://localhost:8000" -ForegroundColor Green
    python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
} -ArgumentList $BACKEND, $DB, $ROOT

Start-Sleep -Seconds 3

Write-Host "[2/3] Iniciando Frontend (porta 5173)..." -ForegroundColor Yellow
$jobFrontend = Start-Job -Name "CDB-Frontend" -ScriptBlock {
    param($FRONTEND)
    Set-Location $FRONTEND
    Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Green
    npm run dev
} -ArgumentList $FRONTEND

Start-Sleep -Seconds 2

Write-Host "[3/3] Iniciando WhatsApp Service (porta 3000)..." -ForegroundColor Yellow
$jobWhatsApp = Start-Job -Name "CDB-WhatsApp" -ScriptBlock {
    param($WHATSAPP, $MEDIA)
    Set-Location $WHATSAPP
    $env:PORT = "3000"
    $env:WHATSAPP_WEBHOOK_URL = "http://localhost:8000/api/v1/webhooks/whatsapp"
    $env:WHATSAPP_WEBHOOK_SECRET = "dev-webhook-secret-32-chars-long!!"
    $env:SHARED_MEDIA_PATH = $MEDIA
    node src\index.js
} -ArgumentList $WHATSAPP, $MEDIA

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Todos os servicos foram iniciados!" -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "  WhatsApp: http://localhost:3000" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nPressione Ctrl+C para parar todos os servicos.`n"

# Manter script rodando
while ($true) {
    Start-Sleep -Seconds 10
    # Verificar se os jobs estão rodando
    $jobs = Get-Job -State Running
    if ($jobs.Count -eq 0) {
        Write-Host "Todos os servicos pararam." -ForegroundColor Red
        break
    }
}