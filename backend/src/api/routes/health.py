import httpx
from fastapi import APIRouter

from src.config import get_settings
from src.infrastructure.cache.redis_client import get_redis
from src.infrastructure.sheets.sheets_client import SheetsClient

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    services = await _check_services()
    statuses = [s["status"] for s in services.values()]
    overall = "ok" if all(s == "ok" for s in statuses) else "degraded"
    if any(s == "down" for s in statuses):
        overall = "down"
    return {"status": overall, "services": services}


@router.get("/health/live")
async def live():
    return {"status": "ok"}


@router.get("/health/ready")
async def ready():
    services = await _check_services()
    critical = ["redis"]
    if all(services.get(k, {}).get("status") == "ok" for k in critical):
        return {"status": "ok"}
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=503, content={"status": "not_ready", "services": services})


async def _check_services() -> dict:
    settings = get_settings()
    result = {}

    # Redis
    try:
        r = get_redis()
        await r.ping()
        result["redis"] = {"status": "ok"}
    except Exception as e:
        result["redis"] = {"status": "down", "error": str(e)}

    # Ollama (opcional)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            result["ollama"] = {"status": "ok" if resp.status_code == 200 else "degraded"}
    except Exception as e:
        result["ollama"] = {"status": "down", "error": str(e)}

    # Google Sheets
    sheets = SheetsClient()
    result["google_sheets"] = {
        "status": "ok" if sheets.available else "degraded",
    }

    # WhatsApp Service
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.whatsapp_service_url}/health")
            result["whatsapp"] = {"status": "ok" if resp.status_code == 200 else "degraded"}
    except Exception as e:
        result["whatsapp"] = {"status": "down", "error": str(e)}

    return result