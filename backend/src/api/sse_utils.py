"""Utilitários compartilhados para Server-Sent Events (SSE)."""
from __future__ import annotations


def sse_payload(event: str, data: str) -> str:
    """Formata uma mensagem SSE no padrão W3C.

    Args:
        event: Nome do evento (ex: "debug-log", "ocr-progresso").
        data: Dados JSON serializados como string.

    Returns:
        String formatada como mensagem SSE.
    """
    return f"event: {event}\ndata: {data}\n\n"