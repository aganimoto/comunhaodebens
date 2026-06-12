import hashlib
import hmac
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from src.application.services.debug_logger import MODULO_WEBHOOK, get_debug_logger
from src.application.services.ocr_logger import (
    ETAPA_IMAGEM_RECEBIDA,
    criar_logger,
)
from src.application.use_cases.processar_comprovante import ProcessarComprovanteUseCase
from src.config import get_settings
from src.domain.events.novo_comprovante_recebido import NovoComprovanteRecebido

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WhatsAppWebhookPayload(BaseModel):
    evento: str
    telefone: str
    whatsapp_msg_id: str
    timestamp: str
    tipo_midia: str
    caminho_arquivo: str
    hash_sha256: str
    nome_sugerido: str = ""


def _verify_hmac(body: bytes, signature: str | None) -> None:
    secret = get_settings().whatsapp_webhook_secret.encode()
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Assinatura HMAC inválida")


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    x_hmac_signature: str | None = Header(None, alias="X-HMAC-Signature"),
):
    body = await request.body()
    _verify_hmac(body, x_hmac_signature)
    payload = WhatsAppWebhookPayload.model_validate_json(body)

    if payload.evento != "NOVO_COMPROVANTE_RECEBIDO":
        return {"ignored": True}

    _debug = get_debug_logger()
    _debug.info(
        MODULO_WEBHOOK,
        "Comprovante recebido via WhatsApp",
        {
            "telefone": payload.telefone,
            "tipo_midia": payload.tipo_midia,
            "hash": payload.hash_sha256[:12] + "...",
            "nome_sugerido": payload.nome_sugerido or "(não informado)",
            "whatsapp_msg_id": payload.whatsapp_msg_id[:20],
        },
    )

    evento = NovoComprovanteRecebido(
        telefone=payload.telefone,
        whatsapp_msg_id=payload.whatsapp_msg_id,
        timestamp=datetime.fromisoformat(payload.timestamp),
        tipo_midia=payload.tipo_midia,
        caminho_arquivo=payload.caminho_arquivo,
        hash_sha256=payload.hash_sha256,
    )
    uc = ProcessarComprovanteUseCase()
    result = await uc.executar(evento)
    _debug.info(
        MODULO_WEBHOOK,
        "Processamento concluído",
        {"resultado": result},
    )
    return result
