from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.contribuicao import Contribuicao, StatusContribuicao
from src.domain.repositories.icontribuicao_repository import IContribuicaoRepository
from src.infrastructure.database.models import ContribuicaoModel


def _to_entity(m: ContribuicaoModel) -> Contribuicao:
    return Contribuicao(
        id=m.id,
        protocolo=m.protocolo,
        membro_id=m.membro_id,
        telefone=m.telefone,
        valor=Decimal(str(m.valor)),
        data_pagamento=m.data_pagamento,
        hora_pagamento=m.hora_pagamento,
        banco=m.banco,
        confianca=float(m.confianca) if m.confianca is not None else 0.0,
        status=StatusContribuicao(m.status),
        hash_imagem=m.hash_imagem,
        arquivo_id=m.arquivo_id,
        criado_em=m.criado_em,
        atualizado_em=m.atualizado_em,
    )


class ContribuicaoRepository(IContribuicaoRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, contribuicao: Contribuicao) -> Contribuicao:
        model = ContribuicaoModel(
            id=contribuicao.id or uuid4(),
            protocolo=contribuicao.protocolo,
            membro_id=contribuicao.membro_id,
            telefone=contribuicao.telefone,
            valor=contribuicao.valor,
            data_pagamento=contribuicao.data_pagamento,
            hora_pagamento=contribuicao.hora_pagamento,
            banco=contribuicao.banco,
            confianca=contribuicao.confianca,
            status=contribuicao.status.value,
            hash_imagem=contribuicao.hash_imagem,
            arquivo_id=contribuicao.arquivo_id,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)

    async def get_by_id(self, contribuicao_id: UUID) -> Contribuicao | None:
        r = await self._session.get(ContribuicaoModel, contribuicao_id)
        return _to_entity(r) if r else None

    async def get_by_protocolo(self, protocolo: str) -> Contribuicao | None:
        q = await self._session.execute(
            select(ContribuicaoModel).where(ContribuicaoModel.protocolo == protocolo)
        )
        m = q.scalar_one_or_none()
        return _to_entity(m) if m else None

    async def get_by_hash_imagem(self, hash_imagem: str) -> Contribuicao | None:
        q = await self._session.execute(
            select(ContribuicaoModel).where(ContribuicaoModel.hash_imagem == hash_imagem)
        )
        m = q.scalar_one_or_none()
        return _to_entity(m) if m else None

    async def list_paginated(
        self,
        skip: int = 0,
        limit: int = 20,
        status: str | None = None,
    ) -> tuple[list[Contribuicao], int]:
        base = select(ContribuicaoModel)
        count_q = select(func.count()).select_from(ContribuicaoModel)
        if status:
            base = base.where(ContribuicaoModel.status == status)
            count_q = count_q.where(ContribuicaoModel.status == status)
        total = (await self._session.execute(count_q)).scalar() or 0
        q = await self._session.execute(
            base.order_by(ContribuicaoModel.criado_em.desc()).offset(skip).limit(limit)
        )
        return [_to_entity(m) for m in q.scalars().all()], total

    async def update(self, contribuicao: Contribuicao) -> Contribuicao:
        m = await self._session.get(ContribuicaoModel, contribuicao.id)
        if not m:
            raise ValueError("Contribuição não encontrada")
        m.status = contribuicao.status.value
        m.valor = contribuicao.valor
        m.banco = contribuicao.banco
        await self._session.flush()
        return _to_entity(m)
