"""Envio de mensagens WhatsApp via whatsapp-service."""
import httpx

from src.config import get_settings
from src.infrastructure.sheets.config_reader import ConfigReader


class NotificacaoService:
    def __init__(self, config: ConfigReader | None = None) -> None:
        self._config = config or ConfigReader()
        self._settings = get_settings()

    async def enviar_texto(self, telefone: str, mensagem: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    f"{self._settings.whatsapp_service_url}/send",
                    json={"telefone": telefone, "mensagem": mensagem},
                )
        except httpx.ConnectError:
            # WhatsApp service não disponível — log e continua
            import structlog
            structlog.get_logger().warning(
                "whatsapp_service_indisponivel", telefone=telefone[:4] + "***"
            )

    async def msg_agradecimento(
        self,
        telefone: str,
        nome: str,
        valor: str,
        data: str,
        protocolo: str,
    ) -> None:
        template = await self._config.get("MENSAGEM_AGRADECIMENTO", "")
        msg = template.format(nome=nome, valor=valor, data=data, protocolo=protocolo)
        await self.enviar_texto(telefone, msg)

    async def msg_nao_cadastrado(self, telefone: str) -> None:
        msg = await self._config.get("MENSAGEM_NAO_CADASTRADO", "")
        await self.enviar_texto(telefone, msg)

    async def msg_revisao(self, telefone: str, protocolo: str) -> None:
        template = await self._config.get("MENSAGEM_REVISAO", "")
        await self.enviar_texto(telefone, template.format(protocolo=protocolo))

    async def msg_erro(self, telefone: str) -> None:
        msg = await self._config.get("MENSAGEM_ERRO", "")
        await self.enviar_texto(telefone, msg)
