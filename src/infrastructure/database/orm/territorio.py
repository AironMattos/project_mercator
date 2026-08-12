from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class DimTerritorio(Base):
    __tablename__ = "dim_territorio"
    __table_args__ = {"schema": "canonical"}

    territorio_id: Mapped[str] = mapped_column(Text, primary_key=True)
    nivel: Mapped[str] = mapped_column(Text, nullable=False)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    nome_alternativo: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    geometria: Mapped[str | None] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True
    )
    territorio_pai_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("canonical.dim_territorio.territorio_id"), nullable=True
    )
    cidade_id: Mapped[str] = mapped_column(
        String, nullable=False, server_default="curitiba"
    )
