"""Cliente Ollama para extração estruturada de dados de comprovantes PIX.

Suporta dois fluxos complementares:

* **extrair_de_imagem** — usa o modelo multimodal
  (``OLLAMA_MODEL``, padrão ``qwen2.5-vl:7b``) para processar a imagem
  diretamente, opcionalmente com o texto OCR como contexto auxiliar.
* **extrair_de_texto** — usa o modelo leve baseado apenas em texto
  (``OLLAMA_TEXT_MODEL``, padrão ``qwen3:4b``) para extrair dados a
  partir do texto devolvido pelo OCR. Esta rota é a recomendada quando
  o OCR já forneceu um texto de boa qualidade.

Ambos os fluxos usam o mesmo ``SYSTEM_PROMPT`` e o parser retrocompatível
definido em :mod:`src.infrastructure.ai.response_parser`.

Regras inegociáveis (LGPD):

* A IA **NUNCA** recebe nome, CPF, telefone, e-mail ou qualquer dado que
  identifique pessoas. A identificação do membro é feita exclusivamente
  pelo telefone via :class:`IdentificacaoService`.
* A IA devolve **apenas** os campos estruturados do comprovante.
"""
from __future__ import annotations

import base64
import logging
from decimal import Decimal
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from src.config import get_settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
Você é um extrator de dados financeiros. Analise o comprovante PIX
fornecido e retorne SOMENTE um JSON válido, sem texto adicional, sem
markdown, sem backticks.

Extraia APENAS:
- valor: número decimal positivo (ex: 150.00)
- data_pix: string ISO 8601 (ex: "2026-06-05")
- favorecido: nome de quem RECEBE o PIX, ou null se não identificado
- tipo_documento: "PIX" | "TED" | "DOC" | "BOLETO" | "OUTRO"
- confidence: float de 0.0 a 1.0 indicando certeza da extração

NÃO infira, NÃO crie, NÃO retorne: nome do pagador, CPF, telefone,
e-mail ou qualquer dado que identifique pessoas.

Formato de retorno OBRIGATÓRIO (somente este JSON, nada mais):
{"valor": 0.00, "data_pix": "YYYY-MM-DD", "favorecido": "string|null",
 "tipo_documento": "PIX|TED|DOC|BOLETO|OUTRO", "confidence": 0.00}
""".strip()


# Tipos de documento aceitos
TIPOS_DOCUMENTO_VALIDOS = ("PIX", "TED", "DOC", "BOLETO", "OUTRO")


class DadosComprovanteSchema(BaseModel):
    """Schema novo (v2) do JSON devolvido pela IA.

    Substitui o schema antigo (``data``/``hora``/``banco``/``confianca``)
    por um conjunto mais explícito e semanticamente correto.
    """

    valor: Decimal = Field(gt=0)
    data_pix: str  # ISO 8601 (validação final fica no parser)
    favorecido: str | None = Field(None, max_length=200)
    tipo_documento: str = "PIX"
    confidence: float = Field(ge=0.0, le=1.0)


class OllamaService:
    def __init__(self) -> None:
        self._settings = get_settings()

    async def extrair_de_imagem(
        self, caminho: str, texto_ocr: str = ""
    ) -> DadosComprovanteSchema | None:
        """Extrai dados diretamente da imagem via modelo multimodal."""
        path = Path(caminho)
        if not path.exists():
            return None
        image_b64 = base64.b64encode(path.read_bytes()).decode()
        prompt = f"Texto OCR auxiliar:\n{texto_ocr}\n\nAnalise o comprovante."
        return await self._chamar_modelo(
            self._settings.ollama_model, prompt, image_b64
        )

    async def extrair_de_texto(self, texto_ocr: str) -> DadosComprovanteSchema | None:
        """Extrai dados a partir do texto OCR via modelo leve (Qwen3:4b).

        Esta é a rota preferencial após OCR. Usa ``OLLAMA_TEXT_MODEL``
        (padrão ``qwen3:4b``), mais leve e rápido, e cai para
        ``OLLAMA_FALLBACK_MODEL`` se o resultado for inválido.
        """
        # Caminho primário: modelo leve (qwen3:4b)
        resultado = await self._chamar_modelo(
            self._settings.ollama_text_model,
            f"Extraia dados do comprovante PIX:\n{texto_ocr}",
            None,
        )
        if resultado is not None:
            return resultado

        # Fallback: modelo de texto maior (qwen2.5:7b)
        logger.info("Qwen3 falhou; tentando fallback %s", self._settings.ollama_fallback_model)
        return await self._chamar_modelo(
            self._settings.ollama_fallback_model,
            f"Extraia dados do comprovante PIX:\n{texto_ocr}",
            None,
        )

    async def _chamar_modelo(
        self, model: str, prompt: str, image_b64: str | None
    ) -> DadosComprovanteSchema | None:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        user_content: dict = {"role": "user", "content": prompt}
        if image_b64:
            user_content["images"] = [image_b64]
        messages.append(user_content)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self._settings.ollama_base_url}/api/chat",
                    json={"model": model, "messages": messages, "stream": False},
                )
                resp.raise_for_status()
                content = resp.json().get("message", {}).get("content", "")
        except Exception as exc:
            logger.warning("Falha ao chamar Ollama (%s): %s", model, exc)
            return None

        from src.infrastructure.ai.response_parser import parse_dados_comprovante

        return parse_dados_comprovante(content)
