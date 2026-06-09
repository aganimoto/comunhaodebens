from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import admin, auth, contribuicoes, health, ocr_progress, pendencias, relatorios, webhooks, whatsapp
from src.config import get_settings

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CDB Shalom API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(webhooks.router, prefix="/api/v1")
    app.include_router(contribuicoes.router, prefix="/api/v1")
    app.include_router(pendencias.router, prefix="/api/v1")
    app.include_router(relatorios.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(whatsapp.router, prefix="/api/v1")
    app.include_router(ocr_progress.router, prefix="/api/v1")
    return app


app = create_app()
