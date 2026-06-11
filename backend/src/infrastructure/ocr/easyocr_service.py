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
from time import perf_counter

from .paddle_ocr_service import BlocoOCR, ResultadoOCR

logger = logging.getLogger(__name__)

# Palavras-chave para identificar comprovante
_KEYWORDS_COMPROVANTE: set[str] = {
    "pix", "ted", "doc", "comprovante", "transferencia", "transf",
    "r$", "valor", "pago", "receb", "remetente", "favorecido",
    "cpf", "cnpj", "instituicao", "conta", "agencia", "chave",
    "pagamento", "enviado", "horario", "data", "transacao",
    "banco", "nome", "documento",
}


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


def _extrair_valor(texto: str) -> float | None:
    """Tenta extrair valor monetario do texto OCR."""
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


def _extrair_data(texto: str) -> str | None:
    """Tenta extrair data do texto OCR no formato DD/MM/AAAA."""
    padroes = [
        r"(\d{2}/\d{2}/\d{4})",  # 12/08/2022
        r"(\d{2}-\d{2}-\d{4})",  # 12-08-2022
    ]

    for padrao in padroes:
        matches = re.findall(padrao, texto)
        if matches:
            return matches[0]

    return None


def _extrair_palavras_chave(texto: str) -> int:
    """Conta quantas palavras-chave de comprovante aparecem no texto."""
    texto_lower = texto.lower()
    return sum(1 for kw in _KEYWORDS_COMPROVANTE if kw in texto_lower)


def _eh_comprovante(texto: str, confianca: float) -> bool:
    """Determina se o texto lido parece ser um comprovante."""
    if not texto.strip():
        return False
    if confianca < 0.3:
        return False
    palavras = _extrair_palavras_chave(texto)
    return palavras >= 3


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