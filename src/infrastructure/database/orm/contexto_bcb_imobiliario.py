from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class ContextoBcbImobiliario(Base):
    """Leitura mensal de uma série do serviço MercadoImobiliario do BCB,
    granularidade UF (checkpoint 11d) - ver
    domain.valuation.IndicadorMercadoImobiliarioUf para a regra de
    categoria/tipo_valor. Nunca uma coluna genérica "valor"/"preco" -
    'leitura' é deliberadamente neutra (pode ser R$, m² ou contagem,
    sempre desambiguada por categoria+unidade)."""

    __tablename__ = "contexto_bcb_imobiliario"
    __table_args__ = (
        CheckConstraint(
            "categoria IN ('valor','area','contagem')",
            name="contexto_bcb_imobiliario_categoria_check",
        ),
        CheckConstraint(
            "tipo_valor IS NULL OR tipo_valor IN ('venal','avaliacao','anuncio','transacao')",
            name="contexto_bcb_imobiliario_tipo_valor_check",
        ),
        # Série mensal publicada pelo BCB - reprocessar o mesmo mês não
        # duplica a leitura (ON CONFLICT DO NOTHING no insert, mesma
        # disciplina de imutabilidade de observacao_entidade).
        UniqueConstraint("uf", "periodo_referencia", "indicador"),
        {"schema": "canonical"},
    )

    registro_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    uf: Mapped[str] = mapped_column(Text, nullable=False)
    periodo_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    indicador: Mapped[str] = mapped_column(Text, nullable=False)
    categoria: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_valor: Mapped[str | None] = mapped_column(Text, nullable=True)
    unidade: Mapped[str] = mapped_column(Text, nullable=False)
    leitura: Mapped[float] = mapped_column(Numeric, nullable=False)
    fonte_id: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_ref: Mapped[str] = mapped_column(Text, nullable=False)
