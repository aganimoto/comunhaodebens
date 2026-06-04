"""Proxy de status/QR/log do WhatsApp Service + dados da planilha."""
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import MensagemRecebidaModel, AuditoriaModel

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.get("/status")
async def whatsapp_status():
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.whatsapp_service_url}/whatsapp/status")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return {"status": "disconnected"}


@router.get("/qr")
async def whatsapp_qr():
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.whatsapp_service_url}/whatsapp/qr")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return {"status": "disconnected", "qr": None}


@router.post("/reconnect")
async def whatsapp_reconnect():
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{settings.whatsapp_service_url}/whatsapp/reconnect")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="WhatsApp Service indisponível — inicie o WhatsApp service na porta 3000")


# ── Log de mensagens recebidas ──────────────────────────────────────
class LogMensagem(BaseModel):
    id: str
    telefone: str
    timestamp: str
    tipo: str
    status: str
    media_path: str | None = None


@router.get("/log")
async def whatsapp_log(limit: int = 50):
    """Retorna as últimas mensagens recebidas via WhatsApp."""
    from src.infrastructure.database.connection import engine

    async with engine.begin() as conn:
        result = await conn.execute(
            select(MensagemRecebidaModel)
            .order_by(desc(MensagemRecebidaModel.timestamp))
            .limit(limit)
        )
        rows = result.scalars().all()

    logs = []
    for r in rows:
        try:
            logs.append(
                LogMensagem(
                    id=str(r.id),
                    telefone=r.telefone if hasattr(r, 'telefone') else str(r),
                    timestamp=r.timestamp.isoformat() if hasattr(r, 'timestamp') and r.timestamp else "",
                    tipo=r.tipo if hasattr(r, 'tipo') else "desconhecido",
                    status=r.status if hasattr(r, 'status') else "recebida",
                    media_path=r.media_path if hasattr(r, 'media_path') else None,
                )
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Erro ao serializar log: %s | row=%s", e, r)
    return logs


# ── Dados da planilha Google ────────────────────────────────────────
@router.get("/sheets")
async def whatsapp_sheets():
    """Retorna dados da planilha Google (abas: Membros, Registros, Pendências)."""
    from src.infrastructure.sheets.sheets_client import SheetsClient

    client = SheetsClient()
    if not client.available:
        return {"available": False, "sheets": {}}

    result = {}
    for sheet_name in ["Membros", "Registros", "Pendências"]:
        try:
            rows = client.get_values(f"{sheet_name}!A1:Z1000")
            result[sheet_name] = rows
        except Exception:
            result[sheet_name] = []

    settings = get_settings()
    spreadsheet_id = settings.google_spreadsheet_id
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit" if spreadsheet_id else None

    return {"available": True, "spreadsheet_url": url, "sheets": result}
