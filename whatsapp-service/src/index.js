import express from "express";
import { createClient, getClient, getStatus, getQrDataUrl, clearAuthSession } from "./client.js";
import { config } from "./config.js";
import { createHealthRouter } from "./health.js";
import { registerMessageHandler } from "./handlers/message_handler.js";
import { sendMessage } from "./api/backend_client.js";

// Captura rejeições não tratadas (ex: auth timeout do Puppeteer)
process.on("unhandledRejection", (reason) => {
  const msg = reason?.message || String(reason);
  console.error("Unhandled rejection:", msg);
  if (msg.includes("auth timeout")) {
    console.error("Auth timeout detectado — limpando sessão para nova tentativa.");
    clearAuthSession();
  }
});

const app = express();
app.use(express.json());
app.use(createHealthRouter());

// ── Endpoints de QR Code / status ──────────────────────────────────
app.get("/whatsapp/status", (_req, res) => {
  const client = getClient();
  const st = getStatus();
  res.json({
    status: client ? st.status : "disconnected",
  });
});

app.get("/whatsapp/qr", (_req, res) => {
  const st = getStatus();
  if (st.status === "connected") {
    return res.json({ status: "connected", qr: null });
  }
  const qr = getQrDataUrl();
  if (!qr) {
    return res.json({ status: st.status, qr: null });
  }
  return res.json({ status: st.status, qr });
});

app.post("/whatsapp/reconnect", (_req, res) => {
  const client = getClient();
  if (!client) {
    createClient((c) => registerMessageHandler(c));
    return res.json({ ok: true, message: "Reconectando..." });
  }
  res.json({ ok: true, message: "Já conectado ou em processo" });
});

app.post("/send", async (req, res) => {
  const { telefone, mensagem } = req.body;
  if (!telefone || !mensagem) {
    return res.status(400).json({ error: "telefone e mensagem obrigatórios" });
  }
  try {
    await sendMessage(telefone, mensagem);
    res.json({ ok: true });
  } catch (e) {
    res.status(503).json({ error: e.message });
  }
});

createClient((client) => {
  registerMessageHandler(client);
});

app.listen(config.port, () => {
  console.log(`whatsapp-service na porta ${config.port}`);
});
