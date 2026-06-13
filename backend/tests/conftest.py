"""Fixtures compartilhadas pelos testes.

Estratégia:
- SQLite em memória não é mais necessário (banco removido, usa Google Sheets).
- Redis usa fakeredis para isolar testes.
- Admin usa JWT direto (payload email + perfil), sem banco.

Em qualquer modo, `dev_mode=true` é ativado para que Sheets/Ollama/
WhatsApp operem sobre os mocks.
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio

# Garante dev_mode antes de qualquer import da app
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-64-characters-for-tests-12345")
os.environ.setdefault("WHATSAPP_WEBHOOK_SECRET", "test-webhook-secret-32-chars-long!!")

from src.config import get_settings
from src.infrastructure.cache import redis_client
from src.infrastructure.sheets.sheets_client import SheetsClient


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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
# Helpers — token JWT (sem banco de dados)
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_headers() -> dict:
    """Retorna headers de autenticação JWT para um admin."""
    from datetime import datetime, timedelta, timezone
    from jose import jwt

    settings = get_settings()
    token = jwt.encode(
        {
            "sub": "admin@test.com",
            "perfil": "administrador",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user_credentials() -> tuple[str, str]:
    """Retorna (email, senha) para login via Sheets."""
    return ("admin@test.com", "TesteSenha123")


@pytest.fixture
def sheets_client() -> SheetsClient:
    return SheetsClient()