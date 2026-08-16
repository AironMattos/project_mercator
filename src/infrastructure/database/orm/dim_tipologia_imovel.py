from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class DimTipologiaImovel(Base):
    """Tradução versionada de tipologia (Radar de Anúncios, checkpoint
    12c) - mesmo espírito de dim_categoria (Radar de Comércio): tabela de
    referência pequena e explícita, nunca um `if` disperso no parser de
    cada conector (ver domain/anuncio/taxonomia.py)."""

    __tablename__ = "dim_tipologia_imovel"
    __table_args__ = {"schema": "canonical"}

    tipologia_id: Mapped[str] = mapped_column(Text, primary_key=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
