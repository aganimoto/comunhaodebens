"""Cria o primeiro usuário administrador (idempotente).

Uso:
    docker compose exec backend python scripts/create_admin.py
    python scripts/create_admin.py              (dev local — lê DATABASE_URL do env)

Lê as variáveis do .env via Settings (database_url, bootstrap_admin_*).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

# Suporte a dev local: se DEV_MODE=true e não houver DATABASE_URL definida,
# usa SQLite local automaticamente.
_backend_root = Path(__file__).resolve().parents[1]
_dev_db = (_backend_root / "dev_data" / "local.db").as_posix()
if os.environ.get("DEV_MODE") == "true" and not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_dev_db}"

import bcrypt
from sqlalchemy import select

from src.config import get_settings
from src.infrastructure.database.connection import async_session_factory
from src.infrastructure.database.models import UsuarioAdminModel


def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cria/atualiza um usuário admin")
    settings = get_settings()
    parser.add_argument("--email", default=settings.bootstrap_admin_email)
    parser.add_argument("--senha", default=settings.bootstrap_admin_password)
    parser.add_argument(
        "--perfil",
        default=settings.bootstrap_admin_perfil,
        choices=["administrador", "financeiro", "consulta"],
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Atualiza a senha mesmo se o admin já existir",
    )
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    if not args.email or not args.senha:
        print("ERRO: informe --email e --senha (ou defina no .env)", file=sys.stderr)
        return 2

    if len(args.senha) < 8:
        print("ERRO: a senha deve ter ao menos 8 caracteres", file=sys.stderr)
        return 2

    senha_hash = _hash_senha(args.senha)

    async with async_session_factory() as session:
        result = await session.execute(
            select(UsuarioAdminModel).where(UsuarioAdminModel.email == args.email)
        )
        existing = result.scalar_one_or_none()

        if existing:
            if args.force:
                existing.senha_hash = senha_hash
                existing.perfil = args.perfil
                existing.ativo = True
                await session.commit()
                print(f"OK: admin '{args.email}' atualizado (perfil={args.perfil}).")
            else:
                print(
                    f"AVISO: admin '{args.email}' já existe. Use --force para atualizar.",
                    file=sys.stderr,
                )
            return 0

        admin = UsuarioAdminModel(
            id=uuid4(),
            email=args.email,
            senha_hash=senha_hash,
            perfil=args.perfil,
            ativo=True,
        )
        session.add(admin)
        await session.commit()
        print(f"OK: admin '{args.email}' criado (perfil={args.perfil}).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
