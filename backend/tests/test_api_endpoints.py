"""Testes de integração dos endpoints HTTP principais (login, admin, relatórios)."""
import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app


async def test_health_live():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_login_credenciais_invalidas():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "senha": "x"},
        )
    assert resp.status_code == 401


async def test_login_sucesso_retorna_token(auth_headers, admin_user):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": admin_user.email, "senha": "TesteSenha123"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_dashboard_stats_requer_auth():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/admin/dashboard/stats")
    assert resp.status_code in (401, 403)


async def test_dashboard_stats_com_admin(auth_headers, db_session):
    """Como admin, retorna contadores."""
    from src.infrastructure.database.models import ContribuicaoModel
    from decimal import Decimal
    from datetime import date
    from uuid import uuid4

    db_session.add(
        ContribuicaoModel(
            id=uuid4(),
            protocolo="CDB-20260101-000001",
            telefone="5511999990001",
            valor=Decimal("100.00"),
            data_pagamento=date(2026, 1, 1),
            status="confirmado",
            hash_imagem="h",
        )
    )
    await db_session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/admin/dashboard/stats", headers=auth_headers
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_contribuicoes"] >= 1
    assert body["contribuicoes_confirmadas"] >= 1
    assert body["valor_total_confirmado"] >= 100.0


async def test_relatorios_listar_vazio(auth_headers, tmp_path, monkeypatch):
    monkeypatch.setenv("DEV_RELATORIOS_PATH", str(tmp_path))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/relatorios", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_pendencias_listar(auth_headers):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/pendencias", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_cache_flush_requer_admin(auth_headers):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/v1/admin/cache/flush", headers=auth_headers)
    assert resp.status_code == 200
    assert "deleted_keys" in resp.json()
