from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.domain.value_objects.protocolo import Protocolo
from src.infrastructure.database.models import SequenciaModel


class ProtocoloService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tz = ZoneInfo(get_settings().app_timezone)

    def _hoje(self) -> date:
        from datetime import datetime

        return datetime.now(self._tz).date()

    async def gerar(self) -> Protocolo:
        hoje = self._hoje()
        result = await self._session.execute(
            select(SequenciaModel).where(SequenciaModel.data == hoje).with_for_update()
        )
        seq = result.scalar_one_or_none()
        if seq is None:
            seq = SequenciaModel(data=hoje, ultimo_numero=0)
            self._session.add(seq)
            await self._session.flush()
        seq.ultimo_numero += 1
        await self._session.flush()
        return Protocolo.gerar(hoje, seq.ultimo_numero)
