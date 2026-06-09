"""Endpoint SSE para debug em tempo real do backend.

Fornece um stream de logs detalhados (níveis debug, info, warn, error)
de todos os módulos (OCR, IA, webhook, banco, etc.) para o frontend.

O frontend conecta em:
    GET /api/v1/debug/stream

E recebe eventos SSE como:
    event: debug-log
    data: {"nivel":"info","modulo":"ocr","mensagem":"...","detalhes":{...}}
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.application.services.debug_logger import get_debug_logger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["debug"])


def _sse_payload(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


@router.get("/stream")
async def debug_stream():
    """SSE endpoint: stream de logs de debug do backend em tempo real."""
    debug_logger = get_debug_logger()

    async def event_generator():
        ultimo_enviado = 0
        while True:
            entries = debug_logger.get_entries()
            for i in range(ultimo_enviado, len(entries)):
                yield _sse_payload("debug-log", json.dumps(entries[i], ensure_ascii=False))
                ultimo_enviado = i + 1

            if not entries:
                # Se não há nada, espera um pouco
                await asyncio.sleep(0.5)
            else:
                # Se há entradas recentes, espera o próximo evento
                try:
                    await asyncio.wait_for(debug_logger.wait_event(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/logs")
async def get_logs(ultimos: int = 100):
    """Retorna os últimos logs em formato JSON (útil para polling)."""
    debug_logger = get_debug_logger()
    return debug_logger.get_entries(ultimos)


@router.post("/clear")
async def clear_logs():
    """Limpa todos os logs de debug."""
    debug_logger = get_debug_logger()
    debug_logger.clear()
    return {"ok": True}