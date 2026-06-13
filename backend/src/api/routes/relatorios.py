"""Endpoints para consulta e geração de relatórios PDF."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.api.middleware.auth import Perfil, get_current_user, require_perfil
from src.config import get_settings

router = APIRouter(prefix="/relatorios", tags=["relatorios"])


class GerarBody(BaseModel):
    ano: int | None = None
    mes: int | None = None


def _base_dir() -> Path:
    return Path(get_settings().effective_relatorios_path)


@router.get("")
async def listar(_user=Depends(get_current_user)):
    base = _base_dir()
    if not base.exists():
        return []
    items = []
    for pdf in sorted(base.glob("relatorio_*.pdf"), reverse=True):
        stat = pdf.stat()
        items.append(
            {
                "caminho": str(pdf),
                "nome": pdf.name,
                "tamanho_bytes": stat.st_size,
                "modificado_em": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )
    return items


@router.get("/{relatorio_id}/download")
async def download(relatorio_id: str, _user=Depends(get_current_user)):
    base = _base_dir()
    # Segurança: aceitar somente o nome do arquivo (sem path traversal)
    if "/" in relatorio_id or ".." in relatorio_id:
        raise HTTPException(400, "Identificador inválido")
    path = base / relatorio_id
    if not path.exists() or path.suffix != ".pdf" or not path.is_file():
        raise HTTPException(404, "Relatório não encontrado")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


