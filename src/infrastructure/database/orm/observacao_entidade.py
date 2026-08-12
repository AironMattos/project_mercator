from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class ObservacaoEntidade(Base):
    __tablename__ = "observacao_entidade"
    __table_args__ = (
        # Uma entidade tem no máximo uma observação por fonte e por data de
        # referência do snapshot - reprocessar o mesmo snapshot não deve
        # duplicar "o que sabíamos, e quando".
        UniqueConstraint("entidade_id", "fonte_id", "observado_em"),
        {"schema": "canonical"},
    )

    observacao_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    entidade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical.entidade.entidade_id"),
        nullable=False,
    )
    observado_em: Mapped[date] = mapped_column(Date, nullable=False)
    atributos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fonte_id: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_ref: Mapped[str] = mapped_column(Text, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
