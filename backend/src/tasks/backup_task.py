"""Backup automatizado do PostgreSQL via pg_dump.

O `pg_dump` é executado em subprocess; o arquivo `.dump` é gerado no
volume compartilhado `shared_backups`. Mantém-se uma rotação dos últimos
N arquivos (default 30).
"""
from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from src.config import get_settings
from src.tasks.celery_app import celery_app

# Locais comuns de pg_dump em imagens Alpine/Debian
_PG_DUMP_CANDIDATES = (
    "/usr/bin/pg_dump",
    "/usr/local/bin/pg_dump",
)


def _resolve_pg_dump() -> str:
    found = shutil.which("pg_dump")
    if found:
        return found
    for c in _PG_DUMP_CANDIDATES:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    raise FileNotFoundError(
        "pg_dump não encontrado. Instale o postgresql-client no container."
    )


def _parse_database_url(url: str) -> dict:
    """Extrai componentes do DATABASE_URL asyncpg para pg_dump."""
    parsed = urlparse(url)
    if parsed.scheme not in ("postgresql", "postgresql+asyncpg", "postgres"):
        raise ValueError(f"Esquema não suportado para pg_dump: {parsed.scheme}")
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "",
        "password": parsed.password or "",
        "dbname": (parsed.path or "/").lstrip("/"),
    }


def _run_pg_dump(parts: dict, out_file: Path) -> None:
    pg_dump = _resolve_pg_dump()
    cmd = [
        pg_dump,
        "-h", parts["host"],
        "-p", parts["port"],
        "-U", parts["user"],
        "-d", parts["dbname"],
        "-F", "c",         # custom (comprimido, suportado por pg_restore)
        "-Z", "9",         # nível máximo de compressão
        "-f", str(out_file),
        "--no-owner",
        "--no-privileges",
        "--quote-all-identifiers",
    ]
    env = os.environ.copy()
    if parts["password"]:
        env["PGPASSWORD"] = parts["password"]
    result = subprocess.run(  # noqa: S603 — execução controlada, args fixos
        cmd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=60 * 30,  # 30 min
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"pg_dump falhou (rc={result.returncode}): {result.stderr.strip()}"
        )


def _rotate(directory: Path, keep: int) -> list[str]:
    files = sorted(directory.glob("backup_*.dump"), key=lambda p: p.stat().st_mtime)
    removed: list[str] = []
    for old in files[:-keep] if keep > 0 else files:
        old.unlink(missing_ok=True)
        removed.append(old.name)
    return removed


@celery_app.task(name="backup_diario", bind=True, max_retries=2)
def backup_diario(self) -> dict:  # noqa: D401
    """Executa pg_dump e roda a rotação dos backups antigos."""
    settings = get_settings()
    tz = ZoneInfo(settings.app_timezone)
    now = datetime.now(tz)

    backup_dir = Path(settings.effective_backup_path)
    backup_dir.mkdir(parents=True, exist_ok=True)

    filename = f"backup_{now.strftime('%Y%m%d_%H%M%S')}.dump"
    out_file = backup_dir / filename

    # Em modo dev com SQLite ou sem postgres, pula pg_dump e cria um .dump vazio
    if settings.dev_mode or not settings.database_url.startswith(("postgres", "postgresql")):
        out_file.write_bytes(b"DEV_MODE_PLACEHOLDER")
        return {"status": "dev_mode", "arquivo": filename}

    try:
        parts = _parse_database_url(settings.database_url)
        _run_pg_dump(parts, out_file)
    except FileNotFoundError as e:
        # Ambiente sem pg_dump instalado — registra e segue
        out_file.write_text(f"SKIPPED: {e}\n", encoding="utf-8")
        return {"status": "skipped", "motivo": str(e), "arquivo": filename}
    except Exception as exc:
        if self.app.conf.task_always_eager:
            out_file.write_text(f"FAILED: {exc}\n", encoding="utf-8")
            return {"status": "failed", "erro": str(exc), "arquivo": filename}
        # tentativa de retry automático
        try:
            raise self.retry(exc=exc, countdown=300)
        except self.MaxRetriesExceededError:
            out_file.write_text(f"FAILED: {exc}\n", encoding="utf-8")
            return {"status": "failed", "erro": str(exc), "arquivo": filename}

    removed = _rotate(backup_dir, keep=settings.backup_keep)
    size = out_file.stat().st_size
    return {
        "status": "ok",
        "arquivo": filename,
        "tamanho_bytes": size,
        "removidos": removed,
    }


@celery_app.task(name="listar_backups")
def listar_backups() -> list[dict]:
    """Lista arquivos de backup ordenados do mais novo para o mais antigo."""
    settings = get_settings()
    base = Path(settings.effective_backup_path)
    if not base.exists():
        return []
    items: list[dict] = []
    for f in sorted(base.glob("backup_*.dump"), key=lambda p: p.stat().st_mtime, reverse=True):
        items.append(
            {
                "nome": f.name,
                "caminho": str(f),
                "tamanho_bytes": f.stat().st_size,
                "modificado_em": datetime.fromtimestamp(
                    f.stat().st_mtime, tz=ZoneInfo(settings.app_timezone)
                ).isoformat(),
            }
        )
    return items


# Suporte a `python -m src.tasks.backup_task` para teste manual
if __name__ == "__main__":  # pragma: no cover
    resultado = backup_diario.apply().get()
    print(resultado)
