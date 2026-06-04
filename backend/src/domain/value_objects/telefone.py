import re
from dataclasses import dataclass

_E164_PATTERN = re.compile(r"^\+?[1-9]\d{10,14}$")


@dataclass(frozen=True)
class Telefone:
    """Número E.164 normalizado (sem + para Sheets, com + internamente opcional)."""

    valor: str

    def __post_init__(self) -> None:
        normalizado = self._normalizar(self.valor)
        if not _E164_PATTERN.match("+" + normalizado.lstrip("+")):
            raise ValueError(f"Telefone inválido: {self.valor}")
        object.__setattr__(self, "valor", normalizado)

    @staticmethod
    def _normalizar(raw: str) -> str:
        digits = re.sub(r"\D", "", raw)
        if digits.startswith("55") and len(digits) >= 12:
            return digits
        if len(digits) >= 10:
            return "55" + digits[-11:] if len(digits) == 11 else digits
        raise ValueError(f"Telefone inválido: {raw}")

    @property
    def e164(self) -> str:
        return f"+{self.valor}"

    def __str__(self) -> str:
        return self.valor
