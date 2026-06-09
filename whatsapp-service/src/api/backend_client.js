import crypto from "crypto";
import axios from "axios";
import { config } from "../config.js";

export async function notifyBackend(payload) {
  const body = JSON.stringify(payload);
  const signature =
    "sha256=" +
    crypto
      .createHmac("sha256", config.webhookSecret)
      .update(body)
      .digest("hex");

  const response = await axios.post(config.webhookUrl, body, {
    headers: {
      "Content-Type": "application/json",
      "X-HMAC-Signature": signature,
    },
    timeout: 120000,
  });
  return response.data;
}

export async function sendMessage(telefone, mensagem) {
  const { getClient } = await import("../client.js");
  const client = getClient();
  if (!client) throw new Error("WhatsApp não conectado");
  const chatId = `${telefone}@c.us`;
  await client.sendMessage(chatId, mensagem);
  return { ok: true };
}
