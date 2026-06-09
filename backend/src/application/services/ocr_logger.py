"""Serviço de logging em tempo real do progresso do OCR.

Permite que o frontend acompanhe o progresso da análise de um comprovante
via Server-Sent Events (SSE), exibindo uma barra de loading com os passos:

1. 📥 Imagem recebida
2. 🔍 Iniciando OCR (EasyOCR)
3. 📝 Texto extraído
4. ✅ Classificando comprovante
5. 🤖 Consultando IA (Ollama)
6. ✅ Análise concluída
7. ❌ Erro (se houver)
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class OCRLogger:
    """Registra o progresso do OCR e permite que listeners SSE acompanhem."""

    def __init__(self, identificador: str) -> None:
        self._identificador = identificador
        self._etapas: list[dict[str, Any]] = []
        self._concluido = False
        self._evento = asyncio.Event()
        self._evento.set()  # começa liberado

    @property
    def identificador(self) -> str:
        return self._identificador

    @property
    def concluido(self) -> bool:
        return self._concluido

    def _add_etapa(
        self,
        etapa: str,
        status: str,
        detalhes: str = "",
        progresso: float = 0.0,
    ) -> dict[str, Any]:
        entry = {
            "identificador": self._identificador,
            "etapa": etapa,
            "status": status,
            "detalhes": detalhes,
            "progresso": progresso,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._etapas.append(entry)
        logger.info("[OCR %s] %s | %s%s", self._identificador[:8], etapa, detalhes,
                     f" ({progresso:.0%})" if progresso else "")
        return entry

    def registrar(
        self,
        etapa: str,
        status: str = "andamento",
        detalhes: str = "",
        progresso: float = 0.0,
    ) -> None:
        entry = self._add_etapa(etapa, status, detalhes, progresso)
        # Notificar listeners SSE
        self._evento.set()

    def registrar_erro(self, etapa: str, detalhes: str) -> None:
        self._add_etapa(etapa, "erro", detalhes)
        self._concluido = True
        self._evento.set()

    def registrar_conclusao(self, detalhes: str = "") -> None:
        self._add_etapa("Concluído", "concluido", detalhes, 1.0)
        self._concluido = True
        self._evento.set()

    def get_etapas(self) -> list[dict[str, Any]]:
        return list(self._etapas)


# ── Gerenciador global de loggers ativos ──────────────────────────────
_loggers_ativos: dict[str, OCRLogger] = {}
_lock = asyncio.Lock()


async def criar_logger(identificador: str) -> OCRLogger:
    """Cria ou reusa um logger para um identificador único."""
    async with _lock:
        if identificador not in _loggers_ativos:
            _loggers_ativos[identificador] = OCRLogger(identificador)
        return _loggers_ativos[identificador]


async def obter_logger(identificador: str) -> OCRLogger | None:
    """Obtém um logger existente."""
    async with _lock:
        return _loggers_ativos.get(identificador)


async def remover_logger(identificador: str) -> None:
    """Remove um logger após conclusão (limpeza)."""
    async with _lock:
        _loggers_ativos.pop(identificador, None)


# ── Etapas predefinidas ───────────────────────────────────────────────
ETAPA_IMAGEM_RECEBIDA = "📥 Imagem recebida"
ETAPA_INICIANDO_OCR = "🔍 Iniciando OCR"
ETAPA_TEXTO_EXTRAIDO = "📝 Texto extraído"
ETAPA_CLASSIFICANDO = "✅ Classificando comprovante"
ETAPA_CONSULTANDO_IA = "🤖 Consultando IA"
ETAPA_CONCLUIDO = "✅ Análise concluída"
ETAPA_ERRO = "❌ Erro"

PROGRESSO_ETAPAS: dict[str, float] = {
    ETAPA_IMAGEM_RECEBIDA: 0.1,
    ETAPA_INICIANDO_OCR: 0.25,
    ETAPA_TEXTO_EXTRAIDO: 0.50,
    ETAPA_CLASSIFICANDO: 0.65,
    ETAPA_CONSULTANDO_IA: 0.80,
    ETAPA_CONCLUIDO: 1.0,
}