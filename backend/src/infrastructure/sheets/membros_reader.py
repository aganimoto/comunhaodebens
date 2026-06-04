from dataclasses import dataclass

from src.config import get_settings
from src.domain.entities.membro import CategoriaMembro, Membro
from src.infrastructure.cache.redis_client import cache_get, cache_set
from src.infrastructure.sheets.sheets_client import SheetsClient

CACHE_KEY = "membros:all"


@dataclass
class MembroSheets:
    telefone: str
    nome: str
    categoria: str
    ativo: bool


class MembrosReader:
    def __init__(self, client: SheetsClient | None = None) -> None:
        self._client = client or SheetsClient()
        self._settings = get_settings()

    async def buscar_por_telefone(self, telefone: str) -> MembroSheets | None:
        membros = await self._listar_membros_cache()
        for m in membros:
            if m.telefone == telefone:
                return m
        return None

    async def _listar_membros_cache(self) -> list[MembroSheets]:
        cached = await cache_get(CACHE_KEY)
        if cached is not None:
            return [MembroSheets(**row) for row in cached]

        rows = self._client.get_values("Membros!A2:D")
        membros: list[MembroSheets] = []
        for row in rows:
            if len(row) < 4:
                continue
            tel, nome, cat, ativo = row[0], row[1], row[2], str(row[3]).upper() == "TRUE"
            membros.append(MembroSheets(telefone=tel.strip(), nome=nome, categoria=cat, ativo=ativo))

        ttl = self._settings.cache_membros_ttl_min * 60
        await cache_set(CACHE_KEY, [m.__dict__ for m in membros], ttl)
        return membros

    def to_membro_entity(self, sheets: MembroSheets) -> Membro:
        return Membro(
            id=None,
            telefone=sheets.telefone,
            nome=sheets.nome,
            categoria=CategoriaMembro(sheets.categoria),
            ativo=sheets.ativo,
        )
