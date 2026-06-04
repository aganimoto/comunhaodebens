"""Escrita no Google Sheets (com fallback local JSON quando indisponível)."""
from datetime import date, time
from decimal import Decimal
from uuid import UUID

from src.infrastructure.sheets.sheets_client import SheetsClient


class SheetsWriter:
    def __init__(self, client=None) -> None:
        self._client = client or SheetsClient()

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

    def append_auditoria(
        self,
        evento: str,
        detalhes: str,
        contribuicao_id: UUID | None = None,
        telefone: str | None = None,
    ) -> None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from src.config import get_settings

        tz = ZoneInfo(get_settings().app_timezone)
        now = datetime.now(tz).isoformat()
        # Planilha: Timestamp, Evento, Detalhes
        detalhes_completo = detalhes
        if telefone:
            detalhes_completo = f"[{telefone}] {detalhes}"
        if contribuicao_id:
            detalhes_completo = f"[contribuição {contribuicao_id}] {detalhes_completo}"

        self._client.append_row(
            "Auditoria",
            [
                now,
                evento,
                detalhes_completo,
            ],
        )