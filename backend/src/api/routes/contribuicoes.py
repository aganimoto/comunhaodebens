"""Endpoints REST para Contribuições — dados vindos do Google Sheets."""
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.middleware.auth import Perfil, get_current_user, require_perfil
from src.infrastructure.sheets.sheets_client import SheetsClient

router = APIRouter(prefix="/contribuicoes", tags=["contribuicoes"])


class ContribuicaoOut(BaseModel):
    protocolo: str
    data: str
    nome: str
    categoria: str
    valor: str
    favorecido: str
    telefone: str
    status: str
    confianca: str
    ocr_preview: str | None = None


@router.get("")
async def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    _user=Depends(get_current_user),
):
    client = SheetsClient()
    if not client.available:
        raise HTTPException(503, "Google Sheets indisponível")

    rows = client.get_values("Doações!A:J")
    if not rows or len(rows) < 2:
        return {"items": [], "total": 0, "skip": skip, "limit": limit}

    # Primeira linha é o cabeçalho, pular
    items = []
    for row in rows[1:]:
        if len(row) < 10:
            continue
        item = ContribuicaoOut(
            protocolo=row[0],
            data=row[1],
            nome=row[2],
            categoria=row[3],
            valor=row[4],
            favorecido=row[5],
            telefone=row[6],
            status=row[7],
            confianca=row[8],
            ocr_preview=row[9] if len(row) > 9 else None,
        )
        if status and item.status.lower() != status.lower():
            continue
        items.append(item)

    total = len(items)
    items = items[skip : skip + limit]

    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{protocolo}")
async def detalhe(
    protocolo: str,
    _user=Depends(get_current_user),
):
    client = SheetsClient()
    if not client.available:
        raise HTTPException(503, "Google Sheets indisponível")

    rows = client.get_values("Doações!A:J")
    if not rows or len(rows) < 2:
        raise HTTPException(404, "Não encontrada")

    for row in rows[1:]:
        if len(row) >= 8 and row[0] == protocolo:
            return ContribuicaoOut(
                protocolo=row[0],
                data=row[1],
                nome=row[2],
                categoria=row[3],
                valor=row[4],
                favorecido=row[5],
                telefone=row[6],
                status=row[7],
                confianca=row[8],
                ocr_preview=row[9] if len(row) > 9 else None,
            )

    raise HTTPException(404, "Não encontrada")


class ReprocessarResponse(BaseModel):
    status: str
    protocolo: str


@router.post("/{protocolo}/reprocessar", response_model=ReprocessarResponse)
async def reprocessar(
    protocolo: str,
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR, Perfil.FINANCEIRO)),
):
    """Reprocessar não disponível sem banco SQL.
    O comprovante precisa ser reenviado pelo WhatsApp.
    """
    raise HTTPException(400, "Reprocessamento manual não disponível. Reenvie o comprovante pelo WhatsApp.")