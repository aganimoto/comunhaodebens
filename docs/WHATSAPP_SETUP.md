# Configuração do WhatsApp

## Pré-requisitos

- Serviço `whatsapp-service` rodando (`docker compose up whatsapp-service`).
- Volume `whatsapp_session` para persistir sessão após QR.

## Primeira autenticação

1. Suba os containers: `docker compose up -d whatsapp-service`.
2. Veja os logs: `docker compose logs -f whatsapp-service`.
3. Escaneie o QR Code exibido no terminal com o WhatsApp da instituição.
4. Aguarde mensagem `Cliente WhatsApp pronto`.

## Reconexão

- Backoff exponencial: 3 tentativas, máximo 30s entre tentativas.
- Se a sessão expirar, delete o volume (último recurso) e escaneie QR novamente.

## Comportamento

- Apenas chats **privados** são processados.
- Ignorados: áudio, vídeo, figurinhas, localização, grupos.
- Imagens e PDFs são salvos em `/shared/media/`.

## Webhook

O serviço envia eventos para:

`POST http://backend:8000/api/v1/webhooks/whatsapp`

Header: `X-HMAC-Signature: sha256=<hmac_do_body>`

Secret: variável `WHATSAPP_WEBHOOK_SECRET` (mesmo valor no backend e no whatsapp-service).

## Health

`GET http://localhost:3000/health`
