from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import Perfil, get_current_user, require_perfil
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import PendenciaModel

router = APIRouter(prefix="/pendencias", tags=["pendencias"])


@router.get("")
async def listar(
    status: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    _user=Depends(get_current_user),
):
    q = select(PendenciaModel)
    if status:
        q = q.where(PendenciaModel.status == status)
    result = await session.execute(q.order_by(PendenciaModel.criado_em.desc()).limit(100))
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "telefone": r.telefone,
            "motivo": r.motivo,
            "status": r.status,
            "criado_em": r.criado_em.isoformat() if r.criado_em else None,
        }
        for r in rows
    ]


class ResolverBody(BaseModel):
    observacao: str = ""


@router.patch("/{pendencia_id}/resolver")
async def resolver(
    pendencia_id: UUID,
    body: ResolverBody,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_perfil(Perfil.ADMINISTRADOR, Perfil.FINANCEIRO)),
):
    p = await session.get(PendenciaModel, pendencia_id)
    if not p:
        raise HTTPException(404, "Pendência não encontrada")
    p.status = "resolvido"
    p.observacao = body.observacao
    p.resolvido_por = user.get("email")
    p.resolvido_em = datetime.now(timezone.utc)
    await session.flush()
    return {"id": str(p.id), "status": p.status}
