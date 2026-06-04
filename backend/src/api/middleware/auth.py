from enum import Enum

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.config import get_settings

security = HTTPBearer()


class Perfil(str, Enum):
    ADMINISTRADOR = "administrador"
    FINANCEIRO = "financeiro"
    CONSULTA = "consulta"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return {"email": payload.get("sub"), "perfil": payload.get("perfil")}
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Token inválido") from e


def require_perfil(*perfis: Perfil):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("perfil") not in [p.value for p in perfis]:
            raise HTTPException(status_code=403, detail="Permissão negada")
        return user

    return checker
