from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.contexto import IndicadorFipezapBairro, IndicadorFipezapCidade
from infrastructure.database.orm.contexto_fipezap import (
    ContextoFipezapBairro,
    ContextoFipezapCidade,
)


def inserir_indicadores_cidade(session: Session, indicadores: list[IndicadorFipezapCidade]) -> int:
    """Idempotente por (cidade, operacao, periodo_referencia) - mesma
    disciplina de contexto_quintoandar_repository."""
    if not indicadores:
        return 0

    rows = [
        {
            "cidade": i.cidade,
            "operacao": i.operacao,
            "periodo_referencia": i.periodo_referencia,
            "preco_medio_m2": i.preco_medio_m2,
            "variacao_mensal": i.variacao_mensal,
            "variacao_acumulada_ano": i.variacao_acumulada_ano,
            "variacao_12m": i.variacao_12m,
            "fonte_id": i.fonte_id,
            "snapshot_ref": i.snapshot_ref,
        }
        for i in indicadores
    ]
    stmt = insert(ContextoFipezapCidade).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["cidade", "operacao", "periodo_referencia"]
    )
    result = session.execute(stmt)
    return result.rowcount or 0


def inserir_indicadores_bairro(session: Session, indicadores: list[IndicadorFipezapBairro]) -> int:
    """Idempotente por (cidade, operacao, periodo_referencia,
    bairro_nome)."""
    if not indicadores:
        return 0

    rows = [
        {
            "cidade": i.cidade,
            "operacao": i.operacao,
            "periodo_referencia": i.periodo_referencia,
            "bairro_nome": i.bairro_nome,
            "preco_medio_m2": i.preco_medio_m2,
            "variacao_12m": i.variacao_12m,
            "territorio_id": i.territorio_id,
            "fonte_id": i.fonte_id,
            "snapshot_ref": i.snapshot_ref,
        }
        for i in indicadores
    ]
    stmt = insert(ContextoFipezapBairro).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["cidade", "operacao", "periodo_referencia", "bairro_nome"]
    )
    result = session.execute(stmt)
    return result.rowcount or 0
