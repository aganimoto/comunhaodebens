"""Serviço de classificação de comprovantes baseado em OCR.

Determina se o texto extraído de uma imagem corresponde a um comprovante
de pagamento/PIX válido, usando palavras-chave e limiar de confiança.

Esta função é usada pelo pipeline de OCR **antes** de qualquer notificação
WhatsApp ser enviada. A mensagem automática só é disparada se a imagem
for classificada como comprovante.
"""
from __future__ import annotations

import logging

from src.application.services.extracao_ocr import (
    LIMIAR_PALAVRAS_CHAVE,
    contar_palavras_chave,
    extrair_valor,
)

logger = logging.getLogger(__name__)

# Limiar mínimo de confiança do OCR para considerar
_CONFIANCA_MINIMA_OCR = 0.3


def eh_comprovante(texto_ocr: str, confianca_media: float) -> bool:
    """Determina se o texto lido pelo OCR parece ser um comprovante válido.

    A função verifica:
    1. Texto não vazio
    2. Confiança mínima do OCR
    3. Presença de pelo menos 3 palavras-chave de comprovante
    4. Presença de valor monetário (R$)

    Args:
        texto_ocr: Texto bruto extraído pelo OCR.
        confianca_media: Confiança média do OCR (0.0 a 1.0).

    Returns:
        True se a imagem for classificada como comprovante, False caso contrário.
    """
    if not texto_ocr or not texto_ocr.strip():
        logger.debug("Classificação: texto vazio — não é comprovante")
        return False

    if confianca_media < _CONFIANCA_MINIMA_OCR:
        logger.debug(
            "Classificação: confiança muito baixa (%.1f%%) — não é comprovante",
            confianca_media * 100,
        )
        return False

    palavras = contar_palavras_chave(texto_ocr)
    if palavras < LIMIAR_PALAVRAS_CHAVE:
        logger.debug(
            "Classificação: apenas %d palavras-chave (mínimo %d) — não é comprovante",
            palavras, LIMIAR_PALAVRAS_CHAVE,
        )
        return False

    valor = extrair_valor(texto_ocr)
    if valor is None:
        logger.debug(
            "Classificação: %d palavras-chave mas sem valor R$ — não é comprovante",
            palavras,
        )
        return False

    logger.debug(
        "Classificação: COMPROVANTE confirmado (%d palavras-chave, R$ %s, conf=%.1f%%)",
        palavras, valor, confianca_media * 100,
    )
    return True