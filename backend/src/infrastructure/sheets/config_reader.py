import logging

from src.config import get_settings
from src.infrastructure.cache.redis_client import cache_get, cache_set
from src.infrastructure.sheets.sheets_client import SheetsClient

logger = logging.getLogger(__name__)

CACHE_KEY = "config:all"
DEFAULTS = {
    "MENSAGEM_AGRADECIMENTO": (
        "Olá, {nome}.\n\nRecebemos sua contribuição da Comunhão de Bens.\n"
        "Valor registrado: R$ {valor}\nData do pagamento: {data}\n"
        "Protocolo: {protocolo}\n\n"
        "Muito obrigado por sua oferta e por colaborar com a missão evangelizadora.\n\n"
        "Deus lhe abençoe."
    ),
    "MENSAGEM_NAO_CADASTRADO": (
        "Seu comprovante foi recebido.\n\n"
        "Entretanto seu número ainda não está cadastrado no sistema da Comunhão de Bens.\n\n"
        "Entre em contato com a equipe responsável para regularização."
    ),
    "MENSAGEM_REVISAO": (
        "Olá, {nome}.\n\nRecebemos seu comprovante da Comunhão de Bens.\n\n"
        "Ele está em revisão pela equipe financeira.\n"
        "Protocolo: {protocolo}\n\n"
        "Entraremos em contato caso seja necessário algum esclarecimento.\n\n"
        "Deus lhe abençoe."
    ),
    "MENSAGEM_ERRO": (
        "Olá, {nome}.\n\nRecebemos seu comprovante, "
        "mas ocorreu um erro no processamento automático. "
        "Nossa equipe financeira já foi notificada e entrará em contato se necessário.\n\n"
        "Comunhão de Bens Shalom."
    ),
    "MENSAGEM_DUPLICADO": (
        "Olá, {nome}.\n\nIdentificamos que este comprovante pode já ter sido "
        "registrado anteriormente (protocolo em análise: {protocolo}).\n\n"
        "Nossa equipe financeira irá verificar. Obrigado."
    ),
    "META_MENSAL": "50000",
    "META_ANUAL": "600000",
    "LIMIAR_CONFIANCA": "0.80",
    "CATEGORIAS_VALIDAS": "Comunidade de Vida,Comunidade de Aliança,Obra,Benfeitor",
}


class ConfigReader:
    def __init__(self, client: SheetsClient | None = None) -> None:
        self._client = client or SheetsClient()
        self._settings = get_settings()

    async def get_all(self) -> dict[str, str]:
        cached = await cache_get(CACHE_KEY)
        if cached:
            return cached

        config = dict(DEFAULTS)
        if self._client.available:
            rows = self._client.get_values("Configuração!A2:B")
            for row in rows:
                if len(row) >= 2:
                    config[row[0].strip()] = str(row[1])

        await cache_set(CACHE_KEY, config, self._settings.cache_config_ttl_sec)
        return config

    async def get(self, chave: str, default: str = "") -> str:
        return (await self.get_all()).get(chave, default)

    async def get_float(self, chave: str, default: float) -> float:
        try:
            return float(await self.get(chave, str(default)))
        except ValueError:
            return default