import { rmSync } from "fs";
import qrcode from "qrcode-terminal";
import qrcodeImg from "qrcode";
import whatsapp from "whatsapp-web.js";
import { config } from "./config.js";

const { Client, LocalAuth } = whatsapp;

let clientInstance = null;
let reconnectAttempt = 0;

/** Estado compartilhado para a API */
let connectionState = "disconnected"; // disconnected | qr_pending | connected
let qrDataUrl = null;

export function getClient() {
  return clientInstance;
}

export function getStatus() {
  return { status: connectionState };
}

export function getQrDataUrl() {
  return qrDataUrl;
}

export function clearAuthSession() {
  try {
    rmSync(".wwebjs_auth", { recursive: true, force: true });
    console.log("Sessão de autenticação limpa.");
  } catch {
    // ignora se não existir
  }
}

export function createClient(onReady) {
  const client = new Client({
    authStrategy: new LocalAuth({ dataPath: ".wwebjs_auth" }),
    puppeteer: {
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH,
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
    },
  });

  client.on("qr", async (qr) => {
    console.log("Escaneie o QR Code:");
    qrcode.generate(qr, { small: true });
    connectionState = "qr_pending";
    try {
      qrDataUrl = await qrcodeImg.toDataURL(qr);
    } catch {
      qrDataUrl = null;
    }
  });

  client.on("ready", () => {
    console.log("Cliente WhatsApp pronto");
    connectionState = "connected";
    qrDataUrl = null;
    reconnectAttempt = 0;
    onReady?.(client);
  });

  client.on("authenticated", () => {
    connectionState = "connected";
    qrDataUrl = null;
  });

  client.on("auth_failure", (msg) => {
    console.error("Falha de autenticação:", msg);
    connectionState = "disconnected";
    qrDataUrl = null;
    clearAuthSession();
    scheduleReconnect(onReady);
  });

  client.on("disconnected", (reason) => {
    console.log("WhatsApp desconectado, motivo:", reason);
    connectionState = "disconnected";
    qrDataUrl = null;
    // Se foi um logout, limpa sessão
    if (reason === "LOGOUT") {
      clearAuthSession();
    }
    scheduleReconnect(onReady);
  });

  client.initialize();
  clientInstance = client;
  return client;
}

function scheduleReconnect(onReady) {
  if (reconnectAttempt >= config.maxReconnectAttempts) {
    console.error("Máximo de tentativas de reconexão atingido");
    return;
  }
  reconnectAttempt += 1;
  const delay = Math.min(
    1000 * 2 ** reconnectAttempt,
    config.maxReconnectDelayMs
  );
  setTimeout(() => {
    console.log(`Reconectando (tentativa ${reconnectAttempt})...`);
    createClient(onReady);
  }, delay);
}
