import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class MembroModel(Base):
    __tablename__ = "membros"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    telefone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    categoria: Mapped[str] = mapped_column(String(50), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class ArquivoModel(Base):
    __tablename__ = "arquivos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nome_original: Mapped[str | None] = mapped_column(String(300))
    caminho: Mapped[str] = mapped_column(String(500), nullable=False)
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    tamanho_bytes: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())


class ContribuicaoModel(Base):
    __tablename__ = "contribuicoes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    protocolo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    membro_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("membros.id"))
    telefone: Mapped[str] = mapped_column(String(20), nullable=False)
    valor: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    data_pagamento: Mapped[date] = mapped_column(Date, nullable=False)
    hora_pagamento: Mapped[time | None] = mapped_column(Time)
    banco: Mapped[str | None] = mapped_column(String(100))
    confianca: Mapped[float | None] = mapped_column(Numeric(3, 2))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    hash_imagem: Mapped[str] = mapped_column(String(64), unique=True)
    arquivo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("arquivos.id"))
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class PendenciaModel(Base):
    __tablename__ = "pendencias"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contribuicao_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contribuicoes.id")
    )
    telefone: Mapped[str | None] = mapped_column(String(20))
    motivo: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="aberto")
    observacao: Mapped[str | None] = mapped_column(Text)
    resolvido_por: Mapped[str | None] = mapped_column(String(100))
    resolvido_em: Mapped[datetime | None] = mapped_column()
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())


class AuditoriaModel(Base):
    __tablename__ = "auditoria"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now())
    evento: Mapped[str] = mapped_column(String(100), nullable=False)
    contribuicao_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contribuicoes.id")
    )
    telefone: Mapped[str | None] = mapped_column(String(20))
    detalhes: Mapped[dict | None] = mapped_column(JSON)
    nivel: Mapped[str] = mapped_column(String(10), default="info")


class MensagemRecebidaModel(Base):
    __tablename__ = "mensagens_recebidas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    telefone: Mapped[str] = mapped_column(String(20), nullable=False)
    whatsapp_msg_id: Mapped[str] = mapped_column(String(100), unique=True)
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now())
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    texto: Mapped[str | None] = mapped_column(Text)
    media_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="recebida")


class SequenciaModel(Base):
    __tablename__ = "sequencias"

    data: Mapped[date] = mapped_column(Date, primary_key=True)
    ultimo_numero: Mapped[int] = mapped_column(Integer, default=0)


class UsuarioAdminModel(Base):
    __tablename__ = "usuarios_admin"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    perfil: Mapped[str] = mapped_column(String(20), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
