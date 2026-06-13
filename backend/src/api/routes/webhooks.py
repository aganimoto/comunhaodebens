import asyncio
import hashlib
import hmac
import logging
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from src.application.services.debug_logger import MODULO_WEBHOOK, get_debug_logger
from src.application.use_cases.processar_comprovante import ProcessarComprovanteUseCase
from src.config import get_settings
from src.domain.events.novo_comprovante_recebido import NovoComprovanteRecebido

logger = logging.getLogger(__name__)

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


async def _processar_comprovante_com_retry(payload: WhatsAppWebhookPayload, max_retries: int = 3) -> dict:
    """Processa o comprovante com retry em caso de falha."""
    ultimo_erro = None
    for tentativa in range(max_retries):
        try:
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
            return result
        except Exception as exc:
            ultimo_erro = exc
            logger.warning(
                "Tentativa %d/%d falhou ao processar comprovante %s: %s",
                tentativa + 1, max_retries, payload.hash_sha256[:12], exc,
            )
            if tentativa < max_retries - 1:
                await asyncio.sleep(2 ** tentativa)  # backoff exponencial: 1s, 2s, 4s

    logger.error(
        "Todas as %d tentativas falharam para comprovante %s: %s",
        max_retries, payload.hash_sha256[:12], ultimo_erro,
    )
    return {"status": "erro", "motivo": f"falha_apos_retry: {ultimo_erro}"}


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

    result = await _processar_comprovante_com_retry(payload)
    _debug.info(
        MODULO_WEBHOOK,
        "Processamento concluído",
        {"resultado": result},
    )
    return result
