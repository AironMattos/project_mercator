from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.event import Evento
from infrastructure.database.orm.fato_evento_territorial import (
    FatoEventoTerritorial as FatoEventoTerritorialORM,
)


def insert_eventos(session: Session, eventos: list[Evento]) -> int:
    """Grava eventos. Reprocessar o mesmo par de snapshots não deve
    duplicar o mesmo evento (entidade + tipo + data) - o evento em si,
    uma vez gravado, nunca é atualizado.
    """
    if not eventos:
        return 0

    rows = [
        {
            "evento_id": e.evento_id,
            "entity_type": e.entity_type,
            "event_type": e.event_type,
            "entidade_id": e.entidade_id,
            "territorio_id": e.territorio_id,
            "data_evento": e.data_evento,
            "confianca": e.confianca,
            "origem_observacoes": list(e.origem_observacoes),
            "payload": e.payload,
        }
        for e in eventos
    ]

    stmt = insert(FatoEventoTerritorialORM).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["entidade_id", "event_type", "data_evento"]
    )
    resultado = session.execute(stmt)
    return resultado.rowcount or 0


def iter_eventos(session: Session) -> Iterator[Evento]:
    """Lê todos os eventos gravados. A tabela é pequena (milhares de
    linhas, não milhões como observação) - não precisa de streaming, mas
    usamos yield_per para não instanciar tudo de uma vez ainda assim.
    """
    tabela = FatoEventoTerritorialORM
    stmt = select(tabela).execution_options(yield_per=2000)
    for row in session.execute(stmt).scalars():
        yield Evento(
            entity_type=row.entity_type,
            event_type=row.event_type,
            entidade_id=row.entidade_id,
            territorio_id=row.territorio_id,
            data_evento=row.data_evento,
            confianca=row.confianca,
            origem_observacoes=tuple(row.origem_observacoes),
            payload=row.payload,
            evento_id=row.evento_id,
        )
