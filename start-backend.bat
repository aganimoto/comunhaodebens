@echo off
title CDB-Backend - API (porta 8000)
echo ========================================
echo   CDB Shalom - Backend API
echo ========================================
echo.

set ROOT=%~dp0
set BACKEND=%ROOT%backend
set MEDIA=%BACKEND%\dev_data\media
set DB=%BACKEND%\dev_data\local.db

REM ─── Criar diretorios se nao existirem ─────────────────
if not exist "%MEDIA%" mkdir "%MEDIA%"
if not exist "%BACKEND%\dev_data\relatorios" mkdir "%BACKEND%\dev_data\relatorios"
if not exist "%BACKEND%\dev_data\backups" mkdir "%BACKEND%\dev_data\backups"

REM ─── Bootstrap do banco SQLite ─────────────────────────
if not exist "%DB%" (
    echo [1/2] Criando banco SQLite...
    cd /d "%BACKEND%"
    python scripts\bootstrap_local_db.py
    python scripts\create_admin.py
    echo Admin: admin@cdbshalom.local / TroqueEstaSenha123!
)

REM ─── Iniciar servidor ──────────────────────────────────
echo [2/2] Iniciando Backend API (porta 8000) e Celery Worker...
cd /d "%BACKEND%"

set DEV_MODE=true
set DATABASE_URL=sqlite+aiosqlite:///%DB:\=/%
set JWT_SECRET_KEY=dev-jwt-secret-change-me-64-chars-minimum-for-hs256
set WHATSAPP_WEBHOOK_SECRET=dev-webhook-secret-32-chars-long!!
set CORS_ORIGINS=http://localhost:5173
set WHATSAPP_SERVICE_URL=http://localhost:3000
set GOOGLE_SERVICE_ACCOUNT_JSON=%ROOT%scripts\google_sa.json

echo Backend API: http://localhost:8000
echo.

REM Inicia o Celery Worker em janela separada (usando python -m celery no Windows)
start "CDB-Celery-Worker" cmd /c "
    cd /d \"%BACKEND%\"
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

echo Celery Worker iniciado em janela separada.
echo.
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

if errorlevel 1 (
    echo.
    echo Erro ao iniciar o servidor. Verifique as mensagens acima.
    pause
)