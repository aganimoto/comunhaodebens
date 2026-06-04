from src.domain.value_objects.telefone import Telefone
from src.infrastructure.sheets.membros_reader import MembroSheets, MembrosReader


class IdentificacaoService:
    """Identifica contribuinte exclusivamente pelo telefone via aba Membros."""

    def __init__(self, reader: MembrosReader | None = None) -> None:
        self._reader = reader or MembrosReader()

    async def identificar(self, telefone_raw: str) -> MembroSheets | None:
        telefone = Telefone(telefone_raw)
        membro = await self._reader.buscar_por_telefone(str(telefone))
        if membro and membro.ativo:
            return membro
        return None
