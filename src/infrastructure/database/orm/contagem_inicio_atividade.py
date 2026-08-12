from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class ContagemInicioAtividade(Base):
    """Feature derivada de canonical.observacao_entidade.atributos->>'inicio_atividade'
    (não de events.fato_evento_territorial - ver checkpoint 8b em
    CLAUDE.md sobre por que aberturas usa essa fonte, que tem
    profundidade real de anos mesmo com poucos snapshots de evento
    processados). Totalmente recomputável (delete + insert a cada
    execução), por isso sem chave de negócio como PK - mesmo padrão de
    ContagemEventos.

    Existe porque a query de origem (DISTINCT ON sobre ~515 mil
    observações, deduplicando por entidade) é cara demais pra rodar ao
    vivo a cada request de /ranking/comercio ou /bairros/{id}/resumo -
    achado medindo o tempo de resposta real (10-12s) depois do checkpoint
    8d ir ao ar.
    """

    __tablename__ = "contagem_inicio_atividade"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    territorio_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical.dim_territorio.territorio_id"), nullable=False
    )
    categoria_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("canonical.dim_categoria.categoria_id"), nullable=True
    )
    mes: Mapped[date] = mapped_column(Date, nullable=False)
    contagem: Mapped[int] = mapped_column(Integer, nullable=False)
    calculado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
