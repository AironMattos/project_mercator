from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class GeolocalizacaoEntidade(Base):
    """Uma linha por entidade_id, não por observação - o endereço não
    muda entre observações da mesma entidade (mesma disciplina dos
    pilotos de geocodificação: geocodifica uma vez, reaproveita)."""

    __tablename__ = "geolocalizacao_entidade"
    __table_args__ = (
        CheckConstraint(
            "confianca IN ('alta','media','baixa')",
            name="geolocalizacao_entidade_confianca_check",
        ),
        {"schema": "canonical"},
    )

    entidade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical.entidade.entidade_id"),
        primary_key=True,
    )
    ponto: Mapped[str | None] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    confianca: Mapped[str] = mapped_column(Text, nullable=False)
    fonte_primaria: Mapped[str] = mapped_column(Text, nullable=False)
    fonte_secundaria: Mapped[str | None] = mapped_column(Text, nullable=True)
    precisao_geocodebr: Mapped[str | None] = mapped_column(Text, nullable=True)
    distancia_desempate_m: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    geocodificado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revisado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
