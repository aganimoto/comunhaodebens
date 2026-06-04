from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
import bcrypt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import UsuarioAdminModel

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def _verificar_senha(senha: str, hash_senha: str) -> bool:
    return bcrypt.checkpw(senha.encode(), hash_senha.encode())


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _create_token(subject: str, perfil: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    return jwt.encode(
        {"sub": subject, "perfil": perfil, "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db_session)):
    q = await session.execute(
        select(UsuarioAdminModel).where(
            UsuarioAdminModel.email == body.email,
            UsuarioAdminModel.ativo.is_(True),
        )
    )
    user = q.scalar_one_or_none()
    if not user or not _verificar_senha(body.senha, user.senha_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    return TokenResponse(access_token=_create_token(user.email, user.perfil))


@router.post("/logout")
async def logout():
    return {"ok": True}


@router.post("/refresh", response_model=TokenResponse)
async def refresh():
    raise HTTPException(status_code=501, detail="Implementar com refresh token")
