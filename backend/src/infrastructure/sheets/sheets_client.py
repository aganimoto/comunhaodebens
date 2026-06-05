"""Cliente Google Sheets com fallback local em JSON quando sem credenciais."""
import json
import logging
import os
from pathlib import Path
from typing import Any

from src.config import get_settings

logger = logging.getLogger(__name__)

_FALLBACK_DIR = Path(__file__).resolve().parent.parent.parent.parent / "dev_data"
_FALLBACK_FILE = _FALLBACK_DIR / "sheets_fallback.json"


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _resolve_creds_path(path: str) -> str | None:
    """Tenta resolver o caminho do service account, buscando em locais comuns."""
    # Já é absoluto e existe
    if os.path.isabs(path) and os.path.isfile(path):
        return path

    # Relativo ao CWD
    if os.path.isfile(path):
        return os.path.abspath(path)

    # Relativo à raiz do projeto
    root_path = _PROJECT_ROOT / path
    if root_path.is_file():
        logger.info("Credenciais Google encontradas em: %s", root_path)
        return str(root_path)

    # Caminhos alternativos comuns
    candidates = [
        Path.cwd() / path,
        Path.cwd() / ".." / path,
        _PROJECT_ROOT / "scripts" / "google_sa.json",
        Path.home() / "Documents" / "comunhaodebens" / path,
    ]
    for c in candidates:
        resolved = str(c.resolve())
        if os.path.isfile(resolved):
            logger.info("Credenciais Google encontradas em: %s", resolved)
            return resolved

    return None


def _load_fallback() -> dict[str, list[list[Any]]]:
    if _FALLBACK_FILE.exists():
        try:
            return json.loads(_FALLBACK_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Erro ao ler fallback sheets: %s", exc)
    return {}


def _save_fallback(data: dict[str, list[list[Any]]]) -> None:
    _FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    _FALLBACK_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


class SheetsClient:
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(self) -> None:
        settings = get_settings()
        self._spreadsheet_id = settings.google_spreadsheet_id
        creds_path = settings.google_service_account_json

        resolved = _resolve_creds_path(creds_path) if creds_path else None

        if resolved and os.path.isfile(resolved):
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build

                creds = service_account.Credentials.from_service_account_file(
                    resolved, scopes=self.SCOPES
                )
                self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
                logger.info(
                    "SheetsClient conectado ao Google Sheets (spreadsheet_id=%s)",
                    self._spreadsheet_id,
                )
            except Exception as exc:
                logger.warning("Falha ao conectar ao Google Sheets, usando fallback local: %s", exc)
                self._service = None
        else:
            logger.warning(
                "SheetsClient: credenciais não encontradas. "
                "Caminho configurado='%s', resolvido='%s'. "
                "Usando fallback local em %s.",
                creds_path,
                resolved,
                _FALLBACK_FILE,
            )
            self._service = None

    @property
    def available(self) -> bool:
        return self._service is not None and bool(self._spreadsheet_id)

    def get_values(self, range_name: str) -> list[list[Any]]:
        if self.available:
            result = (
                self._service.spreadsheets()
                .values()
                .get(spreadsheetId=self._spreadsheet_id, range=range_name)
                .execute()
            )
            return result.get("values", [])

        # Fallback local
        sheet, _ = range_name.split("!", 1) if "!" in range_name else (range_name, "A1")
        data = _load_fallback()
        return [row[:] for row in data.get(sheet, [])]

    def append_row(self, sheet_name: str, values: list[Any]) -> None:
        if self.available:
            self._service.spreadsheets().values().append(
                spreadsheetId=self._spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [values]},
            ).execute()
            return

        # Fallback local
        data = _load_fallback()
        data.setdefault(sheet_name, []).append(list(values))
        _save_fallback(data)
        logger.info("Dados salvos no fallback local (%s): %s", _FALLBACK_FILE, sheet_name)

    def batch_update(self, requests: list[dict]) -> None:
        if not self.available:
            logger.warning(
                "SheetsClient.batch_update ignorado: Google Sheets indisponível. "
                "%d requisições ignoradas.",
                len(requests),
            )
            return
        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={"requests": requests},
        ).execute()