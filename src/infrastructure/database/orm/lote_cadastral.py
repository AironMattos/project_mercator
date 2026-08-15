from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class LoteCadastral(Base):
    """Dimensão de lote (GeoCuritiba/MapaCadastral, layer "Lote Cadastral"
    - checkpoint 11a/11c). Existe para resolver território/zoneamento por
    Indicação Fiscal/Inscrição Imobiliária - a mesma chave que o relatório
    de Alvará/CVCO da SMU carrega, sem geocodificação nenhuma (achado do
    checkpoint 11a).

    PK é objectid_fonte (o id estável do ArcGIS), não indicacao_fiscal:
    confirmado contra dado real que ~0,09% dos lotes (265 de 308.882) têm
    Indicação Fiscal em branco - inutilizável como chave primária.
    indicacao_fiscal fica como coluna indexada, não única, para o join.

    Upsert por objectid_fonte (mesmo padrão de dim_territorio) - é uma
    dimensão, não um log de observação; um lote pode ser resubdividido e
    a linha correspondente atualizada, não versionada.
    """

    __tablename__ = "lote_cadastral"
    __table_args__ = {"schema": "canonical"}

    objectid_fonte: Mapped[int] = mapped_column(primary_key=True)
    indicacao_fiscal: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    inscricao_imobiliaria: Mapped[str | None] = mapped_column(Text, nullable=True)
    area_terreno: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    nome_bairro: Mapped[str | None] = mapped_column(Text, nullable=True)
    territorio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("canonical.dim_territorio.territorio_id"), nullable=True
    )
    sigla_zoneamento: Mapped[str | None] = mapped_column(Text, nullable=True)
    geometria: Mapped[str | None] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True
    )
    fonte_id: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_ref: Mapped[str] = mapped_column(Text, nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
