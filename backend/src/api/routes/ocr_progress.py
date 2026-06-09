"""Endpoint SSE (Server-Sent Events) para acompanhar progresso do OCR em tempo real.

O frontend chama:
    GET /ocr-progress/{identificador}

E recebe eventos como:
    data: {"identificador":"...","etapa":"📥 Imagem recebida","status":"andamento","progresso":0.1}

Quando o OCR conclui, o evento final tem status "concluido" e progresso 1.0.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.application.services.ocr_logger import obter_logger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ocr-progress", tags=["ocr-progress"])


def _sse_payload(event: str, data: str) -> str:
    """Formata uma mensagem SSE."""
    return f"event: {event}\ndata: {data}\n\n"


@router.get("/{identificador}")
async def stream_ocr_progress(identificador: str):
    """SSE endpoint: stream do progresso do OCR em tempo real.

    O cliente deve conectar com o identificador retornado pelo webhook
    (hash_sha256 da imagem). Os eventos são enviados conforme as etapas
    são concluídas. Quando o status for "concluido", a conexão é encerrada.
    """
    ocr_logger = await obter_logger(identificador)
    if ocr_logger is None:
        raise HTTPException(404, "Nenhum processo OCR encontrado para este identificador")

    async def event_generator():
        ultimo_enviado = 0
        while not ocr_logger.concluido:
            etapas = ocr_logger.get_etapas()
            for i in range(ultimo_enviado, len(etapas)):
                yield _sse_payload("ocr-progresso", json.dumps(etapas[i], ensure_ascii=False))
                ultimo_enviado = i + 1
            await asyncio.sleep(0.5)

        # Enviar etapas restantes após conclusão
        etapas = ocr_logger.get_etapas()
        for i in range(ultimo_enviado, len(etapas)):
            yield _sse_payload("ocr-progresso", json.dumps(etapas[i], ensure_ascii=False))

        # Evento final
        yield _sse_payload("ocr-concluido", json.dumps({"identificador": identificador}))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
