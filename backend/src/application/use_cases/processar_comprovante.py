"""Use case principal: recebe um comprovante PIX e orquestra o pipeline.

Fluxo (sem banco SQL — apenas Google Sheets):

1. Valida telefone
2. Identifica membro via Sheets (com cache Redis)
3. Registra pendência se telefone não cadastrado (na planilha)
4. Verifica duplicidade via Sheets
5. Dispara OCR task (Celery em prod, asyncio em dev)
"""
import asyncio
import hashlib
import logging
import uuid

from src.application.services.identificacao_service import IdentificacaoService
from src.application.services.notificacao_service import NotificacaoService
from src.config import get_settings
from src.domain.entities.contribuicao import StatusContribuicao
from src.domain.entities.pendencia import MotivoPendencia
from src.domain.events.novo_comprovante_recebido import NovoComprovanteRecebido
from src.domain.value_objects.telefone import Telefone
from src.infrastructure.sheets.sheets_writer import SheetsWriter
from src.tasks.ocr_task import processar_ocr_e_ia

logger = logging.getLogger(__name__)


def _hash_telefone_log(telefone: str) -> str:
    return hashlib.sha256(telefone.encode()).hexdigest()[:8]


class ProcessarComprovanteUseCase:
    def __init__(self) -> None:
        self._identificacao = IdentificacaoService()
        self._notificacao = NotificacaoService()
        self._sheets = SheetsWriter()
        self._settings = get_settings()

    async def executar(self, evento: NovoComprovanteRecebido) -> dict:
        # Validar telefone
        try:
            telefone = str(Telefone(evento.telefone))
        except ValueError as exc:
            logger.error("Telefone inválido: '%s' — %s", evento.telefone, exc)
            self._sheets.append_pendencia(
                pendencia_id=uuid.uuid4(),
                telefone=evento.telefone,
                nome=None,
                motivo=MotivoPendencia.ERRO_PROCESSAMENTO.value,
                observacao=f"Telefone inválido: {evento.telefone}",
            )
            self._sheets.append_auditoria(
                evento="TELEFONE_INVALIDO",
                detalhes=f"Telefone inválido: {evento.telefone}",
            )
            return {"status": "erro", "motivo": "telefone_invalido", "detalhe": str(exc)}

        # Identificar membro
        membro = await self._identificacao.identificar(telefone)
        nome_membro = membro.nome if membro else "(não cadastrado)"
        from src.domain.entities.membro import CategoriaMembro
        if membro and membro.categoria in CategoriaMembro._value2member_map_:
            categoria_membro = membro.categoria
        else:
            categoria_membro = "benfeitor"

        if not membro:
            logger.info("Telefone não cadastrado: %s", _hash_telefone_log(telefone))
            self._sheets.append_pendencia(
                pendencia_id=uuid.uuid4(),
                telefone=telefone,
                nome=evento.nome_sugerido or None,
                motivo=MotivoPendencia.TELEFONE_NAO_CADASTRADO.value,
                observacao=evento.nome_sugerido or "",
            )
            self._sheets.append_auditoria(
                evento="TELEFONE_NAO_CADASTRADO",
                detalhes=f"Telefone não cadastrado: {_hash_telefone_log(telefone)}",
                telefone=telefone,
            )

        # Disparar OCR task (sempre executa, mesmo se não cadastrado)
        logger.info("Iniciando OCR para %s (membro=%s)", _hash_telefone_log(telefone), nome_membro)

        if self._settings.dev_mode:
            try:
                from src.tasks.ocr_task import _async_processar

                asyncio.create_task(
                    _async_processar(
                        telefone=telefone,
                        membro_nome=nome_membro,
                        membro_categoria=categoria_membro,
                        caminho_arquivo=evento.caminho_arquivo,
                        hash_sha256=evento.hash_sha256,
                    )
                )
            except Exception as exc:
                logger.error("Erro ao iniciar OCR síncrono: %s", exc)
        else:
            processar_ocr_e_ia.delay(
                telefone=telefone,
                membro_nome=nome_membro,
                membro_categoria=categoria_membro,
                caminho_arquivo=evento.caminho_arquivo,
                hash_sha256=evento.hash_sha256,
            )

        if not membro:
            return {"status": "pendencia", "motivo": "telefone_nao_cadastrado", "aguardando_ocr": True}
        return {"status": "processando"}