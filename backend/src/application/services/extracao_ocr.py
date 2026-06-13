"""Funções compartilhadas de extração de dados do texto OCR.

Consolida a lógica que estava duplicada em:
- ollama_service.py (extrair_valor, extrair_data)
- classificador_comprovante.py (extrair_valor, palavras-chave)
- easyocr_service.py (extrair_valor, extrair_data, palavras-chave)
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

# ── Padrões de extração ───────────────────────────────────────────

_PADROES_VALOR = [
    re.compile(r"R\$\s*([\d\s,.]+)"),
    re.compile(r"VALOR[:\s]*R?\$?\s*([\d\s,.]+)", re.IGNORECASE),
]

_PADROES_DATA_BR = re.compile(r"(\d{2})[/\-](\d{2})[/\-](\d{4})")

# Palavras-chave para identificar comprovante de pagamento/PIX
KEYWORDS_COMPROVANTE: set[str] = {
    "pix", "ted", "doc", "comprovante", "transferencia", "transf",
    "r$", "valor", "pago", "receb", "remetente", "favorecido",
    "cpf", "cnpj", "instituicao", "conta", "agencia", "chave",
    "pagamento", "enviado", "horario", "data", "transacao",
    "banco", "nome", "documento",
}

# Limiar mínimo de palavras-chave para considerar como comprovante
LIMIAR_PALAVRAS_CHAVE = 3


def extrair_valor(texto: str) -> Decimal | None:
    """Extrai o primeiro valor monetário do texto OCR.

    Suporta formatos brasileiros (R$ 1.234,56) e americanos (1,234.56).
    Retorna Decimal ou None se não encontrar valor válido.
    """
    for padrao in _PADROES_VALOR:
        match = padrao.search(texto)
        if match:
            raw = match.group(1).strip()
            # Remove separadores de milhar, mantém vírgula decimal
            if "," in raw and raw.rindex(",") > raw.rfind("."):
                raw = raw.replace(".", "").replace(",", ".")
            else:
                raw = raw.replace(",", "")
            raw = raw.replace(" ", "")
            try:
                valor = Decimal(raw)
                if 0 < valor < 1_000_000:
                    return valor
            except (InvalidOperation, ValueError):
                continue
    return None


def extrair_data(texto: str) -> date | None:
    """Extrai a primeira data no formato dd/mm/aaaa ou dd-mm-aaaa."""
    match = _PADROES_DATA_BR.search(texto)
    if match:
        try:
            dia, mes, ano = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return date(ano, mes, dia)
        except (ValueError, OverflowError):
            pass
    return None


def contar_palavras_chave(texto: str) -> int:
    """Conta quantas palavras-chave de comprovante aparecem no texto."""
    texto_lower = texto.lower()
    return sum(1 for kw in KEYWORDS_COMPROVANTE if kw in texto_lower)


def eh_comprovante(texto: str, confianca: float, limiar_confianca: float = 0.3) -> bool:
    """Determina se o texto lido parece ser um comprovante válido.

    Verifica:
    1. Texto não vazio
    2. Confiança mínima do OCR
    3. Presença de pelo menos 3 palavras-chave
    4. Presença de valor monetário (R$)
    """
    if not texto or not texto.strip():
        return False
    if confianca < limiar_confianca:
        return False
    palavras = contar_palavras_chave(texto)
    return palavras >= LIMIAR_PALAVRAS_CHAVE