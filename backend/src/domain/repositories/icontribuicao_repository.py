from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.contribuicao import Contribuicao


class IContribuicaoRepository(ABC):
    @abstractmethod
    async def save(self, contribuicao: Contribuicao) -> Contribuicao:
        pass

    @abstractmethod
    async def get_by_id(self, contribuicao_id: UUID) -> Contribuicao | None:
        pass

    @abstractmethod
    async def get_by_protocolo(self, protocolo: str) -> Contribuicao | None:
        pass

    @abstractmethod
    async def get_by_hash_imagem(self, hash_imagem: str) -> Contribuicao | None:
        pass

    @abstractmethod
    async def list_paginated(
        self,
        skip: int = 0,
        limit: int = 20,
        status: str | None = None,
    ) -> tuple[list[Contribuicao], int]:
        pass

    @abstractmethod
    async def update(self, contribuicao: Contribuicao) -> Contribuicao:
        pass
