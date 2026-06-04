"""Testes dos mocks de dev (Sheets, Ollama, WhatsApp)."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.infrastructure.dev_mocks import (
    DevOllamaService,
    DevSheetsClient,
    DevWhatsAppClient,
    criar_ollama_service,
    criar_sheets_client,
    criar_whatsapp_client,
    reset_dev_data,
)


def test_criar_sheets_em_dev_mode(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    client = criar_sheets_client()
    assert isinstance(client, DevSheetsClient)
    assert client.available is True


def test_criar_ollama_em_dev_mode(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    svc = criar_ollama_service()
    assert isinstance(svc, DevOllamaService)


def test_criar_whatsapp_em_dev_mode(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    cli = criar_whatsapp_client()
    assert isinstance(cli, DevWhatsAppClient)


def test_sheets_padrao(tmp_path, monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    from src.infrastructure import dev_mocks

    monkeypatch.setattr(dev_mocks, "_DATA_DIR", tmp_path)
    client = DevSheetsClient()
    membros = client.get_values("Membros!A1:D100")
    assert len(membros) >= 1
    # Headers das abas obrigatórias
    assert "Registros" in client._data
    assert "Pendências" in client._data


def test_sheets_append_persiste(tmp_path, monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    from src.infrastructure import dev_mocks

    monkeypatch.setattr(dev_mocks, "_DATA_DIR", tmp_path)
    c1 = DevSheetsClient()
    c1.append_row("Teste", ["a", "b"])
    # Reinstancia lendo do disco
    c2 = DevSheetsClient()
    assert c2.get_values("Teste!A1:B1") == [["a", "b"]]


def test_sheets_batch_update_adiciona_aba(tmp_path, monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    from src.infrastructure import dev_mocks

    monkeypatch.setattr(dev_mocks, "_DATA_DIR", tmp_path)
    c = DevSheetsClient()
    c.batch_update([{"addSheet": {"properties": {"title": "NovaAba"}}}])
    assert "NovaAba" in c._data


async def test_ollama_extrair_de_imagem():
    svc = DevOllamaService()
    r = await svc.extrair_de_imagem("comprovante_001")
    assert r.valor > 0
    assert 0.0 <= r.confianca <= 1.0
    assert r.banco in DevOllamaService.BANCOS


async def test_ollama_determinismo():
    """Mesma chave → mesmo resultado."""
    svc = DevOllamaService()
    a = await svc.extrair_de_texto("input-x")
    b = await svc.extrair_de_texto("input-x")
    assert a.valor == b.valor
    assert a.banco == b.banco


async def test_whatsapp_client_grava_outbox(tmp_path, monkeypatch):
    from src.infrastructure import dev_mocks

    monkeypatch.setattr(dev_mocks, "_DATA_DIR", tmp_path)
    cli = DevWhatsAppClient()
    await cli.send("5511999990001", "Olá")
    await cli.send("5511999990001", "Tudo bem?")
    # Reinstancia lendo do disco
    cli2 = DevWhatsAppClient()
    assert len(cli2._sent) == 2
    assert cli2._sent[0]["mensagem"] == "Olá"
