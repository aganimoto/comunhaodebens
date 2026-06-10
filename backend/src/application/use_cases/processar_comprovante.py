"""Use case principal: recebe um comprovante PIX e orquestra o pipeline.

Fluxo (Fase 4 — com status PROCESSANDO):

1. Valida telefone
2. Grava ``MensagemRecebidaModel``
3. Identifica membro (Sheets, cache 5 min)
4. **NOVO** — popula ``ArquivoModel`` (idempotente via ``UNIQUE(hash_sha256)``)
5. **NOVO** — cria ``ContribuicaoModel`` com ``status='processando'`` (idempotente
   via ``UNIQUE(hash_imagem)``) — apenas para rastreabilidade
6. Delega o OCR+IA para a ``tasks/ocr_task.py`` (Celery em prod,
   ``asyncio`` em dev) passando o ``arquivo_id`` e o ``contribuicao_id``
7. A task atualiza a contribuição existente com os dados finais
"""
import asyncio
import hashlib
import logging
import os
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.identificacao_service import IdentificacaoService
from src.application.services.notificacao_service import NotificacaoService
from src.application.services.protocolo_service import ProtocoloService
from src.config import get_settings
from src.domain.entities.contribuicao import StatusContribuicao
from src.domain.entities.pendencia import MotivoPendencia, StatusPendencia
from src.domain.events.novo_comprovante_recebido import NovoComprovanteRecebido
from src.domain.value_objects.telefone import Telefone
from src.infrastructure.database.models import (
    ArquivoModel,
    AuditoriaModel,
    ContribuicaoModel,
    MensagemRecebidaModel,
    PendenciaModel,
)
from src.infrastructure.database.repositories.contribuicao_repository import ContribuicaoRepository
from src.infrastructure.sheets.sheets_writer import SheetsWriter
from src.tasks.ocr_task import processar_ocr_e_ia

logger = logging.getLogger(__name__)


def _hash_telefone_log(telefone: str) -> str:
    return hashlib.sha256(telefone.encode()).hexdigest()[:8]


class ProcessarComprovanteUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._identificacao = IdentificacaoService()
        self._notificacao = NotificacaoService()
        self._protocolo_svc = ProtocoloService(session)
        self._contrib_repo = ContribuicaoRepository(session)
        self._sheets = SheetsWriter()
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
        nome_membro = membro.nome if membro else "(não cadastrado)"
        categoria_membro = membro.categoria if membro else "benfeitor"

        if not membro:
            # Apenas registra pendência, NÃO envia mensagem ainda.
            nome_sugestao = evento.nome_sugerido
            observacao = ""
            if nome_sugestao:
                observacao = f"Nome sugerido: {nome_sugestao}"
            pendencia = PendenciaModel(
                id=uuid.uuid4(),
                telefone=telefone,
                motivo=MotivoPendencia.TELEFONE_NAO_CADASTRADO.value,
                status=StatusPendencia.ABERTO.value,
                observacao=observacao or None,
            )
            self._session.add(pendencia)
            self._session.add(
                AuditoriaModel(
                    evento="TELEFONE_NAO_CADASTRADO",
                    telefone=telefone,
                    detalhes={
                        "telefone_hash": _hash_telefone_log(telefone),
                        "nome_sugerido": nome_sugestao,
                    },
                    nivel="warn",
                )
            )
            self._sheets.append_pendencia(
                pendencia.id, telefone, None,
                MotivoPendencia.TELEFONE_NAO_CADASTRADO.value,
                observacao if nome_sugestao else "",
            )

        # Checagem de duplicidade: mesmo hash_imagem já registrado?
        existente = await self._contrib_repo.get_by_hash_imagem(evento.hash_sha256)
        if existente:
            await self._tratar_duplicata(
                telefone, nome_membro, existente.protocolo, evento
            )
            return {"status": "duplicado", "protocolo": existente.protocolo}

        # ── REGISTRA ARQUIVO ──
        arquivo_id = await self._registrar_arquivo(
            caminho=evento.caminho_arquivo,
            hash_sha256=evento.hash_sha256,
        )

        # ── CRIA CONTRIBUIÇÃO PROCESSANDO ──
        contribuicao_id = await self._criar_contribuicao_processando(
            telefone=telefone,
            hash_sha256=evento.hash_sha256,
            arquivo_id=arquivo_id,
        )

        # ── EXECUTA OCR + IA (sempre, mesmo se não cadastrado) ──
        # O OCR é executado para qualquer comprovante recebido. Mesmo que
        # o telefone não seja cadastrado, extraímos os dados para registro.
        # A mensagem automática só será enviada depois da validação.
        logger.info(
            "Iniciando OCR para %s (membro=%s, contrib=%s)",
            telefone, nome_membro, contribuicao_id,
        )

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
                        contribuicao_id=str(contribuicao_id),
                        arquivo_id=str(arquivo_id) if arquivo_id else None,
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
                contribuicao_id=str(contribuicao_id),
                arquivo_id=str(arquivo_id) if arquivo_id else None,
            )

        if not membro:
            return {"status": "pendencia", "motivo": "telefone_nao_cadastrado", "aguardando_ocr": True}
        return {
            "status": "processando",
            "contribuicao_id": str(contribuicao_id),
        }

    async def _registrar_arquivo(
        self, caminho: str, hash_sha256: str
    ) -> uuid.UUID | None:
        """Registra (ou reaproveita) o arquivo em ``arquivos``.

        Idempotente graças ao ``UNIQUE(hash_sha256)``. Retorna o ``id`` do
        registro (novo ou existente).
        """
        try:
            existing = await self._session.execute(
                select(ArquivoModel).where(ArquivoModel.hash_sha256 == hash_sha256)
            )
            found = existing.scalar_one_or_none()
            if found is not None:
                return found.id

            tamanho = None
            try:
                tamanho = os.path.getsize(caminho)
            except OSError:
                pass

            mime = None
            lower = caminho.lower()
            if lower.endswith((".jpg", ".jpeg")):
                mime = "image/jpeg"
            elif lower.endswith(".png"):
                mime = "image/png"
            elif lower.endswith(".pdf"):
                mime = "application/pdf"

            nome_original = os.path.basename(caminho) or None
            arquivo = ArquivoModel(
                id=uuid.uuid4(),
                nome_original=nome_original,
                caminho=caminho,
                hash_sha256=hash_sha256,
                tamanho_bytes=tamanho,
                mime_type=mime,
            )
            self._session.add(arquivo)
            await self._session.flush()
            return arquivo.id
        except Exception as exc:
            logger.warning("Falha ao registrar arquivo %s: %s", caminho, exc)
            return None

    async def _criar_contribuicao_processando(
        self,
        telefone: str,
        hash_sha256: str,
        arquivo_id: uuid.UUID | None,
    ) -> uuid.UUID | None:
        """Cria uma contribuição com status ``PROCESSANDO``.

        Esta contribuição é o "slot" que será atualizado pela task de
        OCR/IA com os dados finais (valor, data, status, OCR bruto/JSON).

        Se já existir uma contribuição com o mesmo ``hash_imagem``
        (situação possível em caso de reentrega do webhook), reutiliza
        a existente em vez de criar uma nova.
        """
        try:
            existing = await self._session.execute(
                select(ContribuicaoModel).where(
                    ContribuicaoModel.hash_imagem == hash_sha256
                )
            )
            found = existing.scalar_one_or_none()
            if found is not None:
                return found.id

            # Gera um protocolo provisório único (placeholder) — será
            # regenerado pela task de OCR/IA se for o caso. Como
            # protocolo tem UNIQUE, usamos UUID truncado.
            placeholder_protocolo = f"PROC-{uuid.uuid4().hex[:10].upper()}"

            nova = ContribuicaoModel(
                id=uuid.uuid4(),
                protocolo=placeholder_protocolo,
                telefone=telefone,
                # valor=0 e data_pagamento=hoje são placeholders; a
                # task de OCR/IA vai atualizar para os valores reais.
                valor=0,
                data_pagamento=datetime.utcnow().date(),
                confianca=0,
                status=StatusContribuicao.PROCESSANDO.value,
                hash_imagem=hash_sha256,
                arquivo_id=arquivo_id,
            )
            self._session.add(nova)
            await self._session.flush()
            return nova.id
        except Exception as exc:
            logger.warning(
                "Falha ao criar contribuicao PROCESSANDO (hash=%s...): %s",
                hash_sha256[:8], exc,
            )
            return None

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
