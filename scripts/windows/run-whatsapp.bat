@echo off
REM Executa o WhatsApp Service diretamente (%~dp0 = scripts/windows/ → sobe 2 para raiz)
set ROOT=%~dp0..\..
set BACKEND=%ROOT%\backend

cd /d "%ROOT%\whatsapp-service"
set PORT=3000
set WHATSAPP_WEBHOOK_URL=http://localhost:8000/api/v1/webhooks/whatsapp
set WHATSAPP_WEBHOOK_SECRET=dev-webhook-secret-32-chars-long!!
set SHARED_MEDIA_PATH=%BACKEND%\dev_data\media

echo WhatsApp Service: http://localhost:3000
node src/index.js