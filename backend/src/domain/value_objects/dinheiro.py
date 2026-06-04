from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class Dinheiro:
    valor: Decimal

    def __post_init__(self) -> None:
        quantizado = self.valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if quantizado <= 0:
            raise ValueError("Valor deve ser positivo")
        object.__setattr__(self, "valor", quantizado)

    @property
    def centavos(self) -> int:
        return int(self.valor * 100)
