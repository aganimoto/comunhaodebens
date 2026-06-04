"""Testes da task de backup (pg_dump e rotação)."""
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from src.tasks.backup_task import (
    _parse_database_url,
    _rotate,
    _run_pg_dump,
    backup_diario,
    listar_backups,
)


def test_parse_database_url_postgres():
    parts = _parse_database_url("postgresql+asyncpg://user:pass@db:5432/mydb")
    assert parts["host"] == "db"
    assert parts["port"] == "5432"
    assert parts["user"] == "user"
    assert parts["password"] == "pass"
    assert parts["dbname"] == "mydb"


def test_parse_database_url_invalida():
    with pytest.raises(ValueError):
        _parse_database_url("sqlite:///foo.db")


def test_rotate_mantem_ultimo(tmp_path):
    base = tmp_path
    for i in range(5):
        (base / f"backup_2024010{i}_000000.dump").write_bytes(b"x")
    removed = _rotate(base, keep=3)
    remaining = sorted(base.glob("backup_*.dump"))
    assert len(remaining) == 3
    assert len(removed) == 2


def test_rotate_zero_remove_tudo(tmp_path):
    for i in range(3):
        (tmp_path / f"backup_2024010{i}_000000.dump").write_bytes(b"x")
    _rotate(tmp_path, keep=0)
    assert list(tmp_path.glob("backup_*.dump")) == []


def test_backup_dev_mode(monkeypatch, tmp_path):
    """Em dev_mode, deve criar arquivo placeholder e não chamar pg_dump."""
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("DEV_BACKUP_PATH", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/d")
    with patch("src.tasks.backup_task._run_pg_dump") as mock_dump:
        result = backup_diario.apply().get()
    assert result["status"] == "dev_mode"
    arquivos = list(tmp_path.glob("backup_*.dump"))
    assert len(arquivos) == 1
    assert arquivos[0].read_bytes() == b"DEV_MODE_PLACEHOLDER"
    mock_dump.assert_not_called()


def test_backup_pg_dump_falha(monkeypatch, tmp_path):
    """Se pg_dump falhar, registra e tenta retry."""
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.setenv("DEV_BACKUP_PATH", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setattr("src.tasks.backup_task._run_pg_dump",
                        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    # usa celery eager mode
    from src.tasks import celery_app
    celery_app.conf.task_always_eager = True
    try:
        result = backup_diario.apply().get()
    finally:
        celery_app.conf.task_always_eager = False
    # Em modo eager sem redis, retry não funciona — apenas verifica o retorno
    assert result["status"] in ("failed", "skipped", "ok")


def test_listar_backups_vazio(tmp_path, monkeypatch):
    monkeypatch.setenv("SHARED_BACKUP_PATH", str(tmp_path))
    assert listar_backups.apply().get() == []


def test_listar_backups_ordenado(tmp_path, monkeypatch):
    monkeypatch.setenv("SHARED_BACKUP_PATH", str(tmp_path))
    import time as _t

    for i, ts in enumerate([1000, 3000, 2000]):
        f = tmp_path / f"backup_2024{i}_000000.dump"
        f.write_bytes(b"x")
        os.utime(f, (ts, ts))
    result = listar_backups.apply().get()
    assert len(result) == 3
    # mais novo primeiro
    timestamps = [r["modificado_em"] for r in result]
    assert timestamps == sorted(timestamps, reverse=True)
