export const config = {
  port: parseInt(process.env.PORT || "3000", 10),
  webhookUrl:
    process.env.WHATSAPP_WEBHOOK_URL ||
    "http://backend:8000/api/v1/webhooks/whatsapp",
  webhookSecret: process.env.WHATSAPP_WEBHOOK_SECRET || "dev-secret-change-me",
  sharedMediaPath: process.env.SHARED_MEDIA_PATH || "/shared/media",
  maxReconnectAttempts: 3,
  maxReconnectDelayMs: 30000,
};
