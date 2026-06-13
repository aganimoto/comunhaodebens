"""Autenticação JWT — usuário único definido via variáveis de ambiente."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from jose import jwt
from pydantic import BaseModel, Field

from src.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


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
async def login(body: LoginRequest):
    settings = get_settings()

    # Usuário único definido nas configurações
    if body.email != settings.bootstrap_admin_email:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    # Comparação direta de senha (sem bcrypt, já que é único admin via env var)
    if body.senha != settings.bootstrap_admin_password:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    return TokenResponse(
        access_token=_create_token(body.email, settings.bootstrap_admin_perfil)
    )


@router.post("/logout")
async def logout():
    return {"ok": True}


@router.post("/refresh", response_model=TokenResponse)
async def refresh():
    raise HTTPException(status_code=501, detail="Implementar com refresh token")