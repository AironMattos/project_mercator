from __future__ import annotations

from geoalchemy2.shape import from_shape, to_shape
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.territory import Territorio
from infrastructure.database.orm.territorio import DimTerritorio


def upsert_territorios(session: Session, territorios: list[Territorio]) -> int:
    """Grava territórios de forma idempotente (upsert por territorio_id).

    Território é uma dimensão relativamente estável; reprocessar a mesma
    fonte não deve criar duplicatas nem falhar.
    """
    if not territorios:
        return 0

    rows = [
        {
            "territorio_id": t.territorio_id,
            "nivel": t.nivel,
            "nome": t.nome,
            "nome_alternativo": list(t.nome_alternativo),
            "geometria": from_shape(t.geometria, srid=4326) if t.geometria else None,
            "territorio_pai_id": t.territorio_pai_id,
            "cidade_id": t.cidade_id,
        }
        for t in territorios
    ]

    stmt = insert(DimTerritorio).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[DimTerritorio.territorio_id],
        set_={
            "nivel": stmt.excluded.nivel,
            "nome": stmt.excluded.nome,
            "nome_alternativo": stmt.excluded.nome_alternativo,
            "geometria": stmt.excluded.geometria,
            "territorio_pai_id": stmt.excluded.territorio_pai_id,
            "cidade_id": stmt.excluded.cidade_id,
        },
    )
    session.execute(stmt)
    return len(rows)


def list_territorios(session: Session, nivel: str | None = None) -> list[Territorio]:
    query = session.query(DimTerritorio)
    if nivel is not None:
        query = query.filter(DimTerritorio.nivel == nivel)

    result = []
    for row in query.all():
        geometria = to_shape(row.geometria) if row.geometria is not None else None
        result.append(
            Territorio(
                territorio_id=row.territorio_id,
                nivel=row.nivel,
                nome=row.nome,
                geometria=geometria,
                nome_alternativo=tuple(row.nome_alternativo or ()),
                territorio_pai_id=row.territorio_pai_id,
                cidade_id=row.cidade_id,
            )
        )
    return result
