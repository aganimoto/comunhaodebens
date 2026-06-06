"""Endpoints REST para Contribuições — Fase 6 inclui Reprocessamento e Ver Comprovante."""
import os
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import Perfil, get_current_user, require_perfil
from src.application.use_cases.reprocessar_comprovante import ReprocessarComprovante
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import ArquivoModel, ContribuicaoModel
from src.infrastructure.database.repositories.contribuicao_repository import (
    ContribuicaoRepository,
)

router = APIRouter(prefix="/contribuicoes", tags=["contribuicoes"])


class ContribuicaoOut(BaseModel):
    id: UUID
    protocolo: str
    telefone: str
    valor: float
    data_pagamento: str
    status: str
    confianca: float
    ocr_texto_bruto: str | None = None
    ocr_dados_json: dict | None = None
    ocr_confianca_media: float | None = None
    arquivo_id: UUID | None = None


def _to_out(c: ContribuicaoModel) -> ContribuicaoOut:
    return ContribuicaoOut(
        id=c.id,
        protocolo=c.protocolo,
        telefone=c.telefone,
        valor=float(c.valor),
        data_pagamento=c.data_pagamento.isoformat(),
        status=c.status,
        confianca=float(c.confianca) if c.confianca is not None else 0.0,
        ocr_texto_bruto=c.ocr_texto_bruto,
        ocr_dados_json=c.ocr_dados_json,
        ocr_confianca_media=float(c.ocr_confianca_media) if c.ocr_confianca_media is not None else None,
        arquivo_id=c.arquivo_id,
    )


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
        "items": [_to_out(c) for c in items],
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
        raise HTTPException(404, "Não encontrada")
    return _to_out(c)


# ── Fase 6: Reprocessamento manual ─────────────────────────────────────
class ReprocessarResponse(BaseModel):
    status: str
    protocolo: str
    confianca: float | None = None


@router.post("/{contribuicao_id}/reprocessar", response_model=ReprocessarResponse)
async def reprocessar(
    contribuicao_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR, Perfil.FINANCEIRO)),
):
    """Reprocessa um comprovante a partir da imagem original.

    Reexecuta OCR + IA sem precisar reenviar pelo WhatsApp. Idempotente
    no banco (atualiza o mesmo registro); gera nova linha na aba
    ``Doações`` do Sheets para auditoria.
    """
    try:
        uc = ReprocessarComprovante(session)
        resultado = await uc.executar(contribuicao_id)
        return ReprocessarResponse(**resultado)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


# ── Fase 6: Ver comprovante (retorna a imagem) ─────────────────────────
@router.get("/{contribuicao_id}/comprovante")
async def ver_comprovante(
    contribuicao_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    _user=Depends(get_current_user),
):
    """Retorna a imagem original do comprovante.

    Localiza o arquivo via ``ContribuicaoModel.arquivo_id`` (Fase 4).
    Se a contribuição não tiver arquivo associado, devolve 404.
    """
    contrib = await session.get(ContribuicaoModel, contribuicao_id)
    if not contrib:
        raise HTTPException(404, "Contribuição não encontrada")
    if not contrib.arquivo_id:
        raise HTTPException(
            404, "Comprovante sem arquivo associado (legado pré-Fase 4)"
        )
    arquivo = await session.get(ArquivoModel, contrib.arquivo_id)
    if not arquivo or not arquivo.caminho or not os.path.exists(arquivo.caminho):
        raise HTTPException(404, "Arquivo físico não encontrado no disco")
    mime = arquivo.mime_type or "application/octet-stream"
    return FileResponse(arquivo.caminho, media_type=mime, filename=arquivo.nome_original or "comprovante")


# ── PATCH existente (retrocompat) ──────────────────────────────────────
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
    repo = ContribuicaoRepository(session)
    c = await repo.get_by_id(contribuicao_id)
    if not c:
        raise HTTPException(404, "Não encontrada")
    if body.status:
        # Aceita tanto o status novo quanto o legado REVISAO
        from src.domain.entities.contribuicao import StatusContribuicao

        c.status = StatusContribuicao(body.status)
    if body.banco is not None:
        c.banco = body.banco
    return await repo.update(c)
