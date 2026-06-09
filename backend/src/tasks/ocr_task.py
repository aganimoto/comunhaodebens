"""Task que combina OCR + IA para extrair dados do comprovante.

Fase 4 — a task agora:

* Recebe ``contribuicao_id`` (criada em :class:`ProcessarComprovanteUseCase`
  com status ``PROCESSANDO``) e ``arquivo_id``.
* Faz OCR e IA, persiste o **texto OCR bruto** e o **JSON da IA** em
  ``contribuicoes.ocr_texto_bruto`` / ``ocr_dados_json`` /
  ``ocr_confianca_media`` — **nunca descartados**.
* Atualiza a contribuição existente (mesmo ``id``) com os dados finais
  (valor, data, status, etc.), em vez de criar uma nova. A geração
  definitiva do protocolo acontece aqui.
* Status final:
  * ``CONFIRMADO`` se ``confidence >= LIMIAR_CONFIANCA``
  * ``PENDENTE`` caso contrário (substitui o antigo ``REVISAO``)
  * ``ERRO`` se OCR/IA não retornarem nada utilizável
"""
import asyncio
import logging
import uuid
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from src.application.services.ocr_logger import (
    ETAPA_CLASSIFICANDO,
    ETAPA_CONCLUIDO,
    ETAPA_CONSULTANDO_IA,
    ETAPA_ERRO,
    ETAPA_IMAGEM_RECEBIDA,
    ETAPA_INICIANDO_OCR,
    ETAPA_TEXTO_EXTRAIDO,
    PROGRESSO_ETAPAS,
    criar_logger,
    remover_logger,
)
from src.application.services.protocolo_service import ProtocoloService
from src.application.use_cases.registrar_contribuicao import RegistrarContribuicaoUseCase
from src.config import get_settings
from src.domain.entities.contribuicao import StatusContribuicao
from src.domain.entities.pendencia import MotivoPendencia
from src.infrastructure.database.connection import async_session_factory
from src.infrastructure.database.models import (
    ArquivoModel,
    ContribuicaoModel,
    PendenciaModel,
)
from src.infrastructure.ocr.paddle_ocr_service import PaddleOCRService
from src.infrastructure.sheets.sheets_writer import SheetsWriter
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _criar_ai():
    """Factory que devolve o serviço de IA (Ollama real)."""
    from src.infrastructure.ai.ollama_service import OllamaService

    return OllamaService()


def _criar_ocr():
    """Factory que devolve o serviço de OCR selecionado via Settings.

    A engine é escolhida por ``OCR_ENGINE`` (``easyocr``, ``tesseract`` ou ``paddle``).
    O retorno implementa o mesmo protocolo de :class:`PaddleOCRService`
    (método ``processar(caminho) -> ResultadoOCR``), portanto o pipeline
    é agnóstico à engine escolhida.
    """
    from src.config import get_settings

    engine = get_settings().ocr_engine.lower()

    if engine == "easyocr":
        from src.infrastructure.ocr.easyocr_service import EasyOCRService

        logger.info("OCR engine selecionada: easyocr (deep learning)")
        return EasyOCRService()

    if engine == "tesseract":
        from src.infrastructure.ocr.tesseract_ocr_service import TesseractOCRService

        logger.info("OCR engine selecionada: tesseract (lang=%s)", get_settings().tesseract_lang)
        return TesseractOCRService()

    # Default: PaddleOCR (retrocompatível)
    from src.infrastructure.ocr.paddle_ocr_service import PaddleOCRService
    logger.info("OCR engine selecionada: paddle (padr\u00e3o)")
    return PaddleOCRService()


@celery_app.task(name="processar_ocr_e_ia")
def processar_ocr_e_ia(
    telefone: str,
    membro_nome: str,
    membro_categoria: str,
    caminho_arquivo: str,
    hash_sha256: str,
    contribuicao_id: str | None = None,
    arquivo_id: str | None = None,
) -> dict:
    return asyncio.run(
        _async_processar(
            telefone,
            membro_nome,
            membro_categoria,
            caminho_arquivo,
            hash_sha256,
            contribuicao_id,
            arquivo_id,
        )
    )


async def _async_processar(
    telefone: str,
    membro_nome: str,
    membro_categoria: str,
    caminho_arquivo: str,
    hash_sha256: str,
    contribuicao_id: str | None = None,
    arquivo_id: str | None = None,
) -> dict:
    from src.application.services.classificador_comprovante import eh_comprovante
    from src.infrastructure.sheets.config_reader import ConfigReader

    # ── INICIALIZA LOGGER DE PROGRESSO ──
    # Usa hash_sha256 como identificador para o frontend acompanhar via SSE
    ocr_logger = await criar_logger(hash_sha256)
    ocr_logger.registrar(ETAPA_IMAGEM_RECEBIDA, "andamento", f"Telefone: {telefone}", 0.1)

    ocr = _criar_ocr()

    # OCR em andamento
    ocr_logger.registrar(ETAPA_INICIANDO_OCR, "andamento", "Executando OCR na imagem...", 0.25)
    resultado = ocr.processar(caminho_arquivo)

    # Texto extraído
    texto_preview = resultado.texto_bruto[:100].replace("\n", " ") if resultado.texto_bruto else "(vazio)"
    ocr_logger.registrar(
        ETAPA_TEXTO_EXTRAIDO, "andamento",
        f"{len(resultado.blocos)} blocos, conf={resultado.confianca_media:.1%}",
        0.50,
    )
    logger.info("[OCR %s] Texto extraído: %s", hash_sha256[:8], texto_preview)

    # ── VALIDAÇÃO: só processa se for realmente um comprovante ──
    # A mensagem automática só é enviada se o OCR confirmar que a
    # imagem contém palavras-chave de comprovante + valor R$.
    # Se não for comprovante, marca como ERRO e não notifica.
    ocr_logger.registrar(ETAPA_CLASSIFICANDO, "andamento", "Verificando palavras-chave...", 0.65)
    if not eh_comprovante(resultado.texto_bruto, resultado.confianca_media):
        logger.info(
            "Imagem NÃO é comprovante (conf=%.1f%%, texto=%s...) — "
            "marcando como ERRO sem notificar",
            resultado.confianca_media * 100,
            resultado.texto_bruto[:80].replace("\n", " "),
        )
        ocr_logger.registrar_erro(ETAPA_ERRO, "Imagem não é um comprovante válido")
        async with async_session_factory() as session:
            await _marcar_como_erro(
                session=session,
                contribuicao_id=contribuicao_id,
                telefone=telefone,
                membro_nome=membro_nome,
                ocr_texto_bruto=resultado.texto_bruto,
                ocr_confianca_media=resultado.confianca_media,
            )
        await remover_logger(hash_sha256)
        return {"status": "erro", "motivo": "nao_eh_comprovante"}

    # IA
    ocr_logger.registrar(ETAPA_CONSULTANDO_IA, "andamento", "Consultando Ollama...", 0.80)
    ai = _criar_ai()
    dados = await ai.extrair_de_imagem(caminho_arquivo, resultado.texto_bruto)
    if dados is None:
        ocr_logger.registrar(ETAPA_CONSULTANDO_IA, "andamento", "Fallback: consulta via texto...", 0.85)
        dados = await ai.extrair_de_texto(resultado.texto_bruto)

    config = ConfigReader()
    limiar = await config.get_float("LIMIAR_CONFIANCA", get_settings().limiar_confianca)

    async with async_session_factory() as session:
        if dados is None:
            # Sem retorno da IA — registra pendência e marca a contribuição
            # (se existir) como ERRO
            await _marcar_como_erro(
                session=session,
                contribuicao_id=contribuicao_id,
                telefone=telefone,
                membro_nome=membro_nome,
                ocr_texto_bruto=resultado.texto_bruto,
                ocr_confianca_media=resultado.confianca_media,
            )
            return {"status": "erro"}

        # Adapta V2 -> V1 (o RegistrarContribuicaoUseCase ainda usa V1)
        from src.infrastructure.ai.response_parser import adaptar_v2_para_v1

        parsed = adaptar_v2_para_v1(dados)

        status = (
            StatusContribuicao.CONFIRMADO
            if parsed.confianca >= limiar
            else StatusContribuicao.PENDENTE
        )

        uc = RegistrarContribuicaoUseCase(session)
        contrib = await uc.executar(
            telefone=telefone,
            membro_nome=membro_nome,
            membro_categoria=membro_categoria,
            valor=parsed.valor,
            data_pagamento=parsed.data,
            hora_pagamento=parsed.hora,
            banco=parsed.banco,
            confianca=parsed.confianca,
            hash_sha256=hash_sha256,
            status=status,
        )

        # Atualiza a contribuição PROCESSANDO existente (se houver)
        # com os dados finais + OCR bruto / JSON da IA / confiança média.
        # Esta atualização é idempotente — se a contribuição PROCESSANDO
        # não existir, criamos uma nova (caso legado).
        await _atualizar_ou_criar_contribuicao_final(
            session=session,
            contribuicao_existente_id=contribuicao_id,
            arquivo_id=arquivo_id,
            hash_sha256=hash_sha256,
            telefone=telefone,
            valor=parsed.valor,
            data_pagamento=parsed.data,
            hora_pagamento=parsed.hora,
            banco=parsed.banco,
            confianca=parsed.confianca,
            status=status,
            protocolo=contrib.protocolo,
            ocr_texto_bruto=resultado.texto_bruto,
            ocr_dados_json={
                "valor": float(dados.valor),
                "data_pix": dados.data_pix,
                "favorecido": dados.favorecido,
                "tipo_documento": dados.tipo_documento,
                "confidence": dados.confidence,
            },
            ocr_confianca_media=resultado.confianca_media,
        )

        if status == StatusContribuicao.PENDENTE:
            session.add(
                PendenciaModel(
                    id=uuid.uuid4(),
                    telefone=telefone,
                    contribuicao_id=contrib.id,
                    motivo=MotivoPendencia.IA_BAIXA_CONFIANCA.value,
                )
            )
        await session.commit()

    # ── Concluído ──
    ocr_logger.registrar_conclusao(
        f"Status: {status.value}, Protocolo: {contrib.protocolo}, "
        f"Valor: R$ {contrib.valor:.2f}, Confiança: {contrib.confianca:.0%}"
    )
    await remover_logger(hash_sha256)
    return {"status": status.value, "protocolo": contrib.protocolo}


async def _atualizar_ou_criar_contribuicao_final(
    session,
    contribuicao_existente_id: str | None,
    arquivo_id: str | None,
    hash_sha256: str,
    telefone: str,
    valor: Decimal,
    data_pagamento,
    hora_pagamento,
    banco: str | None,
    confianca: float,
    status: StatusContribuicao,
    protocolo: str,
    ocr_texto_bruto: str,
    ocr_dados_json: dict,
    ocr_confianca_media: float,
) -> None:
    """Atualiza a contribuição PROCESSANDO com os dados finais, ou cria
    uma nova se não existir (fallback de robustez).
    """
    try:
        # 1) Tentar atualizar a PROCESSANDO existente
        if contribuicao_existente_id:
            try:
                cid = UUID(contribuicao_existente_id)
            except ValueError:
                cid = None

            if cid is not None:
                existing = await session.get(ContribuicaoModel, cid)
                if existing is not None and existing.status == StatusContribuicao.PROCESSANDO.value:
                    existing.protocolo = protocolo
                    existing.valor = valor
                    existing.data_pagamento = data_pagamento
                    existing.hora_pagamento = hora_pagamento
                    existing.banco = banco
                    existing.confianca = confianca
                    existing.status = status.value
                    existing.ocr_texto_bruto = ocr_texto_bruto
                    existing.ocr_dados_json = ocr_dados_json
                    existing.ocr_confianca_media = ocr_confianca_media
                    if arquivo_id:
                        try:
                            existing.arquivo_id = UUID(arquivo_id)
                        except ValueError:
                            pass
                    return

        # 2) Fallback: criar nova (não encontrou PROCESSANDO)
        # Verifica se já existe contribuicao com este hash (evita duplicar)
        q = await session.execute(
            select(ContribuicaoModel).where(ContribuicaoModel.hash_imagem == hash_sha256)
        )
        found = q.scalar_one_or_none()
        if found is not None:
            # Já existe uma contribuição final — só atualiza os campos OCR
            found.ocr_texto_bruto = ocr_texto_bruto
            found.ocr_dados_json = ocr_dados_json
            found.ocr_confianca_media = ocr_confianca_media
            return

        nova = ContribuicaoModel(
            id=uuid.uuid4(),
            protocolo=protocolo,
            telefone=telefone,
            valor=valor,
            data_pagamento=data_pagamento,
            hora_pagamento=hora_pagamento,
            banco=banco,
            confianca=confianca,
            status=status.value,
            hash_imagem=hash_sha256,
            arquivo_id=UUID(arquivo_id) if arquivo_id else None,
            ocr_texto_bruto=ocr_texto_bruto,
            ocr_dados_json=ocr_dados_json,
            ocr_confianca_media=ocr_confianca_media,
        )
        session.add(nova)
    except Exception as exc:
        logger.warning("Falha ao atualizar/criar contribuicao final: %s", exc)


async def _marcar_como_erro(
    session,
    contribuicao_id: str | None,
    telefone: str,
    membro_nome: str,
    ocr_texto_bruto: str,
    ocr_confianca_media: float,
) -> None:
    """Marca a contribuição como ERRO e registra pendência."""
    pendencia = PendenciaModel(
        id=uuid.uuid4(),
        telefone=telefone,
        motivo=MotivoPendencia.ERRO_PROCESSAMENTO.value,
    )
    session.add(pendencia)
    SheetsWriter().append_pendencia(
        uuid.uuid4(), telefone, membro_nome, MotivoPendencia.ERRO_PROCESSAMENTO.value
    )

    if contribuicao_id:
        try:
            cid = UUID(contribuicao_id)
        except ValueError:
            cid = None
        if cid is not None:
            existing = await session.get(ContribuicaoModel, cid)
            if existing is not None:
                existing.status = StatusContribuicao.ERRO.value
                existing.ocr_texto_bruto = ocr_texto_bruto
                existing.ocr_confianca_media = ocr_confianca_media

    await session.commit()
