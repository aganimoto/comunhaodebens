from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from uuid import UUID


class StatusContribuicao(str, Enum):
    CONFIRMADO = "confirmado"
    REVISAO = "revisao"
    DUPLICADO = "duplicado"
    ERRO = "erro"


@dataclass
class Contribuicao:
    id: UUID | None
    protocolo: str
    membro_id: UUID | None
    telefone: str
    valor: Decimal
    data_pagamento: date
    hora_pagamento: time | None
    banco: str | None
    confianca: float
    status: StatusContribuicao
    hash_imagem: str
    arquivo_id: UUID | None = None
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
