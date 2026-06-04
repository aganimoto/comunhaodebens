from dataclasses import dataclass


@dataclass(frozen=True)
class Confianca:
    valor: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.valor <= 1.0:
            raise ValueError("Confiança deve estar entre 0.0 e 1.0")

    def atende_limiar(self, limiar: float) -> bool:
        return self.valor >= limiar
