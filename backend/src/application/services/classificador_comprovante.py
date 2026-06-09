"""Serviço de classificação de comprovantes baseado em OCR.

Determina se o texto extraído de uma imagem corresponde a um comprovante
de pagamento/PIX válido, usando palavras-chave e limiar de confiança.

Esta função é usada pelo pipeline de OCR **antes** de qualquer notificação
WhatsApp ser enviada. A mensagem automática só é disparada se a imagem
for classificada como comprovante.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Palavras-chave para identificar comprovante de pagamento/PIX
_KEYWORDS_COMPROVANTE: set[str] = {
    "pix", "ted", "doc", "comprovante", "transferencia", "transf",
    "r$", "valor", "pago", "receb", "remetente", "favorecido",
    "cpf", "cnpj", "instituicao", "conta", "agencia", "chave",
    "pagamento", "enviado", "horario", "data", "transacao",
    "banco", "nome", "documento",
}

# Limiar mínimo de palavras-chave para considerar como comprovante
_LIMIAR_PALAVRAS_CHAVE = 3

# Confiança mínima do OCR para considerar
_CONFIANCA_MINIMA_OCR = 0.3


def _extrair_palavras_chave(texto: str) -> int:
    """Conta quantas palavras-chave de comprovante aparecem no texto."""
    texto_lower = texto.lower()
    return sum(1 for kw in _KEYWORDS_COMPROVANTE if kw in texto_lower)


def _extrair_valor(texto: str) -> float | None:
    """Tenta extrair valor monetário do texto OCR."""
    padroes = [
        r"R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",  # R$ 1.234,56
        r"R\$\s*(\d+(?:,\d{2})?)",  # R$ 80,00
    ]

    for padrao in padroes:
        matches = re.findall(padrao, texto)
        for match in matches:
            try:
                valor_str = match.replace(".", "").replace(",", ".")
                valor = float(valor_str)
                if 0 < valor < 1000000:
                    return valor
            except (ValueError, TypeError):
                continue

    return None


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

    palavras = _extrair_palavras_chave(texto_ocr)
    if palavras < _LIMIAR_PALAVRAS_CHAVE:
        logger.debug(
            "Classificação: apenas %d palavras-chave (mínimo %d) — não é comprovante",
            palavras, _LIMIAR_PALAVRAS_CHAVE,
        )
        return False

    valor = _extrair_valor(texto_ocr)
    if valor is None:
        logger.debug(
            "Classificação: %d palavras-chave mas sem valor R$ — não é comprovante",
            palavras,
        )
        return False

    logger.debug(
        "Classificação: COMPROVANTE confirmado (%d palavras-chave, R$ %.2f, conf=%.1f%%)",
        palavras, valor, confianca_media * 100,
    )
    return True