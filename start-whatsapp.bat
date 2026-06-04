@echo off
title CDB-WhatsApp - Service (porta 3000)
echo ========================================
echo   CDB Shalom - WhatsApp Service
echo ========================================
echo.

set ROOT=%~dp0
set WHATSAPP=%ROOT%whatsapp-service
set BACKEND=%ROOT%backend
set MEDIA=%BACKEND%\dev_data\media

REM ─── Criar diretorio de midia se nao existir ──────────
if not exist "%MEDIA%" mkdir "%MEDIA%"

REM ─── Iniciar servidor ──────────────────────────────────
echo Iniciando WhatsApp Service (porta 3000)...
cd /d "%WHATSAPP%"
set PORT=3000
set WHATSAPP_WEBHOOK_URL=http://localhost:8000/api/v1/webhooks/whatsapp
set WHATSAPP_WEBHOOK_SECRET=dev-webhook-secret-32-chars-long!!
set SHARED_MEDIA_PATH=%MEDIA%

echo WhatsApp Service: http://localhost:3000
echo.
node src\index.js

if errorlevel 1 (
    echo.
    echo Erro ao iniciar o WhatsApp Service. Verifique as mensagens acima.
    pause
)