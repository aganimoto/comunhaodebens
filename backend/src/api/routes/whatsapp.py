"""Proxy de status/QR/log do WhatsApp Service + dados da planilha."""
from fastapi import APIRouter, HTTPException

import httpx

from src.config import get_settings

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
        raise HTTPException(
            status_code=502,
            detail="WhatsApp Service indisponível — inicie o WhatsApp service na porta 3000",
        )


# ── Dados da planilha Google ────────────────────────────────────────
@router.get("/sheets")
async def whatsapp_sheets():
    """Retorna dados da planilha Google (abas: Membros, Doações, Pendências)."""
    from src.infrastructure.sheets.sheets_client import SheetsClient

    client = SheetsClient()
    if not client.available:
        return {"available": False, "sheets": {}}

    result = {}
    for sheet_name in ["Membros", "Doações", "Pendências"]:
        try:
            rows = client.get_values(f"{sheet_name}!A1:Z1000")
            result[sheet_name] = rows
        except Exception:
            result[sheet_name] = []

    settings = get_settings()
    spreadsheet_id = settings.google_spreadsheet_id
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit" if spreadsheet_id else None

    return {"available": True, "spreadsheet_url": url, "sheets": result}