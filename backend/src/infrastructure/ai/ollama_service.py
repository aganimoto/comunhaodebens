import base64
import json
from decimal import Decimal
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from src.config import get_settings

SYSTEM_PROMPT = """
Você é um extrator de dados financeiros. Analise o comprovante PIX fornecido
e retorne SOMENTE um JSON válido, sem texto adicional, sem markdown, sem backticks.

Extraia APENAS:
- valor: número decimal (ex: 150.00)
- data: string ISO 8601 (ex: "2026-06-02")
- hora: string HH:MM (ex: "14:32") ou null se não visível
- banco: string com nome da instituição ou null se não identificado
- confianca: float de 0.0 a 1.0 indicando certeza da extração

NÃO infira, NÃO crie, NÃO retorne: nome, CPF, telefone, e-mail ou qualquer
dado que identifique pessoas.

Formato de retorno OBRIGATÓRIO (somente este JSON, nada mais):
{"valor": 0.00, "data": "YYYY-MM-DD", "hora": "HH:MM", "banco": "string", "confianca": 0.00}
""".strip()


class DadosComprovanteSchema(BaseModel):
    valor: Decimal = Field(gt=0)
    data: str
    hora: str | None = None
    banco: str | None = Field(None, max_length=100)
    confianca: float = Field(ge=0.0, le=1.0)


class OllamaService:
    def __init__(self) -> None:
        self._settings = get_settings()

    async def extrair_de_imagem(self, caminho: str, texto_ocr: str = "") -> DadosComprovanteSchema | None:
        path = Path(caminho)
        if not path.exists():
            return None
        image_b64 = base64.b64encode(path.read_bytes()).decode()
        prompt = f"Texto OCR auxiliar:\n{texto_ocr}\n\nAnalise o comprovante."
        return await self._chamar_modelo(self._settings.ollama_model, prompt, image_b64)

    async def extrair_de_texto(self, texto_ocr: str) -> DadosComprovanteSchema | None:
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
        except Exception:
            return None

        from src.infrastructure.ai.response_parser import parse_dados_comprovante

        return parse_dados_comprovante(content)
