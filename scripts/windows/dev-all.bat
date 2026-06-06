@echo off
title CDB Shalom - Iniciando Dev Environment
echo ========================================
echo   CDB Shalom - Ambiente de Desenvolvimento
echo ========================================
echo.

REM ─── Caminhos (%~dp0 = scripts/windows/ → sobe 2 níveis para raiz) ─────
set ROOT=%~dp0..\..
set BACKEND=%ROOT%\backend
set WHATSAPP=%ROOT%\whatsapp-service
set FRONTEND=%ROOT%\frontend
set MEDIA=%BACKEND%\dev_data\media

REM ─── Criar diretorios se nao existirem ─────────────────
if not exist "%MEDIA%" mkdir "%MEDIA%"
if not exist "%BACKEND%\dev_data\relatorios" mkdir "%BACKEND%\dev_data\relatorios"
if not exist "%BACKEND%\dev_data\backups" mkdir "%BACKEND%\dev_data\backups"

REM ─── Rodar migrations Alembic ──────────────────────────
if not exist "%BACKEND%\cdb_shalom.db" (
    echo [1/4] Criando banco SQLite via Alembic...
    cd /d "%BACKEND%"
    python -m alembic upgrade head
    echo Admin: admin@cdbshalom.local / TroqueEstaSenha123!
)

REM ─── Abrir terminais ───────────────────────────────────
echo [2/4] Iniciando Backend API (porta 8000)...
start "CDB-Backend" cmd /c "
    cd /d \"%BACKEND%\"
    set DEV_MODE=true
    set DATABASE_URL=sqlite+aiosqlite:///./cdb_shalom.db
    set JWT_SECRET_KEY=dev-jwt-secret-change-me-64-chars-minimum-for-hs256
    set WHATSAPP_WEBHOOK_SECRET=dev-webhook-secret-32-chars-long!!
    set CORS_ORIGINS=http://localhost:5173
    set WHATSAPP_SERVICE_URL=http://localhost:3000
    echo Backend API: http://localhost:8000
    python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
    pause
"

timeout /t 3 /nobreak >nul

echo [3/4] Iniciando WhatsApp Service (porta 3000)...
start "CDB-WhatsApp" cmd /c "
    cd /d \"%WHATSAPP%\"
    set PORT=3000
    set WHATSAPP_WEBHOOK_URL=http://localhost:8000/api/v1/webhooks/whatsapp
    set WHATSAPP_WEBHOOK_SECRET=dev-webhook-secret-32-chars-long!!
    set SHARED_MEDIA_PATH=%MEDIA%
    echo WhatsApp Service: http://localhost:3000
    node src\index.js
    pause
"

timeout /t 3 /nobreak >nul

echo [4/4] Iniciando Frontend (porta 5173)...
start "CDB-Frontend" cmd /c "
    cd /d \"%FRONTEND%\"
    echo Frontend: http://localhost:5173
    npm run dev
    pause
"

echo.
echo ========================================
echo   Todos os servicos foram iniciados!
echo   Backend:  http://localhost:8000
echo   WhatsApp: http://localhost:3000
echo   Frontend: http://localhost:5173
echo ========================================
echo.
echo Feche as janelas individuais para parar cada servico.
pause