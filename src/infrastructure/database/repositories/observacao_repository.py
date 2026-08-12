from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.observation import ObservacaoEntidade
from infrastructure.database.orm.observacao_entidade import (
    ObservacaoEntidade as ObservacaoEntidadeORM,
)


def insert_observacoes(session: Session, observacoes: list[ObservacaoEntidade]) -> int:
    """Grava observações. Nunca atualiza uma observação existente - se o
    mesmo snapshot (entidade + fonte + observado_em) já foi gravado antes,
    o registro repetido é ignorado (idempotência de reprocessamento), não
    sobrescrito.
    """
    if not observacoes:
        return 0

    rows = [
        {
            "observacao_id": o.observacao_id,
            "entidade_id": o.entidade_id,
            "observado_em": o.observado_em,
            "atributos": o.atributos,
            "fonte_id": o.fonte_id,
            "snapshot_ref": o.snapshot_ref,
        }
        for o in observacoes
    ]

    stmt = insert(ObservacaoEntidadeORM).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["entidade_id", "fonte_id", "observado_em"]
    )
    resultado = session.execute(stmt)
    return resultado.rowcount or 0


def iter_grupos_por_entidade(
    session: Session,
    fonte_id: str,
    data_anterior: date,
    data_atual: date,
) -> Iterator[tuple[uuid.UUID, list[ObservacaoEntidade]]]:
    """Para cada entidade que tem observação em pelo menos uma das duas
    datas, gera (entidade_id, [observações ordenadas por observado_em]).

    Usa cursor server-side (yield_per) - nunca carrega as ~500 mil
    observações de cada snapshot inteiras em memória de uma vez.
    """
    tabela = ObservacaoEntidadeORM
    stmt = (
        select(
            tabela.entidade_id,
            tabela.observado_em,
            tabela.atributos,
            tabela.observacao_id,
            tabela.snapshot_ref,
        )
        .where(
            tabela.fonte_id == fonte_id,
            tabela.observado_em.in_([data_anterior, data_atual]),
        )
        .order_by(tabela.entidade_id, tabela.observado_em)
        .execution_options(yield_per=2000)
    )

    grupo_id = None
    grupo: list[ObservacaoEntidade] = []
    for row in session.execute(stmt):
        if grupo_id is not None and row.entidade_id != grupo_id:
            yield grupo_id, grupo
            grupo = []
        grupo_id = row.entidade_id
        grupo.append(
            ObservacaoEntidade(
                entidade_id=row.entidade_id,
                observado_em=row.observado_em,
                atributos=row.atributos,
                fonte_id=fonte_id,
                snapshot_ref=row.snapshot_ref,
                observacao_id=row.observacao_id,
            )
        )
    if grupo:
        yield grupo_id, grupo
