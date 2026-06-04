# Script para iniciar os 3 serviços em terminais separados
# Encoding: UTF-8
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CDB Shalom - Abrindo servicos..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$batPath = Join-Path $PSScriptRoot "start-backend.bat"
$batWhats = Join-Path $PSScriptRoot "start-whatsapp.bat"
$batFront = Join-Path $PSScriptRoot "start-frontend.bat"

Write-Host "[1/3] Abrindo Backend API (porta 8000)..." -ForegroundColor Yellow
cmd.exe /c "start `"CDB-Backend`" cmd /c `"$batPath`""

Start-Sleep -Seconds 3

Write-Host "[2/3] Abrindo WhatsApp Service (porta 3000)..." -ForegroundColor Yellow
cmd.exe /c "start `"CDB-WhatsApp`" cmd /c `"$batWhats`""

Start-Sleep -Seconds 3

Write-Host "[3/3] Abrindo Frontend (porta 5173)..." -ForegroundColor Yellow
cmd.exe /c "start `"CDB-Frontend`" cmd /c `"$batFront`""

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Todos os servicos foram iniciados!" -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "  WhatsApp: http://localhost:3000" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
