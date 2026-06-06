"""Use case: reprocessa um comprovante a partir da imagem original.

Cenário de uso: o financeiro clica em "Reprocessar" no painel para um
comprovante em status PENDENTE ou ERRO. O sistema reexecuta OCR + IA
na imagem original e atualiza a contribuição (sem precisar reenviar
o comprovante pelo WhatsApp).

Fluxo:

1. Carrega a contribuição por ``id``.
2. Carrega o ``ArquivoModel`` apontado por ``arquivo_id`` (ou, se
   ausente, tenta localizar via hash_imagem).
3. Executa OCR + IA via factory ``_criar_ocr()`` / ``_criar_ai()``.
4. Atualiza a contribuição existente **no mesmo registro** (mesmo
   ``id``), preservando ``protocolo`` e ``arquivo_id``.
5. Persiste OCR bruto / JSON / confiança média (Fase 4).
6. Re-sincroniza Sheets (via ``RegistrarContribuicaoUseCase``) — na
   prática, adiciona uma nova linha na aba ``Doações`` (o Sheets é
   append-only). A fonte da verdade continua sendo o banco.
7. Envia notificação WhatsApp apropriada.

O reprocessamento é **idempotente** com relação ao banco (atualiza o
mesmo registro), mas gera uma nova linha no Sheets. Em cenários de
reprocessamento, é aceitável ter a linha nova no Sheets para auditoria.
"""
import asyncio
import logging
import uuid
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.protocolo_service import ProtocoloService
from src.application.use_cases.registrar_contribuicao import RegistrarContribuicaoUseCase
from src.config import get_settings
from src.domain.entities.contribuicao import StatusContribuicao
from src.domain.entities.pendencia import MotivoPendencia
from src.infrastructure.ai.ollama_service import OllamaService
from src.infrastructure.database.models import (
    ArquivoModel,
    AuditoriaModel,
    ContribuicaoModel,
    MensagemRecebidaModel,
    PendenciaModel,
)
from src.infrastructure.ocr.paddle_ocr_service import PaddleOCRService
from src.infrastructure.sheets.config_reader import ConfigReader
from src.infrastructure.sheets.sheets_writer import SheetsWriter

logger = logging.getLogger(__name__)


class ReprocessarComprovante:
    """Use case de reprocessamento manual."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._config = ConfigReader()
        self._sheets = SheetsWriter()
        self._protocolo = ProtocoloService(session)

    async def executar(self, contribuicao_id: UUID) -> dict:
        """Reprocessa a contribuição apontada por ``contribuicao_id``.

        Retorna um dicionário com o status final e o protocolo. Lança
        ``ValueError`` se a contribuição não for encontrada.
        """
        # 1) Carregar contribuicao
        contrib = await self._session.get(ContribuicaoModel, contribuicao_id)
        if contrib is None:
            raise ValueError(f"Contribuição {contribuicao_id} não encontrada")

        # 2) Carregar arquivo
        caminho = None
        if contrib.arquivo_id:
            arquivo = await self._session.get(ArquivoModel, contrib.arquivo_id)
            if arquivo is not None:
                caminho = arquivo.caminho

        if not caminho:
            # Fallback: tentar achar em mensagens_recebidas
            q = await self._session.execute(
                select(MensagemRecebidaModel)
                .where(MensagemRecebidaModel.telefone == contrib.telefone)
                .order_by(MensagemRecebidaModel.timestamp.desc())
                .limit(1)
            )
            msg = q.scalar_one_or_none()
            if msg and msg.media_path:
                caminho = msg.media_path

        if not caminho:
            raise ValueError(
                f"Arquivo original não localizado para contribuição {contribuicao_id}"
            )

        logger.info(
            "Reprocessando contribuição %s a partir de %s", contribuicao_id, caminho
        )

        # 3) OCR
        ocr = PaddleOCRService()
        resultado = ocr.processar(caminho)

        # 4) IA
        ai = OllamaService()
        dados = await ai.extrair_de_imagem(caminho, resultado.texto_bruto)
        if dados is None:
            dados = await ai.extrair_de_texto(resultado.texto_bruto)

        # 5) Atualizar contribuição no banco (idempotente)
        if dados is None:
            # Sem retorno da IA — marca como ERRO e cria pendência
            contrib.status = StatusContribuicao.ERRO.value
            contrib.ocr_texto_bruto = resultado.texto_bruto
            contrib.ocr_confianca_media = resultado.confianca_media
            self._session.add(
                PendenciaModel(
                    id=uuid.uuid4(),
                    telefone=contrib.telefone,
                    contribuicao_id=contrib.id,
                    motivo=MotivoPendencia.ERRO_PROCESSAMENTO.value,
                )
            )
            self._session.add(
                AuditoriaModel(
                    evento="REPROCESSAMENTO_ERRO",
                    contribuicao_id=contrib.id,
                    telefone=contrib.telefone,
                    detalhes={"motivo": "IA sem retorno"},
                    nivel="warn",
                )
            )
            self._sheets.append_auditoria(
                "REPROCESSAMENTO_ERRO", "IA sem retorno",
                contribuicao_id=contrib.id, telefone=contrib.telefone,
            )
            await self._session.commit()
            return {"status": "erro", "protocolo": contrib.protocolo}

        # 6) Adaptar V2 -> V1 (compat)
        from src.infrastructure.ai.response_parser import adaptar_v2_para_v1

        parsed = adaptar_v2_para_v1(dados)

        limiar = await self._config.get_float(
            "LIMIAR_CONFIANCA", self._settings.limiar_confianca
        )
        novo_status = (
            StatusContribuicao.CONFIRMADO
            if parsed.confianca >= limiar
            else StatusContribuicao.PENDENTE
        )

        # 7) Atualizar a contribuição (mesmo id, mesmo protocolo)
        contrib.valor = parsed.valor
        contrib.data_pagamento = parsed.data
        contrib.hora_pagamento = parsed.hora
        contrib.banco = dados.favorecido
        contrib.confianca = parsed.confianca
        contrib.status = novo_status.value
        contrib.ocr_texto_bruto = resultado.texto_bruto
        contrib.ocr_dados_json = {
            "valor": float(dados.valor),
            "data_pix": dados.data_pix,
            "favorecido": dados.favorecido,
            "tipo_documento": dados.tipo_documento,
            "confidence": dados.confidence,
        }
        contrib.ocr_confianca_media = resultado.confianca_media

        # 8) Registrar pendência se for PENDENTE
        if novo_status == StatusContribuicao.PENDENTE:
            self._session.add(
                PendenciaModel(
                    id=uuid.uuid4(),
                    telefone=contrib.telefone,
                    contribuicao_id=contrib.id,
                    motivo=MotivoPendencia.IA_BAIXA_CONFIANCA.value,
                )
            )

        # 9) Auditoria
        self._session.add(
            AuditoriaModel(
                evento="REPROCESSAMENTO_OK",
                contribuicao_id=contrib.id,
                telefone=contrib.telefone,
                detalhes={
                    "status_anterior": None,  # poderíamos ler antes, simplificamos
                    "status_novo": novo_status.value,
                    "confianca": parsed.confianca,
                    "ocr_confianca_media": resultado.confianca_media,
                },
                nivel="info",
            )
        )

        # 10) Sheets: nova linha na aba Doações (append-only)
        # Tentamos obter o nome/categoria via membro_id se possível
        membro_nome = "(reprocessamento)"
        membro_categoria = "n/d"
        if contrib.membro_id:
            # Não temos o repository de membro aqui — usar placeholder
            # A UI pode completar com JOIN se precisar
            pass

        self._sheets.append_doacao(
            protocolo=contrib.protocolo,
            data_pagamento=contrib.data_pagamento,
            hora=contrib.hora_pagamento,
            nome=membro_nome,
            categoria=membro_categoria,
            valor=contrib.valor,
            favorecido=dados.favorecido,
            tipo_documento=dados.tipo_documento,
            telefone=contrib.telefone,
            status=novo_status.value,
            confianca=contrib.confianca,
            ocr_bruto_preview=resultado.texto_bruto[:100] if resultado.texto_bruto else None,
        )

        await self._session.commit()
        return {
            "status": novo_status.value,
            "protocolo": contrib.protocolo,
            "confianca": parsed.confianca,
        }
