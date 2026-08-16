from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base

# Mesmo motivo do import espelhado em observacao_anuncio.py - garante que
# o alvo do FK abaixo (territorio_id) está registrado em Base.metadata
# independente de quem importa este módulo primeiro.
from infrastructure.database.orm import territorio  # noqa: F401,E402


class TermometroAnuncio(Base):
    """Termômetro do Radar de Anúncios (checkpoint 12f, seção 2 do prompt
    de referência) - uma célula bairro × tipologia × operação × mês.

    100% derivada de `events.fato_evento_territorial` e
    `canonical.observacao_anuncio` (via `imovel_resolvido`) - `id`
    sintético (sem chave de negócio, mesmo padrão de
    `analytics.contagem_eventos`), recomputada do zero (`DELETE` +
    `INSERT`) a cada execução de `run_termometro_anuncio.py`, nunca
    atualizada linha a linha.

    **Limitação de desenho documentada, não escondida**: `estoque`,
    `preco_*` e `preco_m2_*` refletem o estado *no momento em que o
    pipeline rodou* (não existe ainda uma série histórica de estoque por
    mês - isso exigiria um snapshot de estoque capturado periodicamente,
    que só passa a existir depois de várias execuções reais ao longo do
    tempo). `novos_anuncios`/`encerrados` já são de verdade por mês
    (vêm de `data_evento`), mas hoje só há eventos no mês corrente.
    """

    __tablename__ = "termometro_anuncio"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    territorio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("canonical.dim_territorio.territorio_id"), nullable=True
    )
    tipologia: Mapped[str] = mapped_column(Text, nullable=False)
    operacao: Mapped[str] = mapped_column(Text, nullable=False)
    mes: Mapped[date] = mapped_column(Date, nullable=False)

    novos_anuncios: Mapped[int] = mapped_column(Integer, nullable=False)
    encerrados: Mapped[int] = mapped_column(Integer, nullable=False)
    estoque: Mapped[int] = mapped_column(Integer, nullable=False)

    novos_por_mil_domicilios: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    rotacao_oferta: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    renovacao: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    permanencia_mediana_dias: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    pressao_preco_pct_subiu: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    pressao_preco_pct_desceu: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    pressao_preco_variacao_mediana_pct: Mapped[float | None] = mapped_column(
        Numeric, nullable=True
    )

    preco_mediano: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    preco_p25: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    preco_p75: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    preco_m2_mediano: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    preco_m2_p25: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    preco_m2_p75: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    amostra_preco_suficiente: Mapped[bool] = mapped_column(Boolean, nullable=False)

    quadrante: Mapped[str | None] = mapped_column(Text, nullable=True)
