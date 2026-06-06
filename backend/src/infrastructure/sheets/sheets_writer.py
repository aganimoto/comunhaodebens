"""Escrita no Google Sheets (com fallback local JSON quando indisponível).

A partir da Fase 5 do projeto de evolução:

* ``append_doacao`` é o método canônico para novos lançamentos. Grava
  na aba ``Doações``, sincronizando tanto ``CONFIRMADO`` quanto
  ``PENDENTE`` (visão operacional completa, com coluna Status).
* ``append_registro`` é mantido como alias retrocompatível (ainda grava
  na aba ``Registros``) — o código legado que consulta essa aba não
  quebra, mas nenhum dado novo é mais escrito nela.
* ``append_auditoria`` agora aceita ``detalhes_dict`` opcional, que é
  serializado como JSON no campo ``Detalhes``. Permite registrar o JSON
  completo da IA junto com o evento de ``OCR_CONCLUIDO``.
"""
from __future__ import annotations

import json
import logging
from datetime import date, time
from decimal import Decimal
from uuid import UUID

from src.infrastructure.sheets.sheets_client import SheetsClient

logger = logging.getLogger(__name__)

# Limite de caracteres do OCR Bruto exibido na planilha (auditoria)
_OCR_PREVIEW_MAX_CHARS = 100


class SheetsWriter:
    def __init__(self, client: SheetsClient | None = None) -> None:
        self._client = client or SheetsClient()

    # ── Doações (canônico) ──────────────────────────────────────────────
    def append_doacao(
        self,
        protocolo: str,
        data_pagamento: date,
        hora: time | None,
        nome: str,
        categoria: str,
        valor: Decimal,
        favorecido: str | None,
        tipo_documento: str | None,
        telefone: str,
        status: str,
        confianca: float,
        ocr_bruto_preview: str | None = None,
    ) -> None:
        """Adiciona uma linha na aba ``Doações`` (CONFIRMADO ou PENDENTE).

        Colunas: Protocolo, Data, Hora, Nome, Categoria, Valor,
        Favorecido, Tipo Documento, Telefone, Status, Confiança, OCR Bruto.
        """
        hora_str = hora.strftime("%H:%M") if hora else ""
        ocr_preview = ""
        if ocr_bruto_preview:
            ocr_preview = ocr_bruto_preview.replace("\n", " ").strip()[:_OCR_PREVIEW_MAX_CHARS]
        self._client.append_row(
            "Doações",
            [
                protocolo,
                data_pagamento.isoformat(),
                hora_str,
                nome,
                categoria,
                f"{valor:.2f}",
                favorecido or "",
                tipo_documento or "",
                telefone,
                status,
                f"{confianca * 100:.0f}%",
                ocr_preview,
            ],
        )

    # ── Registros (legacy, retrocompatível) ─────────────────────────────
    def append_registro(
        self,
        protocolo: str,
        data_pagamento: date,
        hora: time | None,
        nome: str,
        categoria: str,
        valor: Decimal,
        banco: str | None,
        telefone: str,
        status: str,
        confianca: float,
    ) -> None:
        """Alias retrocompatível — grava na aba legada ``Registros``.

        A partir da Fase 5, novos lançamentos devem usar
        :meth:`append_doacao`. Este método é mantido para que código
        legado (ou integrações externas que ainda consultam ``Registros``)
        não quebre.
        """
        hora_str = hora.strftime("%H:%M") if hora else ""
        self._client.append_row(
            "Registros",
            [
                protocolo,
                data_pagamento.isoformat(),
                hora_str,
                nome,
                categoria,
                f"{valor:.2f}",
                banco or "",
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
        # Planilha: ID, Data, Telefone, Nome, Motivo, Status, Observação
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

    # ── Auditoria (com JSON opcional da IA) ─────────────────────────────
    def append_auditoria(
        self,
        evento: str,
        detalhes: str,
        contribuicao_id: UUID | None = None,
        telefone: str | None = None,
        detalhes_dict: dict | None = None,
    ) -> None:
        """Adiciona linha na aba ``Auditoria``.

        Aceita ``detalhes_dict`` opcional: quando presente, o dicionário
        é serializado como JSON e anexado à string de detalhes. Use
        para gravar o JSON bruto da IA junto com o evento
        ``OCR_CONCLUIDO``.
        """
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
                f"{detalhes_completo} | IA: {json.dumps(detalhes_dict, ensure_ascii=False, default=str)}"
            )

        self._client.append_row(
            "Auditoria",
            [
                now,
                evento,
                detalhes_completo,
            ],
        )
