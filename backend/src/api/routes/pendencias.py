from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import Perfil, get_current_user, require_perfil
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import MembroModel, PendenciaModel

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
            "observacao": r.observacao or "",
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


class CadastrarMembroBody(BaseModel):
    pendencia_id: UUID
    nome: str
    categoria: str = "benfeitor"
    observacao: str = ""


@router.post("/cadastrar-membro")
async def cadastrar_membro_e_resolver(
    body: CadastrarMembroBody,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_perfil(Perfil.ADMINISTRADOR, Perfil.FINANCEIRO)),
):
    """Cadastra um novo membro e resolve a pendência associada."""
    # Buscar a pendência
    p = await session.get(PendenciaModel, body.pendencia_id)
    if not p:
        raise HTTPException(404, "Pendência não encontrada")
    if not p.telefone:
        raise HTTPException(400, "Pendência sem telefone — não é possível cadastrar membro")

    # Verificar se já existe membro com este telefone
    result = await session.execute(
        select(MembroModel).where(MembroModel.telefone == p.telefone)
    )
    if result.scalar_one_or_none():
        raise HTTPException(409, f"Já existe um membro cadastrado com o telefone {p.telefone}")

    # Limpar o telefone (remover + e caracteres não dígito)
    telefone_limpo = p.telefone.lstrip("+")
    if telefone_limpo.startswith("55") and len(telefone_limpo) > 12:
        telefone_limpo = telefone_limpo  # mantém com DDI

    # Criar membro
    membro = MembroModel(
        id=uuid4(),
        telefone=telefone_limpo,
        nome=body.nome.strip(),
        categoria=body.categoria.strip(),
        ativo=True,
    )
    session.add(membro)

    # Resolver a pendência
    p.status = "resolvido"
    p.observacao = body.observacao or f"Membro cadastrado: {body.nome}"
    p.resolvido_por = user.get("email")
    p.resolvido_em = datetime.now(timezone.utc)

    await session.flush()
    return {
        "membro_id": str(membro.id),
        "pendencia_id": str(p.id),
        "status": p.status,
        "telefone": membro.telefone,
        "nome": membro.nome,
        "categoria": membro.categoria,
    }
