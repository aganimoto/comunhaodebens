"""Cliente Ollama para classificação de comprovantes PIX.

Usa ``OLLAMA_MODEL`` (padrão ``llama3.2:1b``) apenas para **confirmar**
se o texto OCR é um comprovante válido. A extração de valor, data e
favorecido é feita via expressões regulares no próprio Python, já que
o modelo 1B é pequeno demais para gerar JSON estruturado confiável.

Regras inegociáveis (LGPD):

* A IA **NUNCA** recebe nome, CPF, telefone, e-mail ou qualquer dado que
  identifique pessoas. A identificação do membro é feita exclusivamente
  pelo telefone via :class:`IdentificacaoService`.
* A IA devolve **apenas** confirmação se é comprovante ou não.
"""
from __future__ import annotations

import logging

import httpx

from src.application.services.extracao_ocr import extrair_data, extrair_valor
from src.config import get_settings

logger = logging.getLogger(__name__)


# ── Prompt ultra-simplificado para modelo 1B ──────────────────────────

SYSTEM_PROMPT = (
    "Você é um classificador. Responda apenas 'sim' se o texto for "
    "um comprovante de pagamento/PIX, ou 'nao' caso contrário."
)


async def _chamar_ollama(model: str, texto_ocr: str) -> str | None:
    """Chama o Ollama e retorna o texto cru da resposta."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Texto: {texto_ocr}\n"
                "Responda apenas 'sim' ou 'nao'."
            ),
        },
    ]
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "").strip().lower()
    except Exception as exc:
        logger.warning("Falha ao chamar Ollama (%s): %s", model, exc)
        return None


class OllamaService:
    """Serviço de classificação de comprovantes via Ollama.

    O modelo 1B classifica se o texto OCR é comprovante (sim/nao).
    Os dados estruturados (valor, data, favorecido) são extraídos via
    regex no método :meth:`extrair_dados`.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    async def classificar(self, texto_ocr: str) -> bool:
        """Classifica se o texto OCR é um comprovante válido.

        Usa o modelo ``llama3.2:1b``. Em caso de falha ou resposta
        ambígua, retorna ``True`` (assume que é comprovante, já que
        o classificador por palavras-chave já aprovou antes).
        """
        resultado = await _chamar_ollama(self._settings.ollama_text_model, texto_ocr)
        if resultado is None:
            logger.info("Ollama falhou; assumindo comprovante válido")
            return True
        if "sim" in resultado:
            return True
        if "nao" in resultado:
            logger.info("Ollama classificou como NÃO comprovante")
            return False
        logger.info("Resposta ambígua (%r); assumindo comprovante", resultado)
        return True

    async def extrair_dados(self, texto_ocr: str) -> dict | None:
        """Extrai dados do comprovante via regex.

        Returns:
            Dict com ``valor`` (Decimal), ``data_pagamento`` (date),
            ``favorecido`` (str|None) e ``confidence`` (float),
            ou ``None`` se não conseguir extrair ao menos o valor.
        """
        valor = extrair_valor(texto_ocr)
        data = extrair_data(texto_ocr)

        dados: dict = {"valor": valor, "data_pagamento": data, "favorecido": None}

        if dados["valor"] is None:
            logger.info("Não foi possível extrair valor do texto OCR")
            return None

        campos = sum(1 for v in dados.values() if v is not None)
        dados["confidence"] = round(campos / 3, 2)
        return dados