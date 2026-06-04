import json
import re
from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, Field, ValidationError


class DadosComprovante(BaseModel):
    valor: Decimal = Field(gt=0)
    data: date
    hora: time | None = None
    banco: str | None = Field(None, max_length=100)
    confianca: float = Field(ge=0.0, le=1.0)


def parse_dados_comprovante(raw: str) -> DadosComprovante | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
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
    except (json.JSONDecodeError, ValidationError, KeyError, ValueError):
        return None
