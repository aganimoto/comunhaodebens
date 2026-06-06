@echo off
REM Executa o frontend diretamente (%~dp0 = scripts/windows/ → sobe 2 para raiz)
set ROOT=%~dp0..\..
cd /d "%ROOT%\frontend"
echo Frontend: http://localhost:5173
npm run dev