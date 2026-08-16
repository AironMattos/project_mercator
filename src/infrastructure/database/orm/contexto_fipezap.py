from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base

# Índice FipeZAP publica venda e locação como relatórios (e cestas de
# cidades) separados - nunca combinar as duas na mesma linha nem no
# mesmo agregado, mesmo espírito de operacao em canonical.observacao_anuncio.
_OPERACOES_CHECK = "operacao IN ('venda','locacao')"


class ContextoFipezapCidade(Base):
    """Leitura mensal de nível cidade do Índice FipeZAP (checkpoint 12b)
    - ver domain.contexto.IndicadorFipezapCidade. **Uso estritamente
    interno** (nunca uma rota de API pública lê esta tabela) - segunda
    régua de validação contra o preço pedido calculado a partir dos
    anúncios coletados, não um dado redistribuível (Fipe não publica
    licença de redistribuição, só o PDF mensal em si)."""

    __tablename__ = "contexto_fipezap_cidade"
    __table_args__ = (
        CheckConstraint(_OPERACOES_CHECK, name="contexto_fipezap_cidade_operacao_check"),
        UniqueConstraint("cidade", "operacao", "periodo_referencia"),
        {"schema": "canonical"},
    )

    registro_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    cidade: Mapped[str] = mapped_column(Text, nullable=False)
    operacao: Mapped[str] = mapped_column(Text, nullable=False)
    periodo_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    preco_medio_m2: Mapped[float] = mapped_column(Numeric, nullable=False)
    variacao_mensal: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    variacao_acumulada_ano: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    variacao_12m: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    fonte_id: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_ref: Mapped[str] = mapped_column(Text, nullable=False)


class ContextoFipezapBairro(Base):
    """Um dos bairros mais representativos de uma cidade no Índice
    FipeZAP (checkpoint 12b) - ver domain.contexto.IndicadorFipezapBairro.
    Mesma restrição de uso interno da tabela de cidade acima. Sem FK para
    dim_territorio (mesmo padrão de fonte_id em todo o projeto desde o
    Checkpoint 11b - resolução best-effort, `territorio_id` fica NULL
    quando não resolvido, nunca bloqueia o insert)."""

    __tablename__ = "contexto_fipezap_bairro"
    __table_args__ = (
        CheckConstraint(_OPERACOES_CHECK, name="contexto_fipezap_bairro_operacao_check"),
        UniqueConstraint("cidade", "operacao", "periodo_referencia", "bairro_nome"),
        {"schema": "canonical"},
    )

    registro_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    cidade: Mapped[str] = mapped_column(Text, nullable=False)
    operacao: Mapped[str] = mapped_column(Text, nullable=False)
    periodo_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    bairro_nome: Mapped[str] = mapped_column(Text, nullable=False)
    preco_medio_m2: Mapped[float] = mapped_column(Numeric, nullable=False)
    variacao_12m: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    territorio_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    fonte_id: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_ref: Mapped[str] = mapped_column(Text, nullable=False)
