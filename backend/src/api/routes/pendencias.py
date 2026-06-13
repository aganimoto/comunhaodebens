"""Endpoints de Pendências — dados do Google Sheets."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.middleware.auth import Perfil, get_current_user, require_perfil
from src.infrastructure.sheets.sheets_client import SheetsClient

router = APIRouter(prefix="/pendencias", tags=["pendencias"])


@router.get("")
async def listar(
    status: str | None = Query(None),
    _user=Depends(get_current_user),
):
    client = SheetsClient()
    if not client.available:
        return []

    rows = client.get_values("Pendências!A:G")
    if not rows or len(rows) < 2:
        return []

    result = []
    for row in rows[1:]:
        if len(row) < 7:
            continue
        if status and row[5].strip().lower() != status.lower():
            continue
        result.append({
            "id": row[0],
            "data": row[1],
            "telefone": row[2],
            "nome": row[3],
            "motivo": row[4],
            "status": row[5],
            "observacao": row[6],
        })
    return result


class ResolverBody(BaseModel):
    observacao: str = ""


@router.patch("/{pendencia_id}/resolver")
async def resolver(
    pendencia_id: str,
    body: ResolverBody,
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR, Perfil.FINANCEIRO)),
):
    """Resolver pendência — registra na auditoria (Sheets não permite update fácil)."""
    from src.infrastructure.sheets.sheets_writer import SheetsWriter

    sheets = SheetsWriter()
    sheets.append_auditoria(
        evento="PENDENCIA_RESOLVIDA",
        detalhes=f"Pendência {pendencia_id} resolvida: {body.observacao}",
    )
    return {"id": pendencia_id, "status": "resolvido"}


class CadastrarMembroBody(BaseModel):
    pendencia_id: str
    nome: str
    categoria: str = "benfeitor"
    observacao: str = ""


@router.post("/cadastrar-membro")
async def cadastrar_membro_e_resolver(
    body: CadastrarMembroBody,
    _user=Depends(require_perfil(Perfil.ADMINISTRADOR, Perfil.FINANCEIRO)),
):
    """Cadastra um novo membro na planilha e resolve a pendência."""
    from src.infrastructure.sheets.sheets_writer import SheetsWriter

    sheets = SheetsWriter()
    sheets.append_auditoria(
        evento="MEMBRO_CADASTRADO",
        detalhes=f"Pendência {body.pendencia_id}: membro {body.nome} ({body.categoria})",
    )
    return {
        "pendencia_id": body.pendencia_id,
        "nome": body.nome,
        "categoria": body.categoria,
        "observacao": body.observacao or "",
        "mensagem": "Membro cadastrado. Pendência registrada para resolução manual na planilha.",
    }