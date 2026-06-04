"""Inicializa SQLite local para desenvolvimento sem Docker.

Uso (na pasta backend, com venv ativo):
    python scripts/bootstrap_local_db.py
    python scripts/create_admin.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEV_DB = BACKEND_ROOT / "dev_data" / "local.db"

os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{DEV_DB.as_posix()}",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "dev-jwt-secret-change-me-64-chars-minimum-for-hs256",
)
os.environ.setdefault("WHATSAPP_WEBHOOK_SECRET", "dev-webhook-secret-32-chars-long!!")
os.environ.setdefault("DEV_RELATORIOS_PATH", str(BACKEND_ROOT / "dev_data" / "relatorios"))
os.environ.setdefault("DEV_BACKUP_PATH", str(BACKEND_ROOT / "dev_data" / "backups"))

sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.ext.asyncio import create_async_engine

from src.infrastructure.database.models import Base


async def main() -> None:
    DEV_DB.parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print(f"Banco SQLite criado em: {DEV_DB}")


if __name__ == "__main__":
    asyncio.run(main())
