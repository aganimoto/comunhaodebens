"""Parser retrocompatível para o JSON devolvido pela IA.

Existem dois schemas possíveis no sistema:

**Schema novo (v2)** — usado a partir da Fase 3 com Qwen3:4b::

    {
      "valor": 150.00,
      "data_pix": "2026-06-05",
      "favorecido": "Comunidade Católica Shalom",
      "tipo_documento": "PIX",
      "confidence": 0.96
    }

**Schema antigo (v1)** — usado pelo código legado (``data``, ``hora``,
``banco``, ``confianca``)::

    {
      "valor": 150.00,
      "data": "2026-06-02",
      "hora": "14:32",
      "banco": "Banco do Brasil",
      "confianca": 0.96
    }

A função :func:`parse_dados_comprovante` tenta primeiro o schema novo.
Se falhar, tenta o schema antigo e converte para o novo
(``adaptar_v1_para_v2``), mantendo 100% de compatibilidade com respostas
de modelos ainda no schema antigo.

A função :func:`adaptar_v2_para_v1` faz o caminho inverso para que o
resto do pipeline (``RegistrarContribuicaoUseCase``, etc.) continue
funcionando sem alterações até a Fase 4.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


# ── Schema NOVO (v2) ────────────────────────────────────────────────────
class DadosComprovanteV2(BaseModel):
    """Schema novo do JSON devolvido pela IA."""

    valor: Decimal = Field(gt=0)
    data_pix: str
    favorecido: str | None = Field(None, max_length=200)
    tipo_documento: str = "PIX"
    confidence: float = Field(ge=0.0, le=1.0)

    @property
    def data_pix_date(self) -> date | None:
        """Converte ``data_pix`` para :class:`datetime.date` se possível."""
        try:
            return date.fromisoformat(self.data_pix)
        except (ValueError, TypeError):
            return None


# ── Schema ANTIGO (v1) — mantido para retrocompatibilidade ─────────────
class DadosComprovante(BaseModel):
    """Schema antigo. Mantido para não quebrar o pipeline atual."""

    valor: Decimal = Field(gt=0)
    data: date
    hora: time | None = None
    banco: str | None = Field(None, max_length=100)
    confianca: float = Field(ge=0.0, le=1.0)


# ── Adaptadores entre schemas ───────────────────────────────────────────
TIPOS_DOCUMENTO_VALIDOS = ("PIX", "TED", "DOC", "BOLETO", "OUTRO")


def _normalizar_tipo_documento(tipo: str | None) -> str:
    if not tipo:
        return "PIX"
    # Remove acentos e caixa para uma comparação robusta
    t = unicodedata.normalize("NFKD", str(tipo))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.strip().upper()
    if t in TIPOS_DOCUMENTO_VALIDOS:
        return t
    # Heurística por substring
    if "PIX" in t:
        return "PIX"
    if "TED" in t or ("TRANSFERENCIA" in t and "ELETRONICA" in t):
        return "TED"
    if t == "DOC" or t.startswith("DOC ") or t.endswith(" DOC"):
        return "DOC"
    if "BOLETO" in t or "BOLET" in t or "FATURA" in t:
        return "BOLETO"
    return "OUTRO"


def adaptar_v1_para_v2(dados_v1: DadosComprovante) -> DadosComprovanteV2:
    """Converte o schema antigo (v1) para o novo (v2)."""
    return DadosComprovanteV2(
        valor=dados_v1.valor,
        data_pix=dados_v1.data.isoformat(),
        favorecido=dados_v1.banco,  # aproximação: o "banco" antigo vira favorecido
        tipo_documento="PIX",
        confidence=dados_v1.confianca,
    )


def adaptar_v2_para_v1(dados_v2: DadosComprovanteV2) -> DadosComprovante:
    """Converte o schema novo (v2) para o antigo (v1) para uso no
    pipeline atual (``RegistrarContribuicaoUseCase``).
    """
    data_obj: date
    try:
        data_obj = date.fromisoformat(str(dados_v2.data_pix))
    except (ValueError, TypeError):
        # Fallback: hoje, mas com warning
        logger.warning(
            "data_pix inválida (%r); usando data atual como fallback", dados_v2.data_pix
        )
        data_obj = datetime.utcnow().date()

    return DadosComprovante(
        valor=dados_v2.valor,
        data=data_obj,
        hora=None,
        banco=dados_v2.favorecido,
        confianca=dados_v2.confidence,
    )


# ── Parser principal ────────────────────────────────────────────────────
def _extrair_primeiro_json(texto: str) -> str | None:
    """Extrai o primeiro bloco JSON de uma string, mesmo que venha
    cercado por markdown ````json ... `````."""
    text = texto.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    # Tenta pegar o maior bloco balanceado (suporta um nível de aninhamento)
    match = re.search(r"\{(?:[^{}]|\{[^{}]*\})*\}", text, re.DOTALL)
    if not match:
        return None
    return match.group()


def _parse_v2(data: dict[str, Any]) -> DadosComprovanteV2 | None:
    """Tenta validar como schema v2."""
    if "data_pix" not in data:
        return None
    if "valor" not in data:
        return None
    try:
        return DadosComprovanteV2(
            valor=Decimal(str(data["valor"])),
            data_pix=str(data["data_pix"]),
            favorecido=data.get("favorecido"),
            tipo_documento=_normalizar_tipo_documento(data.get("tipo_documento")),
            confidence=float(data.get("confidence", 0)),
        )
    except (ValidationError, ValueError, TypeError) as exc:
        logger.debug("Falha parse v2: %s", exc)
        return None


def _parse_v1(data: dict[str, Any]) -> DadosComprovante | None:
    """Tenta validar como schema v1 (legado)."""
    if "data" not in data:
        return None
    if "valor" not in data:
        return None
    try:
        hora_val = data.get("hora")
        hora_parsed = None
        if hora_val:
            parts = str(hora_val).split(":")
            hora_parsed = time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        return DadosComprovante(
            valor=Decimal(str(data["valor"])),
            data=date.fromisoformat(str(data["data"])),
            hora=hora_parsed,
            banco=data.get("banco"),
            confianca=float(data.get("confianca", 0)),
        )
    except (ValidationError, ValueError, TypeError) as exc:
        logger.debug("Falha parse v1: %s", exc)
        return None


def parse_dados_comprovante(raw: str) -> DadosComprovanteV2 | None:
    """Faz o parse do JSON da IA, retornando sempre o schema novo (v2).

    Primeiro verifica se a imagem foi classificada como comprovante válido
    (campo ``e_comprovante``). Se ``e_comprovante`` for ``false``, retorna
    ``None`` imediatamente.

    Em seguida tenta o schema novo; em caso de falha, tenta o schema
    antigo e converte para v2. Retorna ``None`` se nenhum dos dois casar.
    """
    json_str = _extrair_primeiro_json(raw)
    if not json_str:
        return None

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.warning("JSON inválido da IA: %s", exc)
        return None

    # Verifica se a IA classificou como NÃO sendo comprovante
    if data.get("e_comprovante") is False:
        logger.info("IA classificou a imagem como NÃO sendo comprovante válido")
        return None

    # 1) Tenta v2 primeiro
    v2 = _parse_v2(data)
    if v2 is not None:
        return v2

    # 2) Fallback: v1
    v1 = _parse_v1(data)
    if v1 is not None:
        logger.info("Resposta da IA em schema v1 (legado); convertendo para v2")
        return adaptar_v1_para_v2(v1)

    return None
