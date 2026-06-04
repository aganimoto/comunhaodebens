from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class MotivoPendencia(str, Enum):
    TELEFONE_NAO_CADASTRADO = "telefone_nao_cadastrado"
    OCR_BAIXA_CONFIANCA = "ocr_baixa_confianca"
    IA_BAIXA_CONFIANCA = "ia_baixa_confianca"
    COMPROVANTE_DUPLICADO = "comprovante_duplicado"
    VALOR_NAO_IDENTIFICADO = "valor_nao_identificado"
    ERRO_PROCESSAMENTO = "erro_processamento"


class StatusPendencia(str, Enum):
    ABERTO = "aberto"
    EM_ANALISE = "em_analise"
    RESOLVIDO = "resolvido"


@dataclass
class Pendencia:
    id: UUID | None
    motivo: MotivoPendencia
    status: StatusPendencia = StatusPendencia.ABERTO
    telefone: str | None = None
    contribuicao_id: UUID | None = None
    observacao: str | None = None
    resolvido_por: str | None = None
    resolvido_em: datetime | None = None
    criado_em: datetime | None = None
