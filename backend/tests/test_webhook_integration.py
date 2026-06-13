"""Testes de integração do webhook WhatsApp (FastAPI)."""
import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _payload(telefone="5511999990001", evento="NOVO_COMPROVANTE_RECEBIDO",
             msg_id=None, hash_img=None):
    return {
        "evento": evento,
        "telefone": telefone,
        "whatsapp_msg_id": msg_id or f"wamid_{uuid4().hex[:8]}",
        "timestamp": "2026-06-02T14:32:00",
        "tipo_midia": "image",
        "caminho_arquivo": "/tmp/fake.jpg",
        "hash_sha256": hash_img or hashlib.sha256(uuid4().bytes).hexdigest(),
    }


async def test_webhook_hmac_invalido_retorna_401(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        body = json.dumps(_payload()).encode()
        resp = await client.post(
            "/api/v1/webhooks/whatsapp",
            content=body,
            headers={"Content-Type": "application/json", "X-HMAC-Signature": "invalido"},
        )
    assert resp.status_code == 401


async def test_webhook_telefone_nao_cadastrado_gera_pendencia(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    # popula planilha mock com 1 membro via fallback local
    from src.infrastructure.sheets.sheets_client import _load_fallback, _save_fallback
    data = _load_fallback()
    data.setdefault("Membros", [])
    data["Membros"].append(["5511999990001", "Maria", "comunidade_de_vida", "TRUE"])
    _save_fallback(data)

    from src.config import get_settings

    secret = get_settings().whatsapp_webhook_secret
    body = json.dumps(_payload(telefone="5511000000000")).encode()
    sig = _sign(body, secret)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/webhooks/whatsapp",
            content=body,
            headers={"Content-Type": "application/json", "X-HMAC-Signature": sig},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pendencia"
    assert data["motivo"] == "telefone_nao_cadastrado"


async def test_webhook_evento_ignorado(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    from src.config import get_settings

    secret = get_settings().whatsapp_webhook_secret
    body = json.dumps(_payload(evento="OUTRO_EVENTO")).encode()
    sig = _sign(body, secret)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/webhooks/whatsapp",
            content=body,
            headers={"Content-Type": "application/json", "X-HMAC-Signature": sig},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ignored": True}
