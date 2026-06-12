import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Descobre a raiz do projeto (onde está o .env) independente de onde o código roda
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"
    ollama_fallback_model: str = "llama3.2:1b"
    ollama_text_model: str = "llama3.2:1b"

    # OCR — seleção de engine
    ocr_engine: str = "easyocr"  # "easyocr" | "paddle" | "tesseract"
    tesseract_cmd: str = ""  # caminho do binário tesseract (vazio = usar PATH)
    tesseract_lang: str = "por"

    google_service_account_json: str = ""
    google_spreadsheet_id: str = ""

    whatsapp_service_url: str = "http://localhost:3000"
    whatsapp_webhook_secret: str = "dev-secret-change-me"

    jwt_secret_key: str = "dev-jwt-secret-change-me-64-chars-minimum-for-hs256"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    app_timezone: str = "America/Sao_Paulo"
    shared_media_path: str = "/shared/media"
    shared_relatorios_path: str = "/shared/relatorios"
    shared_backup_path: str = "/shared/backups"
    log_level: str = "info"
    cors_origins: str = "http://localhost:5173"

    cache_membros_ttl_min: int = 5
    cache_config_ttl_sec: int = 60
    limiar_confianca: float = 0.80

    # --- Ajustes de desenvolvimento ---
    # Em dev_mode, caminhos locais substituem volumes Docker
    dev_mode: bool = False
    # Manter últimos N backups antes de rotacionar
    backup_keep: int = 30
    # Caminho de saída de PDFs de relatório em dev (sem volume compartilhado)
    dev_relatorios_path: str = "./dev_data/relatorios"
    dev_backup_path: str = "./dev_data/backups"
    # Primeiro admin criado pelo script create_admin
    bootstrap_admin_email: str = "admin@cdbshalom.local"
    bootstrap_admin_password: str = "TroqueEstaSenha123!"
    bootstrap_admin_perfil: str = "administrador"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_relatorios_path(self) -> str:
        return self.dev_relatorios_path if self.dev_mode else self.shared_relatorios_path

    @property
    def effective_backup_path(self) -> str:
        if self.dev_mode and "DEV_BACKUP_PATH" in os.environ:
            return self.dev_backup_path
        if "SHARED_BACKUP_PATH" in os.environ:
            return self.shared_backup_path
        return self.dev_backup_path if self.dev_mode else self.shared_backup_path


@lru_cache
def get_settings() -> Settings:
    return Settings()
