@echo off
title CDB Shalom - Iniciando Dev Environment
echo ========================================
echo   CDB Shalom - Ambiente de Desenvolvimento
echo ========================================
echo.

REM ─── Caminhos ──────────────────────────────────────────
set ROOT=%~dp0
set BACKEND=%ROOT%backend
set WHATSAPP=%ROOT%whatsapp-service
set FRONTEND=%ROOT%frontend
set MEDIA=%BACKEND%\dev_data\media
set DB=%BACKEND%\dev_data\local.db

REM ─── Criar diretorios se nao existirem ─────────────────
if not exist "%MEDIA%" mkdir "%MEDIA%"
if not exist "%BACKEND%\dev_data\relatorios" mkdir "%BACKEND%\dev_data\relatorios"
if not exist "%BACKEND%\dev_data\backups" mkdir "%BACKEND%\dev_data\backups"

REM ─── Bootstrap do banco SQLite ─────────────────────────
if not exist "%DB%" (
    echo [1/5] Criando banco SQLite...
    cd /d "%BACKEND%"
    python scripts\bootstrap_local_db.py
    python scripts\create_admin.py
    echo Admin: admin@cdbshalom.local / TroqueEstaSenha123!
)

REM ─── Abrir terminais ───────────────────────────────────
echo [2/5] Iniciando Backend API (porta 8000)...
start "CDB-Backend" cmd /c "
    cd /d "%BACKEND%"
    set DEV_MODE=true
    set DATABASE_URL=sqlite+aiosqlite:///%DB:\=/%
    set JWT_SECRET_KEY=dev-jwt-secret-change-me-64-chars-minimum-for-hs256
    set WHATSAPP_WEBHOOK_SECRET=dev-webhook-secret-32-chars-long!!
    set CORS_ORIGINS=http://localhost:5173
    set WHATSAPP_SERVICE_URL=http://localhost:3000
    set GOOGLE_SERVICE_ACCOUNT_JSON=%ROOT%scripts\google_sa.json
    echo Backend API: http://localhost:8000
    python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
    pause
"

timeout /t 2 /nobreak >nul

echo [3/5] Iniciando Celery Worker...
start "CDB-Celery-Worker" cmd /c "
    cd /d %BACKEND%
    set DEV_MODE=true
    set DATABASE_URL=sqlite+aiosqlite:///%DB:\=/%
    set JWT_SECRET_KEY=dev-jwt-secret-change-me-64-chars-minimum-for-hs256
    set WHATSAPP_WEBHOOK_SECRET=dev-webhook-secret-32-chars-long!!
    set GOOGLE_SERVICE_ACCOUNT_JSON=%ROOT%scripts\google_sa.json
    set SHARED_MEDIA_PATH=%MEDIA%
    echo Celery Worker iniciado.
    python -m celery -A src.tasks.celery_app worker --loglevel=info --pool=solo
    pause
"

timeout /t 2 /nobreak >nul

echo [4/5] Iniciando WhatsApp Service (porta 3000)...
start "CDB-WhatsApp" cmd /c "
    cd /d "%WHATSAPP%"
    set PORT=3000
    set WHATSAPP_WEBHOOK_URL=http://localhost:8000/api/v1/webhooks/whatsapp
    set WHATSAPP_WEBHOOK_SECRET=dev-webhook-secret-32-chars-long!!
    set SHARED_MEDIA_PATH=%MEDIA%
    echo WhatsApp Service: http://localhost:3000
    node src\index.js
    pause
"

timeout /t 2 /nobreak >nul

echo [5/5] Iniciando Frontend (porta 5173)...
start "CDB-Frontend" cmd /c "
    cd /d "%FRONTEND%"
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