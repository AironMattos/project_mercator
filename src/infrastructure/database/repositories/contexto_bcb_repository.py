from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.valuation import IndicadorMercadoImobiliarioUf
from infrastructure.database.orm.contexto_bcb_imobiliario import ContextoBcbImobiliario


def inserir_indicadores_bcb(
    session: Session, indicadores: list[IndicadorMercadoImobiliarioUf]
) -> int:
    """Grava leituras mensais do BCB de forma idempotente por
    (uf, periodo_referencia, indicador) - reprocessar o mesmo mês não
    duplica a leitura (ON CONFLICT DO NOTHING, mesma disciplina de
    imutabilidade de observacao_entidade)."""
    if not indicadores:
        return 0

    rows = [
        {
            "uf": i.uf,
            "periodo_referencia": i.periodo_referencia,
            "indicador": i.indicador,
            "categoria": i.categoria,
            "tipo_valor": i.tipo_valor,
            "unidade": i.unidade,
            "leitura": i.leitura,
            "fonte_id": i.fonte_id,
            "snapshot_ref": i.snapshot_ref,
        }
        for i in indicadores
    ]

    stmt = insert(ContextoBcbImobiliario).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["uf", "periodo_referencia", "indicador"]
    )
    result = session.execute(stmt)
    return result.rowcount or 0


def consultar_ultimo_periodo(
    session: Session, uf: str = "PR"
) -> tuple[date | None, list[dict]]:
    """As 14 séries do BCB no mês mais recente disponível para `uf` -
    granularidade UF explícita no retorno (checkpoint 11d/11e: nunca
    implicar Curitiba num dado que é do Paraná inteiro)."""
    tabela = ContextoBcbImobiliario
    ultimo = session.execute(
        select(func.max(tabela.periodo_referencia)).where(tabela.uf == uf)
    ).scalar()
    if ultimo is None:
        return None, []

    stmt = select(tabela).where(tabela.uf == uf, tabela.periodo_referencia == ultimo)
    itens = [
        {
            "indicador": row.indicador,
            "categoria": row.categoria,
            "tipo_valor": row.tipo_valor,
            "unidade": row.unidade,
            "leitura": float(row.leitura),
            "fonte_id": row.fonte_id,
        }
        for row in session.execute(stmt).scalars()
    ]
    return ultimo, itens
