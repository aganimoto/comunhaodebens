from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NovoComprovanteRecebido:
    telefone: str
    whatsapp_msg_id: str
    timestamp: datetime
    tipo_midia: str
    caminho_arquivo: str
    hash_sha256: str
