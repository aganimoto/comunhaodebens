import { notifyBackend } from "../api/backend_client.js";
import { saveMedia } from "./media_handler.js";

const IGNORED_TYPES = ["audio", "video", "sticker", "location", "ptt", "call_log"];

/**
 * Extrai o número de telefone real de uma mensagem.
 * WhatsApp pode retornar IDs internos longos para contatos não salvos.
 * Telefones brasileiros reais têm entre 10 e 13 dígitos (ex: 5561999999999).
 */
async function extractPhone(message) {
  // Telefones reais brasileiros têm entre 10 e 13 dígitos (ex: 556198400658)
  // WhatsApp Business API pode retornar IDs internos de 15 dígitos no message.from
  // Formato antigo: 556198400658@c.us  |  Novo formato: 176780971343939@lid

  // Estratégia 1: contact.id.user (mais confiável para novos formatos)
  try {
    const contact = await message.getContact();
    const idUser = (contact.id?.user || "").replace(/\D/g, "");
    console.log("Contact info - number:", contact.number, "id.user:", contact.id?.user, "pushname:", contact.pushname);
    if (idUser.length >= 10 && idUser.length <= 13) {
      return idUser;
    }
  } catch (err) {
    console.log("Erro ao obter contato:", err.message);
  }

  // Estratégia 2: extrair dígitos do message.from (formato antigo: 556198400658@c.us)
  const rawFrom = message.from.split("@")[0];
  const digitsFrom = rawFrom.replace(/\D/g, "");
  if (digitsFrom.length >= 10 && digitsFrom.length <= 13) {
    return digitsFrom;
  }

  // Estratégia 3: contact.number (pode funcionar em alguns casos)
  try {
    const contact = await message.getContact();
    const contactNumber = (contact.number || "").replace(/\D/g, "");
    if (contactNumber.length >= 10 && contactNumber.length <= 13) {
      return contactNumber;
    }
  } catch (err) {
    console.log("Erro ao obter contact.number:", err.message);
  }

  console.error(
    "Número inválido/indisponível - from:", message.from,
    "id.user do contato tem", (await message.getContact()).id?.user || "N/A",
    "(IDs com 15+ dígitos = WhatsApp interno, não telefone real)"
  );
  return null;
}

export function registerMessageHandler(client) {
  client.on("message", async (message) => {
    try {
      // Ignorar mensagens de grupos e do próprio número
      if (message.from.includes("@g.us")) return;
      if (message.fromMe) return;

      const chat = await message.getChat();
      if (chat.isGroup) return;

      // Ignorar tipos não suportados
      if (IGNORED_TYPES.includes(message.type)) return;

      // Extrair telefone (com validação de tamanho)
      const telefone = await extractPhone(message);
      if (!telefone) return;

      console.log("Mensagem recebida - from:", message.from, "telefone:", telefone, "tipo:", message.type, "hasMedia:", message.hasMedia);

      // Processar apenas mídia (imagem ou documento)
      if (!message.hasMedia) {
        console.log("Mensagem sem mídia, ignorando:", message.type, "de:", telefone);
        return;
      }

      if (message.type !== "image" && message.type !== "document") {
        console.log("Tipo de mídia não suportado:", message.type, "de:", telefone);
        return;
      }

      const saved = await saveMedia(message, telefone);
      if (!saved) {
        console.error("Falha ao salvar mídia para:", telefone);
        return;
      }

      // Formata como E.164 (+55 + DDD + número)
      const telefoneFormatado = "+" + (telefone.startsWith("55") ? telefone : "55" + telefone);

      const payload = {
        evento: "NOVO_COMPROVANTE_RECEBIDO",
        telefone: telefoneFormatado,
        whatsapp_msg_id: message.id._serialized || message.id,
        timestamp: new Date().toISOString(),
        tipo_midia: saved.ext === "pdf" ? "documento" : "imagem",
        caminho_arquivo: saved.filepath,
        hash_sha256: saved.hash,
      };

      console.log("Enviando webhook para backend:", payload.evento, payload.telefone, "msg_id:", payload.whatsapp_msg_id);
      await notifyBackend(payload);
      console.log("Webhook enviado com sucesso para:", payload.telefone);
    } catch (err) {
      console.error("Erro ao processar mensagem:", err.message);
      console.error(err.stack);
    }
  });
}