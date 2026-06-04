import asyncio
import hashlib
import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.identificacao_service import IdentificacaoService
from src.application.services.notificacao_service import NotificacaoService
from src.application.services.protocolo_service import ProtocoloService
from src.config import get_settings
from src.domain.entities.contribuicao import Contribuicao, StatusContribuicao
from src.domain.entities.pendencia import MotivoPendencia, Pendencia, StatusPendencia
from src.domain.events.novo_comprovante_recebido import NovoComprovanteRecebido
from src.domain.value_objects.telefone import Telefone
from src.infrastructure.database.models import (
    AuditoriaModel,
    MensagemRecebidaModel,
    PendenciaModel,
)
from src.infrastructure.database.repositories.contribuicao_repository import ContribuicaoRepository
from src.infrastructure.sheets.config_reader import ConfigReader
from src.infrastructure.sheets.sheets_writer import SheetsWriter
from src.tasks.ocr_task import processar_ocr_e_ia

logger = logging.getLogger(__name__)


def _hash_telefone_log(telefone: str) -> str:
    return hashlib.sha256(telefone.encode()).hexdigest()[:8]


def _hash_duplicidade(file_hash: str, telefone: str, valor_centavos: int, data_iso: str) -> str:
    payload = f"{file_hash}{telefone}{valor_centavos}{data_iso}"
    return hashlib.sha256(payload.encode()).hexdigest()


class ProcessarComprovanteUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._identificacao = IdentificacaoService()
        self._notificacao = NotificacaoService()
        self._protocolo_svc = ProtocoloService(session)
        self._contrib_repo = ContribuicaoRepository(session)
        self._sheets = SheetsWriter()
        self._config = ConfigReader()
        self._settings = get_settings()

    async def executar(self, evento: NovoComprovanteRecebido) -> dict:
        # Validar telefone — se inválido, cria pendência sem crashar
        try:
            telefone = str(Telefone(evento.telefone))
        except ValueError as exc:
            logger.error(
                "Telefone inválido recebido: '%s' — erro: %s",
                evento.telefone, exc,
            )
            try:
                pendencia = PendenciaModel(
                    id=uuid.uuid4(),
                    motivo=MotivoPendencia.ERRO_PROCESSAMENTO.value,
                    status=StatusPendencia.ABERTO.value,
                    observacao=f"Telefone inválido: {evento.telefone} ({exc})",
                )
                self._session.add(pendencia)
                self._session.add(
                    AuditoriaModel(
                        evento="TELEFONE_INVALIDO",
                        detalhes={"telefone_recebido": evento.telefone, "erro": str(exc)},
                        nivel="error",
                    )
                )
                self._sheets.append_pendencia(
                    pendencia.id, evento.telefone, None,
                    MotivoPendencia.ERRO_PROCESSAMENTO.value,
                    f"Telefone inválido: {evento.telefone}",
                )
            except Exception as e2:
                logger.error("Erro ao registrar pendência de telefone inválido: %s", e2)
            return {"status": "erro", "motivo": "telefone_invalido", "detalhe": str(exc)}

        self._session.add(
            MensagemRecebidaModel(
                telefone=telefone,
                whatsapp_msg_id=evento.whatsapp_msg_id,
                tipo=evento.tipo_midia,
                media_path=evento.caminho_arquivo,
                status="recebida",
            )
        )

        membro = await self._identificacao.identificar(telefone)
        if not membro:
            await self._tratar_nao_cadastrado(telefone, evento)
            return {"status": "pendencia", "motivo": "telefone_nao_cadastrado"}

        existente = await self._contrib_repo.get_by_hash_imagem(evento.hash_sha256)
        if existente:
            await self._tratar_duplicata(telefone, membro.nome, existente.protocolo, evento)
            return {"status": "duplicado", "protocolo": existente.protocolo}

        # Em dev_mode, chama o OCR diretamente (síncrono) sem Celery/Redis
        if self._settings.dev_mode:
            logger.info(
                "DEV_MODE: processando OCR síncrono para %s",
                telefone,
            )
            try:
                from src.tasks.ocr_task import _async_processar

                asyncio.create_task(
                    _async_processar(
                        telefone=telefone,
                        membro_nome=membro.nome,
                        membro_categoria=membro.categoria,
                        caminho_arquivo=evento.caminho_arquivo,
                        hash_sha256=evento.hash_sha256,
                    )
                )
                return {"status": "processando", "task": "async"}
            except Exception as exc:
                logger.error("Erro ao iniciar OCR síncrono: %s", exc)
                return {"status": "erro", "motivo": str(exc)}

        # Produção: delega ao Celery via Redis
        processar_ocr_e_ia.delay(
            telefone=telefone,
            membro_nome=membro.nome,
            membro_categoria=membro.categoria,
            caminho_arquivo=evento.caminho_arquivo,
            hash_sha256=evento.hash_sha256,
        )
        return {"status": "processando"}

    async def _tratar_nao_cadastrado(
        self, telefone: str, evento: NovoComprovanteRecebido
    ) -> None:
        pendencia = PendenciaModel(
            id=uuid.uuid4(),
            telefone=telefone,
            motivo=MotivoPendencia.TELEFONE_NAO_CADASTRADO.value,
            status=StatusPendencia.ABERTO.value,
        )
        self._session.add(pendencia)
        self._session.add(
            AuditoriaModel(
                evento="TELEFONE_NAO_CADASTRADO",
                telefone=telefone,
                detalhes={"telefone_hash": _hash_telefone_log(telefone)},
                nivel="warn",
            )
        )
        self._sheets.append_pendencia(
            pendencia.id, telefone, None, MotivoPendencia.TELEFONE_NAO_CADASTRADO.value
        )
        self._sheets.append_auditoria("TELEFONE_NAO_CADASTRADO", "sem OCR", telefone=telefone)
        await self._notificacao.msg_nao_cadastrado(telefone)

    async def _tratar_duplicata(
        self, telefone: str, nome: str, protocolo_original: str, evento: NovoComprovanteRecebido
    ) -> None:
        pendencia_id = uuid.uuid4()
        self._session.add(
            PendenciaModel(
                id=pendencia_id,
                telefone=telefone,
                motivo=MotivoPendencia.COMPROVANTE_DUPLICADO.value,
                observacao=f"Protocolo original: {protocolo_original}",
            )
        )
        self._sheets.append_pendencia(
            pendencia_id,
            telefone,
            nome,
            MotivoPendencia.COMPROVANTE_DUPLICADO.value,
            protocolo_original,
        )
        await self._notificacao.enviar_texto(
            telefone,
            f"Este comprovante já foi registrado (protocolo {protocolo_original}).",
        )