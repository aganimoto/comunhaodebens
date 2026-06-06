@echo off
REM Uso direto: executa o backend sem o roteiro completo do dev-all
REM (%~dp0 = scripts/windows/ → sobe 2 níveis para a raiz)
set ROOT=%~dp0..\..
set BACKEND=%ROOT%\backend

cd /d "%BACKEND%"
set DATABASE_URL=sqlite+aiosqlite:///./cdb_shalom.db
set JWT_SECRET_KEY=dev-jwt-secret-change-me-64-chars-minimum-for-hs256
set WHATSAPP_WEBHOOK_SECRET=dev-webhook-secret-32-chars-long!!
set CORS_ORIGINS=http://localhost:5173
set WHATSAPP_SERVICE_URL=http://localhost:3000
set PYTHONPATH=%BACKEND%

echo Backend API: http://localhost:8000
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
