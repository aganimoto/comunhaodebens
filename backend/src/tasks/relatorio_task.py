"""Tasks periódicas de geração de relatório mensal PDF."""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.application.reports.relatorio_service import RelatorioService
from src.config import get_settings
from src.infrastructure.database.connection import async_session_factory
from src.infrastructure.database.models import ContribuicaoModel
from src.tasks.celery_app import celery_app


@celery_app.task(name="gerar_relatorio_mensal")
def gerar_relatorio_mensal(ano: int | None = None, mes: int | None = None) -> dict:
    """Gera o PDF do mês solicitado (default: mês atual)."""
    return asyncio.get_event_loop().run_until_complete(
        _async_gerar(ano, mes)
    )


async def _async_gerar(ano: int | None, mes: int | None) -> dict:
    settings = get_settings()
    tz = ZoneInfo(settings.app_timezone)
    hoje = datetime.now(tz).date()
    alvo_ano = ano or hoje.year
    alvo_mes = mes or hoje.month
    async with async_session_factory() as session:
        service = RelatorioService(session)
        path = await service.gerar_e_salvar(alvo_ano, alvo_mes)
    return {"status": "ok", "arquivo": str(path), "ano": alvo_ano, "mes": alvo_mes}


@celery_app.task(name="regenerar_relatorios_faltantes")
def regenerar_relatorios_faltantes() -> dict:
    """Gera relatórios de meses anteriores que ainda não possuem PDF."""
    return asyncio.get_event_loop().run_until_complete(_async_regenerar())


async def _async_regenerar() -> dict:
    settings = get_settings()
    base = Path(settings.shared_relatorios_path)
    base.mkdir(parents=True, exist_ok=True)
    gerados: list[str] = []
    async with async_session_factory() as session:
        service = RelatorioService(session)
        # detecta meses já gerados
        existentes = {p.stem.replace("relatorio_", "") for p in base.glob("relatorio_*.pdf")}
        # busca a contribuição mais antiga
        from sqlalchemy import select

        stmt = select(ContribuicaoModel).order_by(ContribuicaoModel.data_pagamento.asc()).limit(1)
        primeira = (await session.execute(stmt)).scalars().first()
        if not primeira:
            return {"status": "no_data"}
        cursor = primeira.data_pagamento.replace(day=1)
        tz = ZoneInfo(settings.app_timezone)
        hoje = datetime.now(tz).date().replace(day=1)
        while cursor <= hoje:
            chave = f"{cursor.year:04d}-{cursor.month:02d}"
            if chave not in existentes:
                await service.gerar_e_salvar(cursor.year, cursor.month)
                gerados.append(chave)
            # avança mês
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1)
    return {"status": "ok", "gerados": gerados}
