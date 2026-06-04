from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.membro import Membro


class IMembroRepository(ABC):
    @abstractmethod
    async def get_by_telefone(self, telefone: str) -> Membro | None:
        pass

    @abstractmethod
    async def get_by_id(self, membro_id: UUID) -> Membro | None:
        pass

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 50) -> list[Membro]:
        pass
