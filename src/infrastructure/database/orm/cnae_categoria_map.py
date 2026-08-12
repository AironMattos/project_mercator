from __future__ import annotations

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class CnaeCategoriaMap(Base):
    __tablename__ = "cnae_categoria_map"
    __table_args__ = {"schema": "canonical"}

    codigo_cnae: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical.dim_cnae.codigo_cnae"), primary_key=True
    )
    categoria_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical.dim_categoria.categoria_id"), primary_key=True
    )
