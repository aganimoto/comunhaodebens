import logging
import tempfile
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _ler_imagem_segura(caminho: str):
    """Tenta ler imagem: primeiro com OpenCV, fallback para Pillow.

    OpenCV falha com caracteres especiais (parenteses, acentos) no Windows.
    Pillow funciona com qualquer nome de arquivo.
    """
    # Tentativa 1: OpenCV
    img = cv2.imread(caminho)
    if img is not None:
        return img

    # Tentativa 2: Pillow (resolve caracteres especiais)
    try:
        from PIL import Image

        pil_img = Image.open(caminho)
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        logger.warning("Falha ao ler imagem com Pillow: %s", exc)
        return None


def preprocess_image(caminho: str) -> str:
    """Pre-processa imagem para OCR com fallback Pillow."""
    img = _ler_imagem_segura(caminho)
    if img is None:
        return caminho

    h, w = img.shape[:2]
    max_width = 2000
    if w > max_width:
        scale = max_width / w
        img = cv2.resize(img, None, fx=scale, fy=scale)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    binary = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    coords = np.column_stack(np.where(binary > 0))
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) > 2:
            (h2, w2) = binary.shape
            center = (w2 // 2, h2 // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            binary = cv2.warpAffine(
                binary, M, (w2, h2), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
            )

    out = Path(tempfile.gettempdir()) / f"pre_{Path(caminho).name}"
    cv2.imwrite(str(out), binary)
    return str(out)