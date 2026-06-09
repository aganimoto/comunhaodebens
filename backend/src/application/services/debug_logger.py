"""Sistema de debug em tempo real para o backend.

Funciona como um "React DevTools" para o backend — captura todos os
eventos relevantes (OCR, IA, webhooks, erros) e os streama via SSE
para o frontend, onde um painel flutuante os exibe.

Níveis de log:
- debug:    Detalhes internos (blocos OCR, payloads)
- info:     Informações gerais (etapas concluídas)
- warn:     Avisos (fallback usado, timeout parcial)
- error:    Erros (falha no OCR, IA sem retorno)
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class DebugLogger:
    """Logger global de debug. Armazena até 500 eventos em memória."""

    def __init__(self, max_entries: int = 500) -> None:
        self._max_entries = max_entries
        self._entries: list[dict[str, Any]] = []
        self._evento = asyncio.Event()

    def log(
        self,
        nivel: str,
        modulo: str,
        mensagem: str,
        detalhes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = {
            "nivel": nivel,
            "modulo": modulo,
            "mensagem": mensagem,
            "detalhes": detalhes or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._entries.append(entry)
        # Limitar memória
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

        # Log local também
        level_map = {
            "debug": logger.debug,
            "info": logger.info,
            "warn": logger.warning,
            "error": logger.error,
        }
        level_map.get(nivel, logger.info)(
            "[%s] %s | %s", modulo, mensagem,
            json.dumps(detalhes, ensure_ascii=False) if detalhes else ""
        )

        self._evento.set()
        return entry

    def debug(self, modulo: str, mensagem: str, detalhes: dict | None = None) -> None:
        self.log("debug", modulo, mensagem, detalhes)

    def info(self, modulo: str, mensagem: str, detalhes: dict | None = None) -> None:
        self.log("info", modulo, mensagem, detalhes)

    def warn(self, modulo: str, mensagem: str, detalhes: dict | None = None) -> None:
        self.log("warn", modulo, mensagem, detalhes)

    def error(self, modulo: str, mensagem: str, detalhes: dict | None = None) -> None:
        self.log("error", modulo, mensagem, detalhes)

    def get_entries(self, ultimos: int = 0) -> list[dict[str, Any]]:
        if ultimos > 0:
            return list(self._entries[-ultimos:])
        return list(self._entries)

    async def wait_event(self) -> None:
        await self._evento.wait()
        self._evento.clear()

    def clear(self) -> None:
        self._entries.clear()


# Instância global (singleton)
_instancia: DebugLogger | None = None


def get_debug_logger() -> DebugLogger:
    global _instancia
    if _instancia is None:
        _instancia = DebugLogger()
    return _instancia


# ── Módulos predefinidos ──────────────────────────────────────────────
MODULO_WEBHOOK = "webhook"
MODULO_OCR = "ocr"
MODULO_CLASSIFICADOR = "classificador"
MODULO_IA = "ia"
MODULO_BANCO = "banco"
MODULO_SHEETS = "sheets"
MODULO_NOTIFICACAO = "notificacao"
MODULO_AUTH = "auth"
MODULO_API = "api"