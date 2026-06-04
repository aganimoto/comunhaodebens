"""Popula dados de exemplo em modo dev.

Uso (após subir o stack com DEV_MODE=true):
    docker compose exec backend python scripts/seed_dev_data.py

Cria: 5 membros, ~20 contribuições confirmadas e 2 pendências,
para popular a aba Membros/Registros/Pendências em dev_data/sheets.json.
"""
from __future__ import annotations

import asyncio
import random
import sys
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from src.config import get_settings
from src.domain.entities.contribuicao import StatusContribuicao
from src.infrastructure.database.connection import async_session_factory
from src.infrastructure.database.models import (
    ContribuicaoModel,
    MembroModel,
    MensagemRecebidaModel,
    PendenciaModel,
)


MEMBROS = [
    ("5511999990001", "Maria Silva", "comunidade_de_vida"),
    ("5511999990002", "João Santos", "comunidade_de_alianca"),
    ("5511999990003", "Ana Pereira", "obra"),
    ("5511999990004", "Carlos Lima", "benfeitor"),
    ("5511999990005", "Dona Tereza", "comunidade_de_vida"),
]

NOMES = [m[1] for m in MEMBROS]
CATS = {m[0]: m[2] for m in MEMBROS}


async def main() -> int:
    settings = get_settings()
    if not settings.dev_mode:
        print(
            "AVISO: DEV_MODE está desligado. Nada foi gravado no banco.",
            file=sys.stderr,
        )
        return 0

    rng = random.Random(42)
    async with async_session_factory() as session:
        # Membros
        for tel, nome, cat in MEMBROS:
            m = MembroModel(
                id=uuid.uuid4(),
                telefone=tel,
                nome=nome,
                categoria=cat,
                ativo=True,
            )
            session.add(m)
        await session.flush()

        # Contribuições
        hoje = datetime.now().date()
        for i in range(20):
            tel, nome = rng.choice(MEMBROS)[:2]
            dias_atras = rng.randint(0, 45)
            data_pag = hoje - timedelta(days=dias_atras)
            valor = Decimal(str(round(rng.uniform(30, 500), 2)))
            status = StatusContribuicao.CONFIRMADO.value
            session.add(
                ContribuicaoModel(
                    id=uuid.uuid4(),
                    protocolo=f"CDB-{data_pag.strftime('%Y%m%d')}-{i + 1:06d}",
                    telefone=tel,
                    valor=valor,
                    data_pagamento=data_pag,
                    hora_pagamento=time(rng.randint(8, 21), rng.choice([0, 15, 30, 45])),
                    banco=rng.choice(["Nubank", "Itaú", "Bradesco", "Santander", "Caixa"]),
                    confianca=Decimal(str(round(rng.uniform(0.85, 0.99), 2))),
                    status=status,
                    hash_imagem=uuid.uuid4().hex,
                )
            )

        # Pendências
        for _ in range(2):
            tel = rng.choice(MEMBROS)[0]
            session.add(
                PendenciaModel(
                    id=uuid.uuid4(),
                    telefone=tel,
                    motivo=rng.choice(["ocr_baixa_confianca", "valor_nao_identificado"]),
                    status="aberto",
                )
            )

        # Mensagens recebidas (algumas)
        for i in range(5):
            tel = rng.choice(MEMBROS)[0]
            session.add(
                MensagemRecebidaModel(
                    telefone=tel,
                    whatsapp_msg_id=f"wamid.dev_{i}",
                    tipo="image",
                    media_path=f"/shared/media/dev_{i}.jpg",
                    status="processada",
                )
            )
        await session.commit()

    print(f"OK: dados de dev populados ({len(MEMBROS)} membros, 20 contribuições, 2 pendências).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
