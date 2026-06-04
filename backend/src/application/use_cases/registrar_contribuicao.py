import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.notificacao_service import NotificacaoService
from src.application.services.protocolo_service import ProtocoloService
from src.domain.entities.contribuicao import Contribuicao, StatusContribuicao
from src.infrastructure.database.repositories.contribuicao_repository import ContribuicaoRepository
from src.infrastructure.sheets.config_reader import ConfigReader
from src.infrastructure.sheets.sheets_writer import SheetsWriter


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
            banco=banco,
            confianca=confianca,
            status=status,
            hash_imagem=hash_sha256,
        )
        saved = await self._repo.save(contrib)

        if status == StatusContribuicao.CONFIRMADO:
            self._sheets.append_registro(
                saved.protocolo,
                saved.data_pagamento,
                saved.hora_pagamento,
                membro_nome,
                membro_categoria,
                saved.valor,
                saved.banco,
                telefone,
                saved.status.value,
                saved.confianca,
            )
            await self._notificacao.msg_agradecimento(
                telefone,
                membro_nome,
                f"{saved.valor:.2f}",
                saved.data_pagamento.isoformat(),
                saved.protocolo,
            )
        elif status == StatusContribuicao.REVISAO:
            await self._notificacao.msg_revisao(telefone, saved.protocolo)

        return saved
