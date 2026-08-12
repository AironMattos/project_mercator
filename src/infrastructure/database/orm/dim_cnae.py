from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class DimCnae(Base):
    __tablename__ = "dim_cnae"
    __table_args__ = {"schema": "canonical"}

    codigo_cnae: Mapped[str] = mapped_column(Text, primary_key=True)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    secao: Mapped[str | None] = mapped_column(Text, nullable=True)
    divisao: Mapped[str | None] = mapped_column(Text, nullable=True)
    grupo: Mapped[str | None] = mapped_column(Text, nullable=True)
    classe: Mapped[str | None] = mapped_column(Text, nullable=True)
    subclasse: Mapped[str | None] = mapped_column(Text, nullable=True)
