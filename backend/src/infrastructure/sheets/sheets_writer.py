"""Escrita no Google Sheets.

A partir da Fase 5, o método principal é ``append_doacao`` que grava
na aba ``Doações`` com a estrutura otimizada para o novo fluxo de
extração via regex.

Métodos legados:
- ``append_registro`` — mantido para retrocompatibilidade (aba Registros)
- ``append_pendencia`` — grava na aba Pendências
- ``append_auditoria`` — grava na aba Auditoria
"""
from __future__ import annotations

import json
import logging
from datetime import date, time
from decimal import Decimal
from uuid import UUID

from src.infrastructure.sheets.sheets_client import SheetsClient

logger = logging.getLogger(__name__)

_OCR_PREVIEW_MAX_CHARS = 100


class SheetsWriter:
    def __init__(self, client: SheetsClient | None = None) -> None:
        self._client = client or SheetsClient()

    # ── Doações (canônico) ──────────────────────────────────────────────
    def append_doacao(
        self,
        protocolo: str,
        data_pagamento: date,
        nome: str,
        categoria: str,
        valor: Decimal,
        favorecido: str | None,
        telefone: str,
        status: str,
        confianca: float,
        ocr_bruto_preview: str | None = None,
    ) -> None:
        """Adiciona uma linha na aba ``Doações``.

        Colunas: Protocolo, Data, Nome, Categoria, Valor,
        Favorecido, Telefone, Status, Confiança, OCR Preview.
        """
        ocr_preview = ""
        if ocr_bruto_preview:
            ocr_preview = ocr_bruto_preview.replace("\n", " ").strip()[:_OCR_PREVIEW_MAX_CHARS]
        self._client.append_row(
            "Doações",
            [
                protocolo,
                data_pagamento.isoformat(),
                nome,
                categoria,
                f"{valor:.2f}",
                favorecido or "",
                telefone,
                status,
                f"{confianca * 100:.0f}%",
                ocr_preview,
            ],
        )

    # ── Registros (legacy) ─────────────────────────────────────────────
    def append_registro(
        self,
        protocolo: str,
        data_pagamento: date,
        nome: str,
        categoria: str,
        valor: Decimal,
        telefone: str,
        status: str,
        confianca: float,
    ) -> None:
        """Alias retrocompatível — grava na aba legada ``Registros``."""
        self._client.append_row(
            "Registros",
            [
                protocolo,
                data_pagamento.isoformat(),
                nome,
                categoria,
                f"{valor:.2f}",
                telefone,
                status,
                f"{confianca * 100:.0f}%",
            ],
        )

    # ── Pendências ──────────────────────────────────────────────────────
    def append_pendencia(
        self,
        pendencia_id: UUID,
        telefone: str,
        nome: str | None,
        motivo: str,
        observacao: str = "",
    ) -> None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from src.config import get_settings

        tz = ZoneInfo(get_settings().app_timezone)
        now = datetime.now(tz)
        self._client.append_row(
            "Pendências",
            [
                str(pendencia_id),
                now.date().isoformat(),
                telefone,
                nome or "",
                motivo,
                "aberto",
                observacao,
            ],
        )

    # ── Auditoria ───────────────────────────────────────────────────────
    def append_auditoria(
        self,
        evento: str,
        detalhes: str,
        contribuicao_id: UUID | None = None,
        telefone: str | None = None,
        detalhes_dict: dict | None = None,
    ) -> None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from src.config import get_settings

        tz = ZoneInfo(get_settings().app_timezone)
        now = datetime.now(tz).isoformat()
        detalhes_completo = detalhes
        if telefone:
            detalhes_completo = f"[{telefone}] {detalhes_completo}"
        if contribuicao_id:
            detalhes_completo = f"[contribuição {contribuicao_id}] {detalhes_completo}"
        if detalhes_dict:
            detalhes_completo = (
                f"{detalhes_completo} | Dados: {json.dumps(detalhes_dict, ensure_ascii=False, default=str)}"
            )

        self._client.append_row(
            "Auditoria",
            [
                now,
                evento,
                detalhes_completo,
            ],
        )