"""Entidade de domínio :class:`Contribuicao`.

Status possíveis a partir da Fase 4 do projeto de evolução:

* ``PROCESSANDO`` — criada quando o comprovante foi recebido e o OCR/IA
  está em andamento. Rastreabilidade para o painel.
* ``CONFIRMADO`` — extração OK (confidence >= limiar).
* ``PENDENTE`` — confidence abaixo do limiar ou pagamento precisa de
  revisão manual.
* ``DUPLICADO`` — mesmo ``hash_imagem`` já registrado.
* ``ERRO`` — falha técnica (OCR/IA sem retorno, JSON inválido, etc.).

``REVISAO`` é mantido como alias de ``PENDENTE`` por uma versão para que
qualquer referência em código ou dados antigos continue funcionando.
"""
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from uuid import UUID


class StatusContribuicao(str, Enum):
    PROCESSANDO = "processando"
    CONFIRMADO = "confirmado"
    PENDENTE = "pendente"
    DUPLICADO = "duplicado"
    ERRO = "erro"

    # Alias retrocompatível (Fase 4): REVISAO -> PENDENTE
    @classmethod
    def _missing_(cls, value: str):  # type: ignore[override]
        if isinstance(value, str) and value.lower() == "revisao":
            return cls.PENDENTE
        return None


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
    # Campos novos (Fase 4) — auditoria/observabilidade
    ocr_texto_bruto: str | None = None
    ocr_dados_json: dict | None = None
    ocr_confianca_media: float | None = None
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
