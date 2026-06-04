"""Testes do script create_admin (criação idempotente do primeiro admin)."""
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.infrastructure.database import connection
from src.infrastructure.database.models import UsuarioAdminModel


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
SCRIPT = SCRIPTS_DIR / "create_admin.py"


def _patch_settings(monkeypatch, email, senha, perfil="administrador"):
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", email)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", senha)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PERFIL", perfil)
    # limpa cache do lru_cache
    from src.config import get_settings

    get_settings.cache_clear()


async def _count_admins() -> int:
    async with connection.async_session_factory() as session:
        r = await session.execute(select(UsuarioAdminModel))
        return len(r.scalars().all())


async def test_cria_admin_se_nao_existe(monkeypatch):
    email = f"admin_{uuid4().hex[:8]}@test.com"
    _patch_settings(monkeypatch, email, "SenhaForte1!")
    # Simula invocação via asyncio
    from src.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        "sys.argv",
        ["create_admin.py", "--email", email, "--senha", "SenhaForte1!"],
    )
    rc = await _run_script_async()
    assert rc == 0
    assert await _count_admins() == 1


async def test_idempotente_sem_force(monkeypatch):
    email = f"admin_{uuid4().hex[:8]}@test.com"
    _patch_settings(monkeypatch, email, "SenhaForte1!")
    # cria
    monkeypatch.setattr("sys.argv", ["create_admin.py", "--email", email, "--senha", "SenhaForte1!"])
    await _run_script_async()
    assert await _count_admins() == 1
    # segunda vez sem --force
    await _run_script_async()
    assert await _count_admins() == 1


async def test_force_atualiza_senha(monkeypatch):
    email = f"admin_{uuid4().hex[:8]}@test.com"
    _patch_settings(monkeypatch, email, "SenhaAntiga1!")
    monkeypatch.setattr("sys.argv", ["create_admin.py", "--email", email, "--senha", "SenhaAntiga1!"])
    await _run_script_async()
    # atualiza
    monkeypatch.setattr("sys.argv", [
        "create_admin.py", "--email", email, "--senha", "NovaSenha123!", "--force"
    ])
    await _run_script_async()
    async with connection.async_session_factory() as session:
        user = (await session.execute(
            select(UsuarioAdminModel).where(UsuarioAdminModel.email == email)
        )).scalar_one()
        assert user.senha_hash.startswith("$2")  # bcrypt
        # verifica que a nova senha autentica
        from passlib.context import CryptContext

        pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
        assert pwd.verify("NovaSenha123!", user.senha_hash)
        assert not pwd.verify("SenhaAntiga1!", user.senha_hash)


async def test_rejeita_senha_curta(monkeypatch):
    email = f"admin_{uuid4().hex[:8]}@test.com"
    _patch_settings(monkeypatch, email, "x")
    monkeypatch.setattr("sys.argv", ["create_admin.py", "--email", email, "--senha", "123"])
    rc = await _run_script_async()
    assert rc == 2


async def _run_script_async() -> int:
    """Executa o script como módulo num subprocess é caro; em vez disso,
    importamos e chamamos main() diretamente."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("create_admin_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    import asyncio

    return await mod.main()
