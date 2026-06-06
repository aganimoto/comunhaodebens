@echo off
title CDB-Frontend - Vite (porta 5173)
echo ========================================
echo   CDB Shalom - Frontend
echo ========================================
echo.

REM (%~dp0 = scripts/windows/ → sobe 2 níveis para raiz)
set ROOT=%~dp0..\..
set FRONTEND=%ROOT%\frontend

REM ─── Iniciar servidor de desenvolvimento ──────────────
echo Iniciando Frontend (porta 5173)...
cd /d "%FRONTEND%"

echo Frontend: http://localhost:5173
echo.
npm run dev

if errorlevel 1 (
    echo.
    echo Erro ao iniciar o Frontend. Verifique as mensagens acima.
    pause
)