from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class ContagemEventos(Base):
    """Feature derivada de events.fato_evento_territorial - totalmente
    recomputável (truncate + insert a cada execução), por isso não tem
    chave de negócio como PK (territorio_id/categoria_id podem ser nulos).
    """

    __tablename__ = "contagem_eventos"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    territorio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("canonical.dim_territorio.territorio_id"), nullable=True
    )
    categoria_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("canonical.dim_categoria.categoria_id"), nullable=True
    )
    mes: Mapped[date] = mapped_column(Date, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    contagem: Mapped[int] = mapped_column(Integer, nullable=False)
    calculado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
