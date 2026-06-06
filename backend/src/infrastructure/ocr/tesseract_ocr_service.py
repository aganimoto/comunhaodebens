"""Implementação Tesseract do OCR local.

Mantém a mesma interface pública de :class:`PaddleOCRService` para que o
pipeline (``tasks/ocr_task.py``) possa escolher a engine de forma
transparente via configuração (``OCR_ENGINE``).

Tesseract é uma engine clássica e leve, ideal para ambientes com
recursos limitados. A acurácia costuma ser um pouco menor que a do
PaddleOCR, por isso o pré-processamento OpenCV
(:func:`preprocess_image`) é reaproveitado aqui.

A dependência ``pytesseract`` é opcional — só é importada se a engine
for selecionada em tempo de execução. O binário ``tesseract`` precisa
estar instalado no sistema (ver ``docs/OPERACAO.md``).
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from src.config import get_settings
from src.infrastructure.ocr.preprocessor import preprocess_image

from .paddle_ocr_service import BlocoOCR, ResultadoOCR

logger = logging.getLogger(__name__)


@dataclass
class _TesseractHolder:
    pytesseract_module: object | None = None
    binary_checked: bool = False
    binary_ok: bool = False


_holder = _TesseractHolder()


def _garantir_binario(cmd: str) -> bool:
    """Confere se o binário do Tesseract está disponível.

    Não levanta exceção — apenas registra um warning e devolve ``False``
    caso não esteja instalado. O caller trata o fallback para texto
    vazio.
    """
    if _holder.binary_checked:
        return _holder.binary_ok

    _holder.binary_checked = True
    binary = cmd or shutil.which("tesseract")
    if not binary:
        logger.warning(
            "Tesseract não encontrado no PATH. "
            "Instale o binário (apt/choco/brew) ou defina TESSERACT_CMD."
        )
        _holder.binary_ok = False
        return False

    if cmd and not Path(cmd).exists():
        logger.warning("TESSERACT_CMD definido mas arquivo não existe: %s", cmd)
        _holder.binary_ok = False
        return False

    _holder.binary_ok = True
    return True


def _carregar_pytesseract():
    if _holder.pytesseract_module is not None:
        return _holder.pytesseract_module

    try:
        import pytesseract  # type: ignore[import-untyped]

        _holder.pytesseract_module = pytesseract
    except Exception as exc:  # pragma: no cover - import opcional
        logger.warning("pytesseract não está instalado: %s", exc)
        _holder.pytesseract_module = False
    return _holder.pytesseract_module


class TesseractOCRService:
    """Engine Tesseract com a mesma interface de :class:`PaddleOCRService`."""

    def __init__(self, lang: str | None = None, cmd: str | None = None) -> None:
        settings = get_settings()
        self._lang = lang or settings.tesseract_lang
        self._cmd = cmd if cmd is not None else settings.tesseract_cmd

    def processar(self, caminho: str) -> ResultadoOCR:
        start = perf_counter()
        processed_path = preprocess_image(caminho)

        blocos: list[BlocoOCR] = []
        texto_parts: list[str] = []
        conf_media = 0.0

        if _garantir_binario(self._cmd):
            pytesseract = _carregar_pytesseract()
            if pytesseract and pytesseract is not False:
                if self._cmd:
                    pytesseract.pytesseract.tesseract_cmd = self._cmd
                try:
                    # image_to_data devolve blocos com confiança
                    data = pytesseract.image_to_data(
                        processed_path,
                        lang=self._lang,
                        output_type=pytesseract.Output.DICT,
                    )
                    n = len(data.get("text", []))
                    for i in range(n):
                        txt = (data["text"][i] or "").strip()
                        if not txt:
                            continue
                        try:
                            conf = float(data["conf"][i])
                        except (TypeError, ValueError):
                            conf = -1.0
                        # pytesseract devolve -1 quando não há confiança
                        # confiável para o bloco; normalizamos para 0.
                        if conf < 0:
                            conf = 0.0
                        else:
                            # Tesseract devolve 0-100; normalizamos para 0-1
                            conf = min(conf / 100.0, 1.0)
                        texto_parts.append(txt)
                        blocos.append(BlocoOCR(texto=txt, confianca=conf))

                    if not texto_parts:
                        # Fallback: extrai texto puro caso image_to_data
                        # não tenha retornado blocos utilizáveis
                        txt_full = pytesseract.image_to_string(
                            processed_path, lang=self._lang
                        )
                        if txt_full:
                            texto_parts = [txt_full]
                            # Sem confiança por bloco: usamos 0.5 como
                            # estimativa neutra
                            blocos = [BlocoOCR(texto=txt_full, confianca=0.5)]
                except Exception as exc:
                    logger.warning("Falha ao executar tesseract: %s", exc)

        texto_bruto = "\n".join(texto_parts) if texto_parts else ""
        if blocos:
            conf_media = sum(b.confianca for b in blocos) / len(blocos)

        elapsed = int((perf_counter() - start) * 1000)
        return ResultadoOCR(
            texto_bruto=texto_bruto,
            confianca_media=conf_media,
            blocos=blocos,
            tempo_processamento_ms=elapsed,
        )
