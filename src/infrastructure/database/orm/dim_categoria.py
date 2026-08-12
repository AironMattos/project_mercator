from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class DimCategoria(Base):
    __tablename__ = "dim_categoria"
    __table_args__ = {"schema": "canonical"}

    categoria_id: Mapped[str] = mapped_column(Text, primary_key=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
