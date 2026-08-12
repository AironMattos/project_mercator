from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class FatoEventoTerritorial(Base):
    __tablename__ = "fato_evento_territorial"
    __table_args__ = (
        CheckConstraint(
            "confianca IN ('alta','media','baixa')",
            name="fato_evento_territorial_confianca_check",
        ),
        # Reprocessar o mesmo par de snapshots não deve duplicar o mesmo
        # evento já inferido para a mesma entidade na mesma data.
        UniqueConstraint("entidade_id", "event_type", "data_evento"),
        {"schema": "events"},
    )

    evento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    entidade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical.entidade.entidade_id"),
        nullable=False,
    )
    territorio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("canonical.dim_territorio.territorio_id"), nullable=True
    )
    data_evento: Mapped[date] = mapped_column(Date, nullable=False)
    data_ingestao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    confianca: Mapped[str] = mapped_column(Text, nullable=False)
    origem_observacoes: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
