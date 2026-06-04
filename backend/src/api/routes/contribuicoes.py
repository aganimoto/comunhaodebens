from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import Perfil, get_current_user, require_perfil
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.repositories.contribuicao_repository import ContribuicaoRepository

router = APIRouter(prefix="/contribuicoes", tags=["contribuicoes"])


class ContribuicaoOut(BaseModel):
    id: UUID
    protocolo: str
    telefone: str
    valor: float
    data_pagamento: str
    status: str
    confianca: float


@router.get("")
async def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    _user=Depends(get_current_user),
):
    repo = ContribuicaoRepository(session)
    items, total = await repo.list_paginated(skip=skip, limit=limit, status=status)
    return {
        "items": [
            ContribuicaoOut(
                id=c.id,
                protocolo=c.protocolo,
                telefone=c.telefone,
                valor=float(c.valor),
                data_pagamento=c.data_pagamento.isoformat(),
                status=c.status.value,
                confianca=c.confianca,
            )
            for c in items
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{contribuicao_id}")
async def detalhe(
    contribuicao_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    _user=Depends(get_current_user),
):
    repo = ContribuicaoRepository(session)
    c = await repo.get_by_id(contribuicao_id)
    if not c:
        from fastapi import HTTPException

        raise HTTPException(404, "Não encontrada")
    return ContribuicaoOut(
        id=c.id,
        protocolo=c.protocolo,
        telefone=c.telefone,
        valor=float(c.valor),
        data_pagamento=c.data_pagamento.isoformat(),
        status=c.status.value,
        confianca=c.confianca,
    )


class ContribuicaoPatch(BaseModel):
    status: str | None = None
    banco: str | None = None


@router.patch("/{contribuicao_id}")
async def atualizar(
    contribuicao_id: UUID,
    body: ContribuicaoPatch,
    session: AsyncSession = Depends(get_db_session),
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR, Perfil.FINANCEIRO)),
):
    from src.domain.entities.contribuicao import StatusContribuicao

    repo = ContribuicaoRepository(session)
    c = await repo.get_by_id(contribuicao_id)
    if not c:
        from fastapi import HTTPException

        raise HTTPException(404, "Não encontrada")
    if body.status:
        c.status = StatusContribuicao(body.status)
    if body.banco is not None:
        c.banco = body.banco
    return await repo.update(c)
