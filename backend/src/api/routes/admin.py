"""Endpoints administrativos (cache, dashboard, backup, restore)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import Perfil, require_perfil
from src.infrastructure.cache.redis_client import cache_delete_pattern
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import ContribuicaoModel, PendenciaModel

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/cache/flush")
async def flush_cache(
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR)),
):
    deleted = await cache_delete_pattern("membros:*")
    deleted += await cache_delete_pattern("config:*")
    return {"deleted_keys": deleted}


@router.get("/dashboard/stats")
async def dashboard_stats(
    session: AsyncSession = Depends(get_db_session),
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR, Perfil.FINANCEIRO, Perfil.CONSULTA)),
):
    total = (
        await session.execute(select(func.count()).select_from(ContribuicaoModel))
    ).scalar() or 0
    confirmadas = (
        await session.execute(
            select(func.count()).select_from(ContribuicaoModel).where(
                ContribuicaoModel.status == "confirmado"
            )
        )
    ).scalar() or 0
    revisao = (
        await session.execute(
            select(func.count()).select_from(ContribuicaoModel).where(
                ContribuicaoModel.status == "revisao"
            )
        )
    ).scalar() or 0
    pendencias = (
        await session.execute(
            select(func.count()).select_from(PendenciaModel).where(PendenciaModel.status == "aberto")
        )
    ).scalar() or 0
    total_valor = (
        await session.execute(
            select(func.coalesce(func.sum(ContribuicaoModel.valor), 0)).where(
                ContribuicaoModel.status == "confirmado"
            )
        )
    ).scalar() or 0
    return {
        "total_contribuicoes": total,
        "contribuicoes_confirmadas": confirmadas,
        "contribuicoes_revisao": revisao,
        "pendencias_abertas": pendencias,
        "valor_total_confirmado": float(total_valor),
    }


class RestoreBody(BaseModel):
    backup_filename: str
    confirmar: bool


@router.post("/backup/restore")
async def restore_backup(
    body: RestoreBody,
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR)),
):
    if not body.confirmar:
        raise HTTPException(400, "Confirmação obrigatória")
    return {"status": "scheduled", "file": body.backup_filename}


@router.post("/backup/run", status_code=202)
async def run_backup_now(
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR)),
):
    """Dispara o backup imediatamente (útil para teste)."""
    from src.tasks.backup_task import backup_diario

    async_result = backup_diario.delay()
    return {"status": "enqueued", "task_id": str(async_result.id)}


@router.get("/backup/list")
async def list_backups(
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR, Perfil.FINANCEIRO)),
):
    """Lista os backups disponíveis."""
    from src.tasks.backup_task import listar_backups

    return listar_backups.apply().get()
