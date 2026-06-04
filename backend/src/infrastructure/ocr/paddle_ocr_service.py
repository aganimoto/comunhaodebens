from dataclasses import dataclass
from time import perf_counter

from pydantic import BaseModel, Field

from src.infrastructure.ocr.preprocessor import preprocess_image


class BlocoOCR(BaseModel):
    texto: str
    confianca: float


class ResultadoOCR(BaseModel):
    texto_bruto: str
    confianca_media: float = Field(ge=0.0, le=1.0)
    blocos: list[BlocoOCR] = Field(default_factory=list)
    tempo_processamento_ms: int


@dataclass
class _PaddleHolder:
    engine: object | None = None


_holder = _PaddleHolder()


class PaddleOCRService:
    def _get_engine(self):
        if _holder.engine is None:
            try:
                from paddleocr import PaddleOCR

                _holder.engine = PaddleOCR(use_angle_cls=True, lang="pt", show_log=False)
            except Exception:
                _holder.engine = False
        return _holder.engine

    def processar(self, caminho: str) -> ResultadoOCR:
        start = perf_counter()
        processed_path = preprocess_image(caminho)
        engine = self._get_engine()
        blocos: list[BlocoOCR] = []
        texto_parts: list[str] = []

        if engine and engine is not False:
            result = engine.ocr(processed_path, cls=True)
            for line in result or []:
                for item in line:
                    text, conf = item[1][0], float(item[1][1])
                    texto_parts.append(text)
                    blocos.append(BlocoOCR(texto=text, confianca=conf))

        texto_bruto = "\n".join(texto_parts) if texto_parts else ""
        conf_media = (
            sum(b.confianca for b in blocos) / len(blocos) if blocos else 0.0
        )
        elapsed = int((perf_counter() - start) * 1000)
        return ResultadoOCR(
            texto_bruto=texto_bruto,
            confianca_media=conf_media,
            blocos=blocos,
            tempo_processamento_ms=elapsed,
        )
