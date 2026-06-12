"""Use case: registra uma contribuição apenas no Google Sheets.

Este use case NÃO usa banco de dados. Toda persistência é feita
diretamente na planilha Google Sheets via :class:`SheetsWriter`.
"""
import logging
import uuid
from decimal import Decimal

from src.application.services.notificacao_service import NotificacaoService
from src.config import get_settings
from src.domain.entities.contribuicao import StatusContribuicao
from src.infrastructure.sheets.sheets_writer import SheetsWriter

logger = logging.getLogger(__name__)


def _gerar_protocolo() -> str:
    """Gera protocolo único usando timestamp + hash curto."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(get_settings().app_timezone)
    now = datetime.now(tz)
    hash_curto = uuid.uuid4().hex[:6].upper()
    return f"{now.strftime('%Y%m%d')}-{hash_curto}"


class RegistrarContribuicaoUseCase:
    def __init__(self) -> None:
        self._sheets = SheetsWriter()
        self._notificacao = NotificacaoService()

    async def executar(
        self,
        telefone: str,
        membro_nome: str,
        membro_categoria: str,
        valor: Decimal,
        data_pagamento,
        confianca: float,
        hash_sha256: str,
        status: StatusContribuicao,
        ocr_bruto_preview: str | None = None,
        favorecido: str | None = None,
    ) -> str:
        """Registra contribuição na planilha e envia notificação.

        Retorna o protocolo gerado.
        """
        protocolo = _gerar_protocolo()

        # ── Gravar na planilha (aba Doações) ──
        self._sheets.append_doacao(
            protocolo=protocolo,
            data_pagamento=data_pagamento,
            nome=membro_nome,
            categoria=membro_categoria,
            valor=valor,
            favorecido=favorecido,
            telefone=telefone,
            status=status.value,
            confianca=confianca,
            ocr_bruto_preview=ocr_bruto_preview,
        )

        # ── Auditoria ──
        self._sheets.append_auditoria(
            evento="CONTRIBUICAO_REGISTRADA",
            detalhes=f"Protocolo {protocolo}, Valor R$ {valor:.2f}, Status: {status.value}",
            telefone=telefone,
        )

        # ── Notificação WhatsApp ──
        if status == StatusContribuicao.CONFIRMADO:
            await self._notificacao.msg_agradecimento(
                telefone,
                membro_nome,
                f"{valor:.2f}",
                data_pagamento.isoformat(),
                protocolo,
            )
        elif status == StatusContribuicao.PENDENTE:
            await self._notificacao.msg_revisao(
                telefone, protocolo, nome=membro_nome
            )

        return protocolo