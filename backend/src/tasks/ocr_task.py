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

from src.application.services.debug_logger import (
    MODULO_CLASSIFICADOR,
    MODULO_IA,
    MODULO_OCR,
    get_debug_logger,
)
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
    from src.infrastructure.ai.ollama_service import OllamaService
    return OllamaService()


def _criar_ocr():
    from src.config import get_settings
    engine = get_settings().ocr_engine.lower()
    if engine == "easyocr":
        from src.infrastructure.ocr.easyocr_service import EasyOCRService
        logger.info("OCR engine: easyocr")
        return EasyOCRService()
    if engine == "tesseract":
        from src.infrastructure.ocr.tesseract_ocr_service import TesseractOCRService
        logger.info("OCR engine: tesseract")
        return TesseractOCRService()
    from src.infrastructure.ocr.paddle_ocr_service import PaddleOCRService
    logger.info("OCR engine: paddle")
    return PaddleOCRService()


@celery_app.task(name="processar_ocr_e_ia")
def processar_ocr_e_ia(
    telefone: str, membro_nome: str, membro_categoria: str,
    caminho_arquivo: str, hash_sha256: str,
    contribuicao_id: str | None = None,
    arquivo_id: str | None = None,
) -> dict:
    return asyncio.run(
        _async_processar(telefone, membro_nome, membro_categoria,
                         caminho_arquivo, hash_sha256,
                         contribuicao_id, arquivo_id)
    )


async def _async_processar(
    telefone: str, membro_nome: str, membro_categoria: str,
    caminho_arquivo: str, hash_sha256: str,
    contribuicao_id: str | None = None,
    arquivo_id: str | None = None,
) -> dict:
    from src.application.services.classificador_comprovante import eh_comprovante
    from src.infrastructure.sheets.config_reader import ConfigReader

    _debug = get_debug_logger()
    ocr_logger = await criar_logger(hash_sha256)
    ocr_logger.registrar(ETAPA_IMAGEM_RECEBIDA, "andamento", f"Telefone: {telefone}", 0.1)

    _debug.info(MODULO_OCR, f"Iniciando pipeline OCR", {
        "hash": hash_sha256[:12],
        "telefone": telefone,
        "membro": membro_nome,
        "arquivo": caminho_arquivo.split("\\")[-1] if "\\" in caminho_arquivo else caminho_arquivo.split("/")[-1],
    })

    try:
        ocr = _criar_ocr()
        ocr_logger.registrar(ETAPA_INICIANDO_OCR, "andamento", "Executando OCR na imagem...", 0.25)
        _debug.info(MODULO_OCR, "Chamando OCR.processar()...")

        resultado = ocr.processar(caminho_arquivo)

        _debug.info(MODULO_OCR, "OCR.processar() OK", {
            "blocos": len(resultado.blocos),
            "confianca": round(resultado.confianca_media, 3),
            "chars": len(resultado.texto_bruto),
        })
    except Exception as e:
        _debug.error(MODULO_OCR, f"Falha no OCR: {e}", {"erro": str(e)})
        logger.error("Falha no OCR: %s", e, exc_info=True)
        async with async_session_factory() as session:
            await _marcar_como_erro(session, contribuicao_id, telefone, membro_nome, "", 0.0)
        ocr_logger.registrar_erro(ETAPA_ERRO, f"Falha no OCR: {e}")
        await remover_logger(hash_sha256)
        return {"status": "erro", "motivo": f"ocr_falhou: {e}"}

    texto_preview = resultado.texto_bruto[:100].replace("\n", " ") if resultado.texto_bruto else "(vazio)"
    ocr_logger.registrar(ETAPA_TEXTO_EXTRAIDO, "andamento",
                         f"{len(resultado.blocos)} blocos, conf={resultado.confianca_media:.1%}", 0.50)
    logger.info("[OCR %s] Texto: %s", hash_sha256[:8], texto_preview)

    # Classificação
    ocr_logger.registrar(ETAPA_CLASSIFICANDO, "andamento", "Verificando palavras-chave...", 0.65)
    if not eh_comprovante(resultado.texto_bruto, resultado.confianca_media):
        logger.info("NÃO é comprovante (conf=%.1f%%), marcando ERRO", resultado.confianca_media * 100)
        _debug.warn(MODULO_CLASSIFICADOR, "Imagem rejeitada: não é comprovante", {
            "confianca": round(resultado.confianca_media, 3),
            "texto_preview": resultado.texto_bruto[:120],
        })
        ocr_logger.registrar_erro(ETAPA_ERRO, "Imagem não é um comprovante válido")
        async with async_session_factory() as session:
            await _marcar_como_erro(session, contribuicao_id, telefone, membro_nome,
                                    resultado.texto_bruto, resultado.confianca_media)
        await remover_logger(hash_sha256)
        return {"status": "erro", "motivo": "nao_eh_comprovante"}

    # IA
    _debug.info(MODULO_IA, "Iniciando consulta IA")
    ocr_logger.registrar(ETAPA_CONSULTANDO_IA, "andamento", "Consultando Ollama...", 0.80)
    try:
        ai = _criar_ai()
        dados = await ai.extrair_de_imagem(caminho_arquivo, resultado.texto_bruto)
        if dados is None:
            _debug.warn(MODULO_IA, "Fallback: consulta via texto")
            ocr_logger.registrar(ETAPA_CONSULTANDO_IA, "andamento", "Fallback via texto...", 0.85)
            dados = await ai.extrair_de_texto(resultado.texto_bruto)
        _debug.info(MODULO_IA, "IA respondeu", {
            "dados": str(dados)[:200] if dados else "None",
        })
    except Exception as e:
        _debug.error(MODULO_IA, f"Falha na IA: {e}", {"erro": str(e)})
        logger.error("Falha na IA: %s", e, exc_info=True)
        dados = None

    config = ConfigReader()
    limiar = await config.get_float("LIMIAR_CONFIANCA", get_settings().limiar_confianca)

    async with async_session_factory() as session:
        if dados is None:
            _debug.error(MODULO_IA, "IA sem retorno — marcando ERRO")
            await _marcar_como_erro(session, contribuicao_id, telefone, membro_nome,
                                    resultado.texto_bruto, resultado.confianca_media)
            ocr_logger.registrar_erro(ETAPA_ERRO, "IA não retornou dados")
            await remover_logger(hash_sha256)
            return {"status": "erro"}

        from src.infrastructure.ai.response_parser import adaptar_v2_para_v1
        parsed = adaptar_v2_para_v1(dados)

        status = (
            StatusContribuicao.CONFIRMADO
            if parsed.confianca >= limiar
            else StatusContribuicao.PENDENTE
        )

        uc = RegistrarContribuicaoUseCase(session)
        contrib = await uc.executar(
            telefone=telefone, membro_nome=membro_nome,
            membro_categoria=membro_categoria,
            valor=parsed.valor, data_pagamento=parsed.data,
            hora_pagamento=parsed.hora, banco=parsed.banco,
            confianca=parsed.confianca, hash_sha256=hash_sha256,
            status=status,
        )

        await _atualizar_ou_criar_contribuicao_final(
            session=session, contribuicao_existente_id=contribuicao_id,
            arquivo_id=arquivo_id, hash_sha256=hash_sha256,
            telefone=telefone, valor=parsed.valor,
            data_pagamento=parsed.data, hora_pagamento=parsed.hora,
            banco=parsed.banco, confianca=parsed.confianca,
            status=status, protocolo=contrib.protocolo,
            ocr_texto_bruto=resultado.texto_bruto,
            ocr_dados_json={
                "valor": float(dados.valor), "data_pix": dados.data_pix,
                "favorecido": dados.favorecido,
                "tipo_documento": dados.tipo_documento,
                "confidence": dados.confidence,
            },
            ocr_confianca_media=resultado.confianca_media,
        )

        if status == StatusContribuicao.PENDENTE:
            session.add(PendenciaModel(
                id=uuid.uuid4(), telefone=telefone,
                contribuicao_id=contrib.id,
                motivo=MotivoPendencia.IA_BAIXA_CONFIANCA.value,
            ))
        await session.commit()

    _debug.info(MODULO_OCR, "Pipeline concluído com sucesso", {
        "status": status.value, "protocolo": contrib.protocolo,
        "valor": float(contrib.valor), "confianca": float(contrib.confianca),
    })
    ocr_logger.registrar_conclusao(
        f"Status: {status.value}, Protocolo: {contrib.protocolo}, "
        f"Valor: R$ {contrib.valor:.2f}, Confiança: {contrib.confianca:.0%}"
    )
    await remover_logger(hash_sha256)
    return {"status": status.value, "protocolo": contrib.protocolo}


async def _atualizar_ou_criar_contribuicao_final(
    session, contribuicao_existente_id: str | None,
    arquivo_id: str | None, hash_sha256: str,
    telefone: str, valor: Decimal, data_pagamento, hora_pagamento,
    banco: str | None, confianca: float,
    status: StatusContribuicao, protocolo: str,
    ocr_texto_bruto: str, ocr_dados_json: dict,
    ocr_confianca_media: float,
) -> None:
    try:
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

        q = await session.execute(
            select(ContribuicaoModel).where(ContribuicaoModel.hash_imagem == hash_sha256)
        )
        found = q.scalar_one_or_none()
        if found is not None:
            found.ocr_texto_bruto = ocr_texto_bruto
            found.ocr_dados_json = ocr_dados_json
            found.ocr_confianca_media = ocr_confianca_media
            return

        nova = ContribuicaoModel(
            id=uuid.uuid4(), protocolo=protocolo, telefone=telefone,
            valor=valor, data_pagamento=data_pagamento,
            hora_pagamento=hora_pagamento, banco=banco,
            confianca=confianca, status=status.value,
            hash_imagem=hash_sha256,
            arquivo_id=UUID(arquivo_id) if arquivo_id else None,
            ocr_texto_bruto=ocr_texto_bruto,
            ocr_dados_json=ocr_dados_json,
            ocr_confianca_media=ocr_confianca_media,
        )
        session.add(nova)
    except Exception as exc:
        logger.warning("Falha ao atualizar contribuicao: %s", exc)


async def _marcar_como_erro(
    session, contribuicao_id: str | None,
    telefone: str, membro_nome: str,
    ocr_texto_bruto: str, ocr_confianca_media: float,
) -> None:
    logger.warning("Marcando como ERRO: telefone=%s, membro=%s", telefone, membro_nome)
    pendencia = PendenciaModel(
        id=uuid.uuid4(), telefone=telefone,
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