"""Use case: registra uma contribuição e sincroniza com Sheets/WhatsApp.

A partir da Fase 5, a sincronização com o Google Sheets é feita na aba
**Doações** (canônica) e cobre **tanto CONFIRMADO quanto PENDENTE**,
para que a equipe financeira tenha visão operacional completa. A aba
``Registros`` é mantida apenas para retrocompatibilidade (não recebe
mais dados novos — código legado que a consulta continua funcionando).

A **fonte da verdade** continua sendo o banco local. O Sheets é apenas
uma visão operacional.
"""
import logging
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.notificacao_service import NotificacaoService
from src.application.services.protocolo_service import ProtocoloService
from src.domain.entities.contribuicao import Contribuicao, StatusContribuicao
from src.infrastructure.database.repositories.contribuicao_repository import ContribuicaoRepository
from src.infrastructure.sheets.config_reader import ConfigReader
from src.infrastructure.sheets.sheets_writer import SheetsWriter

logger = logging.getLogger(__name__)


class RegistrarContribuicaoUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._protocolo = ProtocoloService(session)
        self._repo = ContribuicaoRepository(session)
        self._sheets = SheetsWriter()
        self._notificacao = NotificacaoService()
        self._config = ConfigReader()

    async def executar(
        self,
        telefone: str,
        membro_nome: str,
        membro_categoria: str,
        valor: Decimal,
        data_pagamento,
        hora_pagamento,
        banco: str | None,
        confianca: float,
        hash_sha256: str,
        status: StatusContribuicao,
        # Novos parâmetros (Fase 5) — opcionais, retrocompatíveis
        ocr_bruto_preview: str | None = None,
        tipo_documento: str | None = None,
        favorecido: str | None = None,
    ) -> Contribuicao:
        protocolo_vo = await self._protocolo.gerar()
        contrib = Contribuicao(
            id=None,
            protocolo=str(protocolo_vo),
            membro_id=None,
            telefone=telefone,
            valor=valor,
            data_pagamento=data_pagamento,
            hora_pagamento=hora_pagamento,
            banco=favorecido or banco,  # V2: favorecido; V1: banco
            confianca=confianca,
            status=status,
            hash_imagem=hash_sha256,
        )
        saved = await self._repo.save(contrib)

        # ── Sincronização Sheets (aba Doações) ──
        # Tanto CONFIRMADO quanto PENDENTE são gravados. A coluna Status
        # na planilha indica o estado. PENDENTE é para que a equipe
        # financeira consiga ver tudo que precisa de revisão manual.
        if status in (StatusContribuicao.CONFIRMADO, StatusContribuicao.PENDENTE):
            self._sheets.append_doacao(
                protocolo=saved.protocolo,
                data_pagamento=saved.data_pagamento,
                hora=saved.hora_pagamento,
                nome=membro_nome,
                categoria=membro_categoria,
                valor=saved.valor,
                favorecido=favorecido or banco,
                tipo_documento=tipo_documento or "PIX",
                telefone=telefone,
                status=saved.status.value,
                confianca=saved.confianca,
                ocr_bruto_preview=ocr_bruto_preview,
            )

        # ── Notificação WhatsApp ──
        if status == StatusContribuicao.CONFIRMADO:
            await self._notificacao.msg_agradecimento(
                telefone,
                membro_nome,
                f"{saved.valor:.2f}",
                saved.data_pagamento.isoformat(),
                saved.protocolo,
            )
        elif status == StatusContribuicao.PENDENTE:
            # PENDENTE (substitui REVISAO) — usa template configurável
            await self._notificacao.msg_revisao(
                telefone, saved.protocolo, nome=membro_nome
            )
        # REVISAO (legado) — alias de PENDENTE, mesma rota
        elif status.value == "revisao":  # pragma: no cover - retrocompat
            await self._notificacao.msg_revisao(
                telefone, saved.protocolo, nome=membro_nome
            )

        return saved
