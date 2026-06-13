"""Implementacao EasyOCR do OCR local.

Usa EasyOCR (deep learning) com suporte a portugues e ingles.
Resolve o problema de arquivos com caracteres especiais usando Pillow
para leitura das imagens.
Inclui pre-processamento (contraste + nitidez + redimensionamento).

Dependencias:
    - easyocr
    - pillow
    - numpy

Uso:
    O engine e selecionado via ``OCR_ENGINE=easyocr`` nas variaveis de ambiente.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from src.application.services.debug_logger import MODULO_OCR, get_debug_logger
from src.application.services.extracao_ocr import (
    contar_palavras_chave,
    extrair_data,
    extrair_valor,
)
from time import perf_counter

from .paddle_ocr_service import BlocoOCR, ResultadoOCR

logger = logging.getLogger(__name__)


@dataclass
class _EasyOCRHolder:
    """Cache do reader EasyOCR (evita reinicializacao a cada chamada)."""
    reader: object | None = None
    initialized: bool = False


_holder = _EasyOCRHolder()


def _get_reader():
    """Obtem ou inicializa o reader EasyOCR (com cache)."""
    if _holder.initialized:
        return _holder.reader

    try:
        import easyocr

        logger.info("Inicializando EasyOCR reader (pt, en)...")
        _holder.reader = easyocr.Reader(
            ["pt", "en"],
            gpu=False,
            verbose=False,
        )
        _holder.initialized = True
        logger.info("EasyOCR reader inicializado com sucesso")
        return _holder.reader
    except Exception as exc:
        logger.error("Falha ao inicializar EasyOCR: %s", exc)
        _holder.initialized = True  # Evita tentar novamente se falhou
        return None


def _ler_imagem_pillow(caminho: str):
    """Le imagem com Pillow com pre-processamento.

    Resolve caracteres especiais no Windows (parenteses, acentos).
    Inclui:
    - Conversao para RGB
    - Aumento de contraste (imagens muito claras precisam)
    - Nitidez
    - Redimensionamento se imagem muito pequena

    Retorna numpy array RGB ou None se falhar.
    """
    try:
        from PIL import Image, ImageFilter, ImageEnhance
        import numpy as np

        pil_img = Image.open(caminho)

        # Converter para RGB se necessario
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")

        w, h = pil_img.size

        # Aumentar tamanho se muito pequena (ajuda OCR)
        if w < 500 or h < 500:
            scale = max(2, 800 // min(w, h))
            pil_img = pil_img.resize((w * scale, h * scale), Image.LANCZOS)
            logger.debug("Imagem redimensionada: %dx%d -> %dx%d (x%d)",
                         w, h, pil_img.size[0], pil_img.size[1], scale)

        # Aumentar contraste (imagens muito claras)
        enhancer = ImageEnhance.Contrast(pil_img)
        pil_img = enhancer.enhance(1.3)

        # Aplicar nitidez
        pil_img = pil_img.filter(ImageFilter.SHARPEN)

        return np.array(pil_img)
    except Exception as exc:
        logger.warning("Falha ao ler imagem com Pillow: %s", exc)
        return None




class EasyOCRService:
    """Engine EasyOCR principal.

    Caracteristicas:
    - Leitura com Pillow (resolve caracteres especiais no Windows)
    - Pre-processamento: contraste + nitidez + redimensionamento
    - Cache do reader (inicializa uma vez, reusa para todas as imagens)
    - Extracao de valor e data por regex
    - Classificacao de comprovante por palavras-chave
    """

    def __init__(self) -> None:
        self._reader = _get_reader()

    def processar(self, caminho: str) -> ResultadoOCR:
        """Processa uma imagem com EasyOCR e retorna o resultado.

        Args:
            caminho: Caminho absoluto ou relativo para a imagem.

        Returns:
            ResultadoOCR com texto extraido, confianca e blocos.
        """
        start = perf_counter()

        # Ler imagem com Pillow + pre-processamento
        img_array = _ler_imagem_pillow(caminho)
        if img_array is None:
            logger.warning("Falha ao ler imagem: %s", caminho)
            return ResultadoOCR(
                texto_bruto="",
                confianca_media=0.0,
                blocos=[],
                tempo_processamento_ms=0,
            )

        # Verificar se reader esta disponivel
        if self._reader is None:
            logger.warning("EasyOCR reader nao disponivel")
            return ResultadoOCR(
                texto_bruto="",
                confianca_media=0.0,
                blocos=[],
                tempo_processamento_ms=0,
            )

        _debug = get_debug_logger()

        try:
            # Processar com EasyOCR
            # IMPORTANTE: paragraph=False para evitar bug de desempacotamento
            results = self._reader.readtext(
                img_array,
                detail=1,
                paragraph=False,
            )

            # Extrair blocos
            blocos: list[BlocoOCR] = []
            texto_parts: list[str] = []

            for item in results:
                if len(item) == 3:
                    bbox, texto, conf = item
                    texto = texto.strip()
                    if texto:
                        bloco = BlocoOCR(
                            texto=texto,
                            confianca=min(float(conf), 1.0),
                        )
                        blocos.append(bloco)
                        texto_parts.append(texto)

                        # Log detalhado de cada bloco (debug)
                        _debug.debug(
                            MODULO_OCR,
                            f"Bloco: \"{texto[:60]}\" conf={min(float(conf), 1.0):.2f}",
                            {"conf": round(min(float(conf), 1.0), 3), "texto": texto},
                        )

            texto_bruto = "\n".join(texto_parts)
            conf_media = (
                sum(b.confianca for b in blocos) / len(blocos)
                if blocos
                else 0.0
            )

            _debug.info(
                MODULO_OCR,
                "OCR concluído",
                {
                    "blocos": len(blocos),
                    "confianca_media": round(conf_media, 3),
                    "chars": len(texto_bruto),
                    "arquivo": caminho.split("\\")[-1] if "\\" in caminho else caminho.split("/")[-1],
                    "tempo_ms": int((perf_counter() - start) * 1000),
                    "texto_preview": texto_bruto[:200],
                },
            )

            logger.debug("EasyOCR: %d blocos, conf=%.1f%%, %d chars",
                         len(blocos), conf_media * 100, len(texto_bruto))

        except Exception as exc:
            logger.warning("Falha ao executar EasyOCR: %s", exc)
            texto_bruto = ""
            conf_media = 0.0
            blocos = []

        elapsed = int((perf_counter() - start) * 1000)

        return ResultadoOCR(
            texto_bruto=texto_bruto,
            confianca_media=conf_media,
            blocos=blocos,
            tempo_processamento_ms=elapsed,
        )