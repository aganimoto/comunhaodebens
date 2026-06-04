import re
from dataclasses import dataclass
from datetime import date

_PATTERN = re.compile(r"^CDB-\d{8}-\d{6}$")


@dataclass(frozen=True)
class Protocolo:
    valor: str

    def __post_init__(self) -> None:
        if not _PATTERN.match(self.valor):
            raise ValueError(f"Protocolo inválido: {self.valor}")

    @classmethod
    def gerar(cls, dia: date, sequencia: int) -> "Protocolo":
        return cls(f"CDB-{dia.strftime('%Y%m%d')}-{sequencia:06d}")

    def __str__(self) -> str:
        return self.valor
