"""Task que processa comprovante usando apenas Google Sheets como storage.

Pipeline completo:
1. OCR extrai texto da imagem
2. Classificador valida por palavras-chave + valor
3. Regex extrai valor, data, favorecido
4. Salva na planilha (aba Doações)
5. Notifica via WhatsApp
"""
import asyncio
import logging
import uuid
from datetime import date

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
    criar_logger,
    remover_logger,
)
from src.application.services.notificacao_service import NotificacaoService
from src.config import get_settings
from src.domain.entities.contribuicao import StatusContribuicao
from src.domain.entities.pendencia import MotivoPendencia
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


def _gerar_protocolo() -> str:
    """Gera protocolo único usando timestamp + hash curto."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(get_settings().app_timezone)
    now = datetime.now(tz)
    hash_curto = uuid.uuid4().hex[:6].upper()
    return f"{now.strftime('%Y%m%d')}-{hash_curto}"


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

    _debug = get_debug_logger()
    ocr_logger = await criar_logger(hash_sha256)
    ocr_logger.registrar(ETAPA_IMAGEM_RECEBIDA, "andamento", f"Telefone: {telefone}", 0.1)

    _debug.info(MODULO_OCR, "Iniciando pipeline OCR", {
        "hash": hash_sha256[:12],
        "telefone": telefone,
        "membro": membro_nome,
        "arquivo": caminho_arquivo.split("\\")[-1] if "\\" in caminho_arquivo else caminho_arquivo.split("/")[-1],
    })

    # ── 1. OCR ─────────────────────────────────────────────────────────
    try:
        ocr = _criar_ocr()
        ocr_logger.registrar(ETAPA_INICIANDO_OCR, "andamento", "Executando OCR na imagem...", 0.25)
        resultado = ocr.processar(caminho_arquivo)
        _debug.info(MODULO_OCR, "OCR OK", {
            "blocos": len(resultado.blocos),
            "confianca": round(resultado.confianca_media, 3),
            "chars": len(resultado.texto_bruto),
        })
    except Exception as e:
        _debug.error(MODULO_OCR, f"Falha no OCR: {e}", {"erro": str(e)})
        logger.error("Falha no OCR: %s", e, exc_info=True)
        _registrar_erro(telefone, membro_nome, "", 0.0, ocr_logger, hash_sha256,
                        MotivoPendencia.ERRO_PROCESSAMENTO.value)
        return {"status": "erro", "motivo": f"ocr_falhou: {e}"}

    texto_preview = resultado.texto_bruto[:100].replace("\n", " ") if resultado.texto_bruto else "(vazio)"
    ocr_logger.registrar(ETAPA_TEXTO_EXTRAIDO, "andamento",
                         f"{len(resultado.blocos)} blocos, conf={resultado.confianca_media:.1%}", 0.50)
    logger.info("[OCR %s] Texto: %s", hash_sha256[:8], texto_preview)

    # ── 2. Classificação (palavras-chave) ──────────────────────────────
    ocr_logger.registrar(ETAPA_CLASSIFICANDO, "andamento", "Verificando palavras-chave...", 0.65)
    if not eh_comprovante(resultado.texto_bruto, resultado.confianca_media):
        logger.info("NÃO é comprovante (conf=%.1f%%)", resultado.confianca_media * 100)
        _debug.warn(MODULO_CLASSIFICADOR, "Imagem rejeitada", {
            "confianca": round(resultado.confianca_media, 3),
            "texto_preview": resultado.texto_bruto[:120],
        })
        _registrar_erro(telefone, membro_nome, resultado.texto_bruto, resultado.confianca_media,
                        ocr_logger, hash_sha256, MotivoPendencia.ERRO_PROCESSAMENTO.value)
        return {"status": "erro", "motivo": "nao_eh_comprovante"}

    # ── 3. Extração via regex ──────────────────────────────────────────
    _debug.info(MODULO_IA, "Extraindo dados via regex")
    ocr_logger.registrar(ETAPA_CONSULTANDO_IA, "andamento",
                         "Extraindo dados do comprovante...", 0.80)
    try:
        ai = _criar_ai()
        dados_extraidos = await ai.extrair_dados(resultado.texto_bruto)
        if dados_extraidos is None:
            _debug.error(MODULO_IA, "Regex não conseguiu extrair valor")
            _registrar_erro(telefone, membro_nome, resultado.texto_bruto, resultado.confianca_media,
                            ocr_logger, hash_sha256, MotivoPendencia.VALOR_NAO_IDENTIFICADO.value)
            return {"status": "erro"}

        _debug.info(MODULO_IA, "Dados extraídos", {
            "valor": float(dados_extraidos["valor"]),
            "data": str(dados_extraidos.get("data_pagamento", "")),
            "favorecido": dados_extraidos.get("favorecido"),
            "confidence": dados_extraidos["confidence"],
        })
    except Exception as e:
        _debug.error(MODULO_IA, f"Falha na extração: {e}", {"erro": str(e)})
        logger.error("Falha na extração: %s", e, exc_info=True)
        _registrar_erro(telefone, membro_nome, resultado.texto_bruto, 0.0,
                        ocr_logger, hash_sha256, MotivoPendencia.ERRO_PROCESSAMENTO.value)
        return {"status": "erro"}

    # ── 4. Determinar status ──────────────────────────────────────────
    from src.infrastructure.sheets.config_reader import ConfigReader

    config = ConfigReader()
    limiar = await config.get_float("LIMIAR_CONFIANCA", get_settings().limiar_confianca)

    status = (
        StatusContribuicao.CONFIRMADO
        if dados_extraidos["confidence"] >= limiar
        else StatusContribuicao.PENDENTE
    )

    # ── 5. Protocolo ──────────────────────────────────────────────────
    protocolo = _gerar_protocolo()

    # ── 6. Salvar na planilha ─────────────────────────────────────────
    sheets = SheetsWriter()
    data_pag = dados_extraidos.get("data_pagamento") or date.today()

    sheets.append_doacao(
        protocolo=protocolo,
        data_pagamento=data_pag,
        nome=membro_nome,
        categoria=membro_categoria,
        valor=dados_extraidos["valor"],
        favorecido=dados_extraidos.get("favorecido"),
        telefone=telefone,
        status=status.value,
        confianca=dados_extraidos["confidence"],
        ocr_bruto_preview=resultado.texto_bruto,
    )
    sheets.append_auditoria(
        evento="OCR_CONCLUIDO",
        detalhes=f"Protocolo {protocolo}, Valor R$ {dados_extraidos['valor']:.2f}",
        telefone=telefone,
        detalhes_dict={
            "valor": float(dados_extraidos["valor"]),
            "data_pagamento": str(data_pag),
            "favorecido": dados_extraidos.get("favorecido"),
            "confidence": dados_extraidos["confidence"],
        },
    )

    if status == StatusContribuicao.PENDENTE:
        sheets.append_pendencia(
            pendencia_id=uuid.uuid4(),
            telefone=telefone,
            nome=membro_nome,
            motivo=MotivoPendencia.IA_BAIXA_CONFIANCA.value,
        )

    # ── 7. Notificação WhatsApp ───────────────────────────────────────
    try:
        notif = NotificacaoService()
        if status == StatusContribuicao.CONFIRMADO:
            await notif.msg_agradecimento(
                telefone, membro_nome,
                f"{dados_extraidos['valor']:.2f}",
                data_pag.isoformat(),
                protocolo,
            )
        elif status == StatusContribuicao.PENDENTE:
            await notif.msg_revisao(telefone, protocolo, nome=membro_nome)
    except Exception as e:
        logger.warning("Falha ao enviar notificação: %s", e)

    # ── 8. Concluir ───────────────────────────────────────────────────
    ocr_logger.registrar_conclusao(
        f"Status: {status.value}, Protocolo: {protocolo}, "
        f"Valor: R$ {dados_extraidos['valor']:.2f}, Confiança: {dados_extraidos['confidence']:.0%}"
    )
    _debug.info(MODULO_OCR, "Pipeline concluído", {
        "status": status.value, "protocolo": protocolo,
        "valor": float(dados_extraidos["valor"]),
    })
    await remover_logger(hash_sha256)
    return {"status": status.value, "protocolo": protocolo}


def _registrar_erro(
    telefone: str, membro_nome: str,
    ocr_texto_bruto: str, ocr_confianca_media: float,
    ocr_logger, hash_sha256: str, motivo: str,
) -> None:
    """Registra erro na planilha Pendências e auditoria."""
    sheets = SheetsWriter()
    sheets.append_pendencia(
        pendencia_id=uuid.uuid4(),
        telefone=telefone,
        nome=membro_nome,
        motivo=motivo,
        observacao=ocr_texto_bruto[:200] if ocr_texto_bruto else "",
    )
    sheets.append_auditoria(
        evento="ERRO_PROCESSAMENTO",
        detalhes=f"Erro: {motivo}",
        telefone=telefone,
    )
    ocr_logger.registrar_erro(ETAPA_ERRO, f"Erro: {motivo}")
    asyncio.run(remover_logger(hash_sha256))