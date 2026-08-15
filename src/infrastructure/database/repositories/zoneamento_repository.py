from __future__ import annotations

from geoalchemy2.shape import from_shape
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from infrastructure.database.orm.zoneamento_territorial import ZoneamentoTerritorial


def inserir_zoneamentos(session: Session, registros: list[dict]) -> int:
    """Grava zoneamento de forma idempotente por
    (objectid_fonte, fonte_id, data_versao) - reprocessar a mesma versão
    não duplica, mas uma nova data_versao para o mesmo objectid_fonte
    sempre vira uma linha nova (histórico preservado - é o que permite
    detectar ZONEAMENTO_ALTERADO comparando duas linhas)."""
    if not registros:
        return 0

    rows = [
        {
            "geometria": from_shape(r["geometria"], srid=4326),
            "objectid_fonte": r["objectid_fonte"],
            "cd_zona": r["cd_zona"],
            "sg_zona": r["sg_zona"],
            "nm_zona": r["nm_zona"],
            "nm_grupo": r["nm_grupo"],
            "legislacao": r["legislacao"],
            "data_versao": r["data_versao"],
            "data_atualizacao": r["data_atualizacao"],
            "territorio_id": r["territorio_id"],
            "fonte_id": r["fonte_id"],
            "snapshot_ref": r["snapshot_ref"],
        }
        for r in registros
    ]

    stmt = insert(ZoneamentoTerritorial).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["objectid_fonte", "fonte_id", "data_versao"]
    )
    result = session.execute(stmt)
    return result.rowcount or 0


def listar_zoneamento(
    session: Session, territorio_id: str | None = None
) -> list[ZoneamentoTerritorial]:
    """Zoneamento vigente por polígono, com data_versao/data_atualizacao
    (checkpoint 11e) - sem filtro de vigência por enquanto: a fonte
    (checkpoint 11c) ainda não passou por nenhuma revisão observada;
    quando isso acontecer, filtrar pela data_versao mais recente por
    objectid_fonte é trabalho de quem detectar ZONEAMENTO_ALTERADO
    (reservado, ainda não implementado), não deste endpoint de leitura.
    """
    stmt = select(ZoneamentoTerritorial)
    if territorio_id is not None:
        stmt = stmt.where(ZoneamentoTerritorial.territorio_id == territorio_id)
    return list(session.execute(stmt).scalars())
