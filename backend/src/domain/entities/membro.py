from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class CategoriaMembro(str, Enum):
    COMUNIDADE_DE_VIDA = "comunidade_de_vida"
    COMUNIDADE_DE_ALIANCA = "comunidade_de_alianca"
    OBRA = "obra"
    BENFEITOR = "benfeitor"


@dataclass
class Membro:
    id: UUID | None
    telefone: str
    nome: str
    categoria: CategoriaMembro
    ativo: bool = True
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
