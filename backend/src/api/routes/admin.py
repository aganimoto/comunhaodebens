"""Endpoints administrativos (cache, dashboard, backup, restore) — Fase 6 expande o dashboard."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import Perfil, require_perfil
from src.config import get_settings
from src.infrastructure.cache.redis_client import cache_delete_pattern
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import (
    ContribuicaoModel,
    MembroModel,
    PendenciaModel,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Cache ──────────────────────────────────────────────────────────────
@router.post("/cache/flush")
async def flush_cache(
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR)),
):
    deleted = await cache_delete_pattern("membros:*")
    deleted += await cache_delete_pattern("config:*")
    return {"deleted_keys": deleted}


# ── Dashboard (Fase 6: expandido) ──────────────────────────────────────
class ContribuicaoResumo(BaseModel):
    id: str
    protocolo: str
    telefone: str
    valor: float
    data_pagamento: str
    status: str
    confianca: float


class PendenciaResumo(BaseModel):
    id: str
    telefone: str | None
    motivo: str
    status: str
    contribuicao_id: str | None
    criado_em: str | None


class DashboardStats(BaseModel):
    # Métricas originais
    total_contribuicoes: int
    contribuicoes_confirmadas: int
    contribuicoes_revisao: int  # alias de PENDENTE (retrocompat UI)
    contribuicoes_pendentes: int  # novo
    contribuicoes_processando: int
    pendencias_abertas: int
    valor_total_confirmado: float
    # Métricas novas (Fase 6)
    valor_hoje: float
    valor_mes: float
    ultimas_contribuicoes: list[ContribuicaoResumo]
    pendencias_ocr: list[PendenciaResumo]
    # Hash das imagens em processamento (para barra de progresso SSE)
    processando_hashes: list[str] = []


def _to_resumo_contrib(c: ContribuicaoModel) -> ContribuicaoResumo:
    return ContribuicaoResumo(
        id=str(c.id),
        protocolo=c.protocolo,
        telefone=c.telefone,
        valor=float(c.valor),
        data_pagamento=c.data_pagamento.isoformat() if c.data_pagamento else "",
        status=c.status,
        confianca=float(c.confianca) if c.confianca is not None else 0.0,
    )


def _to_resumo_pendencia(p: PendenciaModel) -> PendenciaResumo:
    return PendenciaResumo(
        id=str(p.id),
        telefone=p.telefone,
        motivo=p.motivo,
        status=p.status,
        contribuicao_id=str(p.contribuicao_id) if p.contribuicao_id else None,
        criado_em=p.criado_em.isoformat() if p.criado_em else None,
    )


@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats(
    session: AsyncSession = Depends(get_db_session),
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR, Perfil.FINANCEIRO, Perfil.CONSULTA)),
):
    """Estatísticas expandidas do dashboard (Fase 6).

    Inclui totais clássicos + ``valor_hoje``, ``valor_mes``,
    ``ultimas_contribuicoes`` e ``pendencias_ocr`` (pendências que
    representam falhas de OCR/IA — sobre as quais o botão
    "Reprocessar" do painel atua).
    """
    # Métricas clássicas
    total = (await session.execute(select(func.count()).select_from(ContribuicaoModel))).scalar() or 0
    confirmadas = (
        await session.execute(
            select(func.count()).select_from(ContribuicaoModel).where(
                ContribuicaoModel.status == "confirmado"
            )
        )
    ).scalar() or 0
    # "em revisão" é o alias antigo — mantido para retrocompat da UI
    revisao = (
        await session.execute(
            select(func.count()).select_from(ContribuicaoModel).where(
                ContribuicaoModel.status == "revisao"
            )
        )
    ).scalar() or 0
    # PENDENTE é o status novo
    pendentes = (
        await session.execute(
            select(func.count()).select_from(ContribuicaoModel).where(
                ContribuicaoModel.status == "pendente"
            )
        )
    ).scalar() or 0
    processando = (
        await session.execute(
            select(func.count()).select_from(ContribuicaoModel).where(
                ContribuicaoModel.status == "processando"
            )
        )
    ).scalar() or 0
    pendencias_abertas = (
        await session.execute(
            select(func.count()).select_from(PendenciaModel).where(
                PendenciaModel.status == "aberto"
            )
        )
    ).scalar() or 0
    valor_total_confirmado = (
        await session.execute(
            select(func.coalesce(func.sum(ContribuicaoModel.valor), 0)).where(
                ContribuicaoModel.status == "confirmado"
            )
        )
    ).scalar() or 0

    # Métricas novas
    settings = get_settings()
    tz = timezone(timedelta(hours=-3))  # America/Sao_Paulo fixo
    agora = datetime.now(tz)
    hoje = agora.date()
    mes_inicio = hoje.replace(day=1)

    valor_hoje = (
        await session.execute(
            select(func.coalesce(func.sum(ContribuicaoModel.valor), 0)).where(
                ContribuicaoModel.status == "confirmado",
                ContribuicaoModel.data_pagamento == hoje,
            )
        )
    ).scalar() or 0

    valor_mes = (
        await session.execute(
            select(func.coalesce(func.sum(ContribuicaoModel.valor), 0)).where(
                ContribuicaoModel.status == "confirmado",
                ContribuicaoModel.data_pagamento >= mes_inicio,
            )
        )
    ).scalar() or 0

    # Últimas 5 contribuições
    q_ultimas = await session.execute(
        select(ContribuicaoModel)
        .order_by(desc(ContribuicaoModel.criado_em))
        .limit(5)
    )
    ultimas = [_to_resumo_contrib(c) for c in q_ultimas.scalars().all()]

    # Pendências que representam falhas OCR/IA (sobre as quais o botão
    # "Reprocessar" do painel atua). Exclui pendências de
    # telefone_nao_cadastrado e comprovante_duplicado (que não
    # envolvem reprocessamento de imagem).
    motivos_ocr = ("ocr_baixa_confianca", "ia_baixa_confianca", "erro_processamento")
    q_pend_ocr = await session.execute(
        select(PendenciaModel)
        .where(
            PendenciaModel.status == "aberto",
            PendenciaModel.motivo.in_(motivos_ocr),
        )
        .order_by(desc(PendenciaModel.criado_em))
        .limit(20)
    )
    pendencias_ocr = [_to_resumo_pendencia(p) for p in q_pend_ocr.scalars().all()]

    # Buscar hashes das contribuições em processamento (para barra SSE)
    q_hashes = await session.execute(
        select(ContribuicaoModel.hash_imagem).where(
            ContribuicaoModel.status == "processando"
        )
    )
    processando_hashes = [row[0] for row in q_hashes.all() if row[0]]

    return DashboardStats(
        processando_hashes=processando_hashes,
        total_contribuicoes=total,
        contribuicoes_confirmadas=confirmadas,
        contribuicoes_revisao=revisao,
        contribuicoes_pendentes=pendentes,
        contribuicoes_processando=processando,
        pendencias_abertas=pendencias_abertas,
        valor_total_confirmado=float(valor_total_confirmado),
        valor_hoje=float(valor_hoje),
        valor_mes=float(valor_mes),
        ultimas_contribuicoes=ultimas,
        pendencias_ocr=pendencias_ocr,
    )


# ── Backup ─────────────────────────────────────────────────────────────
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
