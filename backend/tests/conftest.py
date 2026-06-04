"""Fixtures compartilhadas pelos testes.

Estratégia:
- Modo padrão (sem marker integration): usa SQLite em memória + fakeredis
  → testes rápidos, sem dependências externas.
- Marcados com `@pytest.mark.integration`: sobem Postgres+Redis via
  testcontainers, exercitam o caminho real.

Em qualquer modo, `dev_mode=true` é ativado para que Sheets/Ollama/
WhatsApp operem sobre os mocks.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio

# Garante dev_mode antes de qualquer import da app
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-64-characters-for-tests-12345")
os.environ.setdefault("WHATSAPP_WEBHOOK_SECRET", "test-webhook-secret-32-chars-long!!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.config import get_settings
from src.infrastructure.cache import redis_client
from src.infrastructure.database import connection
from src.infrastructure.database.models import Base, UsuarioAdminModel
from src.infrastructure.sheets.sheets_client import SheetsClient


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Sessão assíncrona por teste (SQLite em memória, isolado)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def db_engine():
    """SQLite em memória isolada por teste (rápido e sem rede)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Substitui o engine global usado pela aplicação
    prev_engine = connection.engine
    prev_factory = connection.async_session_factory
    connection.engine = engine
    connection.async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield engine
    finally:
        connection.engine = prev_engine
        connection.async_session_factory = prev_factory
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(db_engine) -> async_sessionmaker:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    SessionLocal = async_sessionmaker(db_engine, expire_on_commit=False)
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


# ---------------------------------------------------------------------------
# Redis fake (fakeredis) — autouse para todos os testes
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _patch_redis(monkeypatch):
    import fakeredis.aioredis as fr

    fake = fr.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "_pool", fake)

    def _override():
        return fake

    monkeypatch.setattr(redis_client, "get_redis", _override)
    yield


# ---------------------------------------------------------------------------
# Sheets fallback local — reset entre testes
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_sheets_fallback(tmp_path, monkeypatch):
    """Cada teste roda com fallback sheets em diretório isolado."""
    from src.infrastructure.sheets import sheets_client as sc

    monkeypatch.setattr(sc, "_FALLBACK_DIR", tmp_path)
    fallback_file = tmp_path / "sheets_fallback.json"
    if fallback_file.exists():
        fallback_file.unlink()
    yield
    if fallback_file.exists():
        fallback_file.unlink()


# ---------------------------------------------------------------------------
# Helpers — usuário admin + token JWT
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def admin_user(db_engine) -> UsuarioAdminModel:
    from passlib.context import CryptContext

    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    Session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with Session() as session:
        user = UsuarioAdminModel(
            id=uuid.uuid4(),
            email=f"admin_{uuid.uuid4().hex[:8]}@test.com",
            senha_hash=pwd.hash("TesteSenha123"),
            perfil="administrador",
            ativo=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user_credentials(admin_user):
    """Retorna (email, senha) para o admin criado pela fixture admin_user."""
    return (admin_user.email, "TesteSenha123")


@pytest_asyncio.fixture
async def auth_headers(admin_user) -> dict:
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    settings = get_settings()
    token = jwt.encode(
        {
            "sub": admin_user.email,
            "perfil": admin_user.perfil,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sheets_client() -> SheetsClient:
    return SheetsClient()
