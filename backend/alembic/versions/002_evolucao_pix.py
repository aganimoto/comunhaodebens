"""Evolucao PIX — Fase 4

Revision ID: 002
Revises: 001
Create Date: 2026-06-05

Mudanças:

* Adiciona colunas ``ocr_texto_bruto``, ``ocr_dados_json`` e
  ``ocr_confianca_media`` em ``contribuicoes`` para auditoria/observabilidade
  (a imagem, o texto OCR bruto e o JSON da IA nunca são descartados).
* Renomeia ``contribuicoes.status = 'revisao'`` para ``'pendente'`` (Fase 4).
  ``REVISAO`` continua aceito pela camada de aplicação via alias.
* Torna ``arquivos.hash_sha256`` ``UNIQUE`` para garantir idempotência
  ao tentar popular o mesmo arquivo duas vezes (Fase 4).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Novas colunas em contribuicoes
    op.add_column(
        "contribuicoes",
        sa.Column("ocr_texto_bruto", sa.Text(), nullable=True),
    )
    op.add_column(
        "contribuicoes",
        sa.Column("ocr_dados_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "contribuicoes",
        sa.Column("ocr_confianca_media", sa.Numeric(3, 2), nullable=True),
    )

    # 2) Migração de dados: REVISAO -> PENDENTE
    op.execute(
        "UPDATE contribuicoes SET status = 'pendente' WHERE status = 'revisao'"
    )

    # 3) Remover duplicatas existentes mantendo o mais antigo
    # (UNIQUE já definido na migration 001)
    op.execute(
        """
        DELETE FROM arquivos
        WHERE rowid NOT IN (
            SELECT MIN(rowid) FROM arquivos GROUP BY hash_sha256
        )
        """
    )


def downgrade() -> None:
    # 2) Reverter PENDENTE -> REVISAO (não totalmente seguro, mas simétrico)
    op.execute(
        "UPDATE contribuicoes SET status = 'revisao' WHERE status = 'pendente'"
    )

    # 1) Remover colunas
    op.drop_column("contribuicoes", "ocr_confianca_media")
    op.drop_column("contribuicoes", "ocr_dados_json")
    op.drop_column("contribuicoes", "ocr_texto_bruto")
