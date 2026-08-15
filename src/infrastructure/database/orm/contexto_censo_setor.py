from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class ContextoCensoSetor(Base):
    """Agregados básicos do Censo Demográfico 2022 por setor censitário,
    em Curitiba (checkpoint 11d) - ver
    domain.contexto.IndicadorCensitarioSetor. Fonte estática (Censo só se
    repete a cada ~10 anos) - PK natural (setor_censitario), upsert
    simples, sem vigencia_inicio/fim (diferente de
    valor_referencia_territorial, que tem revisões periódicas reais)."""

    __tablename__ = "contexto_censo_setor"
    __table_args__ = {"schema": "canonical"}

    setor_censitario: Mapped[str] = mapped_column(Text, primary_key=True)
    territorio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("canonical.dim_territorio.territorio_id"), nullable=True
    )
    municipio_codigo: Mapped[str] = mapped_column(Text, nullable=False)
    area_km2: Mapped[float] = mapped_column(Numeric, nullable=False)
    populacao_total: Mapped[int] = mapped_column(Integer, nullable=False)
    domicilios_total: Mapped[int] = mapped_column(Integer, nullable=False)
    domicilios_particulares_ocupados: Mapped[int] = mapped_column(Integer, nullable=False)
    domicilios_particulares_vagos: Mapped[int] = mapped_column(Integer, nullable=False)
    ano_referencia: Mapped[int] = mapped_column(Integer, nullable=False)
    fonte_id: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_ref: Mapped[str] = mapped_column(Text, nullable=False)
