"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "membros",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telefone", sa.String(20), nullable=False, unique=True),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("categoria", sa.String(50), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default="true"),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "arquivos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nome_original", sa.String(300)),
        sa.Column("caminho", sa.String(500), nullable=False),
        sa.Column("hash_sha256", sa.String(64), nullable=False),
        sa.Column("tamanho_bytes", sa.Integer()),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "sequencias",
        sa.Column("data", sa.Date(), primary_key=True),
        sa.Column("ultimo_numero", sa.Integer(), server_default="0"),
    )
    op.create_table(
        "usuarios_admin",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("senha_hash", sa.String(200), nullable=False),
        sa.Column("perfil", sa.String(20), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default="true"),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "contribuicoes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("protocolo", sa.String(20), nullable=False, unique=True),
        sa.Column("membro_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("membros.id")),
        sa.Column("telefone", sa.String(20), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("data_pagamento", sa.Date(), nullable=False),
        sa.Column("hora_pagamento", sa.Time()),
        sa.Column("banco", sa.String(100)),
        sa.Column("confianca", sa.Numeric(3, 2)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("hash_imagem", sa.String(64), nullable=False, unique=True),
        sa.Column("arquivo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("arquivos.id")),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "pendencias",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contribuicao_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contribuicoes.id")),
        sa.Column("telefone", sa.String(20)),
        sa.Column("motivo", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="aberto"),
        sa.Column("observacao", sa.Text()),
        sa.Column("resolvido_por", sa.String(100)),
        sa.Column("resolvido_em", sa.DateTime(timezone=True)),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "auditoria",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("evento", sa.String(100), nullable=False),
        sa.Column("contribuicao_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contribuicoes.id")),
        sa.Column("telefone", sa.String(20)),
        sa.Column("detalhes", postgresql.JSONB()),
        sa.Column("nivel", sa.String(10), server_default="info"),
    )
    op.create_table(
        "mensagens_recebidas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telefone", sa.String(20), nullable=False),
        sa.Column("whatsapp_msg_id", sa.String(100), nullable=False, unique=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("texto", sa.Text()),
        sa.Column("media_path", sa.String(500)),
        sa.Column("status", sa.String(20), server_default="recebida"),
    )


def downgrade() -> None:
    op.drop_table("mensagens_recebidas")
    op.drop_table("auditoria")
    op.drop_table("pendencias")
    op.drop_table("contribuicoes")
    op.drop_table("usuarios_admin")
    op.drop_table("sequencias")
    op.drop_table("arquivos")
    op.drop_table("membros")
