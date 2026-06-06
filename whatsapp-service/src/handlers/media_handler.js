import crypto from "crypto";
import fs from "fs";
import path from "path";
import { config } from "../config.js";

/**
 * Tenta baixar a mídia com retry, pois o contexto do Puppeteer pode ser
 * destruído durante reconexão do WhatsApp Web.
 */
async function downloadWithRetry(message, maxRetries = 3, delayMs = 2000) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const media = await message.downloadMedia();
      if (media) return media;
      return null;
    } catch (err) {
      const isContextDestroyed =
        err.message?.includes("Execution context was destroyed") ||
        err.message?.includes("Protocol error") ||
        err.message?.includes("Target closed");

      if (isContextDestroyed && attempt < maxRetries) {
        console.log(
          `Contexto destruído ao baixar mídia (tentativa ${attempt}/${maxRetries}), aguardando ${delayMs}ms...`
        );
        await new Promise((r) => setTimeout(r, delayMs));
        delayMs *= 2; // backoff exponencial
        continue;
      }

      if (err.message?.includes("auth timeout")) {
        console.error("Auth timeout ao baixar mídia — sessão expirou.");
        return null;
      }

      throw err;
    }
  }
  return null;
}

export async function saveMedia(message, telefone) {
  const media = await downloadWithRetry(message);
  if (!media) return null;

  const ext = media.mimetype?.includes("pdf") ? "pdf" : "jpg";
  const now = new Date();
  const stamp = now.toISOString().replace(/[-:T]/g, "").slice(0, 15);
  const filename = `${telefone}_${stamp}.${ext}`;
  const dir = config.sharedMediaPath;

  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  const filepath = path.join(dir, filename);
  const buffer = Buffer.from(media.data, "base64");
  fs.writeFileSync(filepath, buffer);
  const hash = crypto.createHash("sha256").update(buffer).digest("hex");

  return { filepath, hash, ext };
}
