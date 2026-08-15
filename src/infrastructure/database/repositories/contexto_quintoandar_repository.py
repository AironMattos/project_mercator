from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.contexto import IndicadorAluguelMercado
from infrastructure.database.orm.contexto_quintoandar_aluguel import (
    ContextoQuintoandarAluguel,
)


def inserir_indicadores_aluguel(
    session: Session, indicadores: list[IndicadorAluguelMercado]
) -> int:
    """Grava leituras mensais do índice QuintoAndar de forma idempotente
    por (cidade, periodo_referencia, segmento) - mesma disciplina de
    contexto_bcb_repository."""
    if not indicadores:
        return 0

    rows = [
        {
            "cidade": i.cidade,
            "periodo_referencia": i.periodo_referencia,
            "segmento": i.segmento,
            "aluguel_m2": i.aluguel_m2,
            "variacao_mensal": i.variacao_mensal,
            "variacao_12m": i.variacao_12m,
            "fonte_id": i.fonte_id,
            "snapshot_ref": i.snapshot_ref,
        }
        for i in indicadores
    ]

    stmt = insert(ContextoQuintoandarAluguel).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["cidade", "periodo_referencia", "segmento"]
    )
    result = session.execute(stmt)
    return result.rowcount or 0


def consultar_ultimo_periodo(
    session: Session, cidade: str = "Curitiba"
) -> tuple[date | None, list[dict]]:
    """Os segmentos do índice de aluguel no mês mais recente disponível
    para `cidade` - granularidade cidade explícita no retorno."""
    tabela = ContextoQuintoandarAluguel
    ultimo = session.execute(
        select(func.max(tabela.periodo_referencia)).where(tabela.cidade == cidade)
    ).scalar()
    if ultimo is None:
        return None, []

    stmt = select(tabela).where(tabela.cidade == cidade, tabela.periodo_referencia == ultimo)
    itens = [
        {
            "segmento": row.segmento,
            "aluguel_m2": float(row.aluguel_m2),
            "variacao_mensal": float(row.variacao_mensal) if row.variacao_mensal is not None else None,
            "variacao_12m": float(row.variacao_12m) if row.variacao_12m is not None else None,
            "fonte_id": row.fonte_id,
        }
        for row in session.execute(stmt).scalars()
    ]
    return ultimo, itens
