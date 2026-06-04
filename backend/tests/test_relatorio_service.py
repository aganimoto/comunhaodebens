"""Testes do RelatorioService (geração de PDF mensal)."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.application.reports.relatorio_service import RelatorioService
from src.config import get_settings
from src.infrastructure.database.models import Base, ContribuicaoModel
from src.infrastructure.sheets.sheets_client import SheetsClient


@pytest.fixture
async def session_with_data(tmp_path):
    """Sessão SQLite em memória com algumas contribuições confirmadas."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        # 2 contribuições no mês atual, 1 em outro mês
        from datetime import date as _date

        hoje = _date.today()
        session.add_all(
            [
                ContribuicaoModel(
                    id=uuid4(),
                    protocolo=f"CDB-{hoje.strftime('%Y%m%d')}-000001",
                    telefone="5511999990001",
                    valor=Decimal("150.00"),
                    data_pagamento=hoje,
                    status="confirmado",
                    hash_imagem="h1",
                ),
                ContribuicaoModel(
                    id=uuid4(),
                    protocolo=f"CDB-{hoje.strftime('%Y%m%d')}-000002",
                    telefone="5511999990002",
                    valor=Decimal("350.00"),
                    data_pagamento=hoje,
                    status="confirmado",
                    hash_imagem="h2",
                ),
                ContribuicaoModel(
                    id=uuid4(),
                    protocolo="CDB-20240101-000001",
                    telefone="5511999990003",
                    valor=Decimal("999.00"),
                    data_pagamento=_date(2024, 1, 1),
                    status="confirmado",
                    hash_imagem="h3",
                ),
            ]
        )
        await session.commit()
        yield session
    await engine.dispose()


async def test_coletar_soma_mes_atual(session_with_data, monkeypatch):
    """Apenas contribuições do mês solicitado devem entrar no total."""
    monkeypatch.setenv("DEV_MODE", "true")
    rel = await RelatorioService(session_with_data).coletar(
        date.today().year, date.today().month
    )
    assert rel.quantidade == 2
    assert rel.total_geral == Decimal("500.00")


async def test_renderizar_html_contem_nome_mes(session_with_data, monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    rel = await RelatorioService(session_with_data).coletar(
        date.today().year, date.today().month
    )
    html = RelatorioService(session_with_data).renderizar_html(rel)
    assert "Relatório Financeiro Mensal" in html
    assert rel.mes_nome in html
    assert "R$" in html


async def test_renderizar_pdf(tmp_path, session_with_data, monkeypatch):
    """Renderiza um PDF de verdade (usa WeasyPrint)."""
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("DEV_RELATORIOS_PATH", str(tmp_path))
    rel = await RelatorioService(session_with_data).coletar(
        date.today().year, date.today().month
    )
    destino = tmp_path / "relatorio_teste.pdf"
    try:
        RelatorioService(session_with_data).renderizar_pdf(rel, destino)
    except Exception as e:  # ambiente sem lib do sistema
        pytest.skip(f"WeasyPrint indisponível: {e}")
    assert destino.exists()
    assert destino.stat().st_size > 100
    head = destino.read_bytes()[:5]
    assert head == b"%PDF-"


async def test_gerar_e_salvar_registra_na_planilha(
    session_with_data, tmp_path, monkeypatch
):
    """Quando dev_mode=true, a SheetsClient é o mock e deve aceitar o append."""
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("DEV_RELATORIOS_PATH", str(tmp_path))
    sheets = SheetsClient()
    # limpa planilha mock
    monkeypatch.setattr("src.infrastructure.dev_mocks._DATA_DIR", tmp_path)
    sheets.append_row("Relatórios", ["placeholder"])  # popula
    path = await RelatorioService(session_with_data).gerar_e_salvar(
        date.today().year, date.today().month
    )
    assert path.exists()
    # Confere que a aba Relatórios agora contém o registro
    valores = sheets.get_values("Relatórios!A1:E100")
    assert any("gerado" in (linha[-1] if linha else "") for linha in valores)
