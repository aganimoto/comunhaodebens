# WhatsApp Service — Configuração

Serviço Node.js que gerencia a conexão com WhatsApp Web e reencaminha mensagens para o backend.

---

## 1. Pré-requisitos

- **Node.js** ≥ 18
- **npm** ≥ 9
- **Chrome/Chromium** (para WhatsApp Web)

---

## 2. Instalação

```bash
cd whatsapp-service
npm install
```

---

## 3. Variáveis de ambiente

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `PORT` | Porta do serviço | `3000` |
| `BACKEND_URL` | URL do backend FastAPI | `http://localhost:8000` |
| `WEBHOOK_SECRET` | Segredo para validação HMAC | `dev-secret-change-me` |
| `MEDIA_PATH` | Caminho para salvar mídia | `./media` |

---

## 4. Iniciar

```bash
cd whatsapp-service
npm start
```

> O serviço rodará em **http://localhost:3000**.

---

## 5. Conectar WhatsApp

1. Ao iniciar, o serviço gera um **QR Code** no terminal
2. Abra o WhatsApp no celular
3. Vá em **Dispositivos conectados** → **Conectar dispositivo**
4. Escaneie o QR Code exibido no terminal
5. Após conectar, a sessão é mantida (não precisa reconectar)

---

## 6. Fluxo de mensagens

```
Membro envia imagem → WhatsApp Web → whatsapp-service
                                          │
                                          ▼
                                   POST /api/v1/webhooks/whatsapp
                                   (com HMAC signature)
                                          │
                                          ▼
                                    Backend FastAPI
                                          │
                                          ▼
                                    Processamento OCR
                                          │
                                          ▼
                                    Google Sheets
```

---

## 7. Webhook

O serviço envia mensagens para o backend via webhook:

```
POST http://localhost:8000/api/v1/webhooks/whatsapp

Headers:
  Content-Type: application/json
  X-Webhook-Signature: HMAC-SHA256(secret, body)

Body:
{
  "from": "5511999998888",
  "type": "image",
  "mediaUrl": "http://localhost:3000/media/abc123.jpg",
  "timestamp": "2026-06-12T15:30:00Z"
}
```

---

## 8. Mídia

- Imagens recebidas são salvas em `whatsapp-service/media/`
- O backend acessa as imagens via URL: `http://localhost:3000/media/{filename}`
- Em Docker, a mídia é compartilhada via volume: `shared/media/`

---

## 9. Reconexão

- A sessão WhatsApp Web é persistida em `.wwebjs_auth/`
- Se a conexão cair, o serviço tenta reconectar automaticamente
- Se a sessão expirar, limpe `.wwebjs_auth/` e reconecte

```bash
# Limpar sessão (Windows)
rmdir /s /q whatsapp-service\.wwebjs_auth

# Limpar sessão (Linux/Mac)
rm -rf whatsapp-service/.wwebjs_auth
```

---

## 10. Docker

```bash
# Iniciar apenas o WhatsApp Service
docker compose up whatsapp-service

# Ver logs
docker compose logs -f whatsapp-service
```

---

## 11. Problemas comuns

| Problema | Causa | Solução |
|----------|-------|---------|
| QR Code não aparece | Chrome não encontrado | Instale Chrome ou configure `CHROME_BIN` |
| `auth timeout` | Sessão expirou | Limpe `.wwebjs_auth/` e reconecte |
| `Execution context destroyed` | Reconexão | Aguarde reconexão automática (3x) |
| `ECONNREFUSED` | Backend não está rodando | Inicie o backend primeiro |
| Mensagens não chegam | Webhook falhou | Verifique `BACKEND_URL` e `WEBHOOK_SECRET` |
| `rate-limited` | Muitas mensagens | Aguarde 1 minuto |

---

## 12. Segurança

- **HMAC Signature**: Todas as mensagens enviadas ao backend são assinadas com HMAC-SHA256
- **WEBHOOK_SECRET**: Mantenha este valor secreto e diferente em produção
- **Idempotência**: O backend processa cada mensagem apenas uma vez (hash SHA256)