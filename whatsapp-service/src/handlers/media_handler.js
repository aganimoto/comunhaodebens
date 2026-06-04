import crypto from "crypto";
import fs from "fs";
import path from "path";
import { config } from "../config.js";

export async function saveMedia(message, telefone) {
  const media = await message.downloadMedia();
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
