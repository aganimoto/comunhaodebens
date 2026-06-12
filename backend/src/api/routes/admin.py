"""Endpoints administrativos (cache, dashboard) — dados do Google Sheets."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.middleware.auth import Perfil, require_perfil
from src.infrastructure.cache.redis_client import cache_delete_pattern
from src.infrastructure.sheets.sheets_client import SheetsClient

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Cache ──
@router.post("/cache/flush")
async def flush_cache(
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR)),
):
    deleted = await cache_delete_pattern("membros:*")
    deleted += await cache_delete_pattern("config:*")
    return {"deleted_keys": deleted}


# ── Dashboard ──
class ContribuicaoResumo(BaseModel):
    protocolo: str
    data: str
    nome: str
    valor: str
    status: str
    confianca: str


class DashboardStats(BaseModel):
    total_contribuicoes: int
    contribuicoes_confirmadas: int
    contribuicoes_pendentes: int
    pendencias_abertas: int
    valor_total_confirmado: float
    valor_hoje: float
    valor_mes: float
    ultimas_contribuicoes: list[ContribuicaoResumo]


def _ler_doacoes(client: SheetsClient) -> list[list[str]]:
    rows = client.get_values("Doações!A1:J5000")
    if not rows or len(rows) < 2:
        return []
    return rows[1:]  # Pular cabeçalho


def _ler_pendencias(client: SheetsClient) -> list[list[str]]:
    rows = client.get_values("Pendências!A1:G5000")
    if not rows or len(rows) < 2:
        return []
    return rows[1:]


@router.get("/dashboard/stats")
async def dashboard_stats(
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR, Perfil.FINANCEIRO, Perfil.CONSULTA)),
):
    client = SheetsClient()
    if not client.available:
        raise HTTPException(503, "Google Sheets indisponível")

    doacoes = _ler_doacoes(client)
    pendencias = _ler_pendencias(client)

    total = len(doacoes)
    confirmadas = 0
    pendentes = 0
    valor_total = 0.0

    ultimas = []
    for row in reversed(doacoes[-20:]):  # Últimas 20
        if len(row) < 9:
            continue
        status = row[7].strip().upper()
        if status == "CONFIRMADO":
            confirmadas += 1
            try:
                valor_total += float(row[4].replace("R$", "").replace(" ", "").replace(",", "."))
            except (ValueError, IndexError):
                pass
        elif status == "PENDENTE":
            pendentes += 1
        ultimas.append(ContribuicaoResumo(
            protocolo=row[0],
            data=row[1],
            nome=row[2],
            valor=row[4],
            status=status,
            confianca=row[8],
        ))

    pendencias_abertas = sum(1 for p in pendencias if len(p) >= 6 and p[5].strip().lower() == "aberto")

    # Valor hoje e mês
    from datetime import date
    hoje = date.today()
    mes_atual = hoje.month
    ano_atual = hoje.year
    valor_hoje = 0.0
    valor_mes = 0.0

    for row in doacoes:
        if len(row) < 8:
            continue
        status = row[7].strip().upper()
        if status != "CONFIRMADO":
            continue
        try:
            v = float(row[4].replace("R$", "").replace(" ", "").replace(",", "."))
        except (ValueError, IndexError):
            continue
        try:
            data_str = row[1].strip()
            data = date.fromisoformat(data_str)
            if data == hoje:
                valor_hoje += v
            if data.month == mes_atual and data.year == ano_atual:
                valor_mes += v
        except (ValueError, IndexError):
            pass

    return DashboardStats(
        total_contribuicoes=total,
        contribuicoes_confirmadas=confirmadas,
        contribuicoes_pendentes=pendentes,
        pendencias_abertas=pendencias_abertas,
        valor_total_confirmado=round(valor_total, 2),
        valor_hoje=round(valor_hoje, 2),
        valor_mes=round(valor_mes, 2),
        ultimas_contribuicoes=ultimas[-5:],
    )


# ── Backup ──
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
    from src.tasks.backup_task import backup_diario
    async_result = backup_diario.delay()
    return {"status": "enqueued", "task_id": str(async_result.id)}


@router.get("/backup/list")
async def list_backups(
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR, Perfil.FINANCEIRO)),
):
    from src.tasks.backup_task import listar_backups
    return listar_backups.apply().get()