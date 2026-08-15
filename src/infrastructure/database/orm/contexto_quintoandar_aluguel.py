from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class ContextoQuintoandarAluguel(Base):
    """Leitura mensal do Índice QuintoAndar/Imovelweb de aluguel por
    cidade/segmento (checkpoint 11d) - ver
    domain.contexto.IndicadorAluguelMercado. Deliberadamente sem
    tipo_valor: aluguel não é uma das quatro grandezas de
    domain.valuation (todas sobre preço de compra)."""

    __tablename__ = "contexto_quintoandar_aluguel"
    __table_args__ = (
        CheckConstraint(
            "segmento IN ('cidade_toda','1_dormitorio','2_dormitorios','3_dormitorios')",
            name="contexto_quintoandar_aluguel_segmento_check",
        ),
        # Série mensal publicada pela QuintoAndar/Imovelweb - reprocessar
        # o mesmo mês não duplica a leitura (mesma disciplina de
        # contexto_bcb_imobiliario).
        UniqueConstraint("cidade", "periodo_referencia", "segmento"),
        {"schema": "canonical"},
    )

    registro_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    cidade: Mapped[str] = mapped_column(Text, nullable=False)
    periodo_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    segmento: Mapped[str] = mapped_column(Text, nullable=False)
    aluguel_m2: Mapped[float] = mapped_column(Numeric, nullable=False)
    variacao_mensal: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    variacao_12m: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    fonte_id: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_ref: Mapped[str] = mapped_column(Text, nullable=False)
