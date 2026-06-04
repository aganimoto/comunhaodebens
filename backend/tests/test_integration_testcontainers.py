"""Testes de integração que sobem Postgres+Redis via testcontainers.

Marcados com `@pytest.mark.integration` (skip se Docker indisponível).
"""
import os
from uuid import uuid4
from decimal import Decimal
from datetime import date

import pytest
import pytest_asyncio
from docker.errors import DockerException

# Estes imports são lazy para que a ausência do Docker não impeça o
# carregamento do módulo.
testcontainers = pytest.importorskip("testcontainers")

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from src.config import get_settings
from src.infrastructure.cache import redis_client
from src.infrastructure.database import connection
from src.infrastructure.database.models import Base, ContribuicaoModel


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_container():
    """Sobe um Postgres efêmero."""
    try:
        with PostgresContainer("postgres:16-alpine") as pg:
            yield pg
    except DockerException as exc:
        pytest.skip(f"Docker indisponivel para testcontainers: {exc}")


@pytest.fixture(scope="module")
def redis_container():
    with RedisContainer("redis:7-alpine") as rc:
        yield rc


@pytest_asyncio.fixture
async def pg_engine(pg_container, redis_container, monkeypatch):
    """Engine conectado ao Postgres do container + fakeredis desativado."""
    url = pg_container.get_connection_url().replace("psycopg2", "asyncpg")
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()

    engine = create_async_engine(url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Override do engine global
    prev = (connection.engine, connection.async_session_factory)
    connection.engine = engine
    connection.async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield engine
    finally:
        connection.engine, connection.async_session_factory = prev
        await engine.dispose()


async def test_postgres_persiste_contribuicao(pg_engine):
    """Verifica o caminho real de INSERT/SELECT no Postgres."""
    Session = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with Session() as session:
        c = ContribuicaoModel(
            id=uuid4(),
            protocolo="CDB-20260101-000001",
            telefone="5511999990001",
            valor=Decimal("250.00"),
            data_pagamento=date(2026, 1, 1),
            status="confirmado",
            hash_imagem=uuid4().hex,
        )
        session.add(c)
        await session.commit()

    async with Session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(ContribuicaoModel).where(ContribuicaoModel.protocolo == "CDB-20260101-000001")
        )
        found = result.scalar_one()
        assert float(found.valor) == 250.0
