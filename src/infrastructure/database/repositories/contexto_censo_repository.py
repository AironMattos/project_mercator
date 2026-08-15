from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.contexto import IndicadorCensitarioSetor
from infrastructure.database.orm.contexto_censo_setor import ContextoCensoSetor

TAMANHO_LOTE_INSERT = 5000


def upsert_setores_censitarios(
    session: Session, setores: Iterable[IndicadorCensitarioSetor]
) -> int:
    """Grava setores censitários em lotes de TAMANHO_LOTE_INSERT (upsert
    por setor_censitario, mesmo padrão de lote_cadastral_repository) - o
    Censo é uma fonte estática (só se repete a cada ~10 anos), então
    reprocessar o mesmo arquivo apenas atualiza os mesmos setores, nunca
    duplica."""
    total = 0
    buffer: list[dict] = []

    for s in setores:
        buffer.append(
            {
                "setor_censitario": s.setor_censitario,
                "territorio_id": s.territorio_id,
                "municipio_codigo": s.municipio_codigo,
                "area_km2": s.area_km2,
                "populacao_total": s.populacao_total,
                "domicilios_total": s.domicilios_total,
                "domicilios_particulares_ocupados": s.domicilios_particulares_ocupados,
                "domicilios_particulares_vagos": s.domicilios_particulares_vagos,
                "ano_referencia": s.ano_referencia,
                "fonte_id": s.fonte_id,
                "snapshot_ref": s.snapshot_ref,
            }
        )
        if len(buffer) >= TAMANHO_LOTE_INSERT:
            total += _gravar_lote(session, buffer)
            buffer = []

    if buffer:
        total += _gravar_lote(session, buffer)

    return total


def _gravar_lote(session: Session, rows: list[dict]) -> int:
    stmt = insert(ContextoCensoSetor).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ContextoCensoSetor.setor_censitario],
        set_={
            "territorio_id": stmt.excluded.territorio_id,
            "municipio_codigo": stmt.excluded.municipio_codigo,
            "area_km2": stmt.excluded.area_km2,
            "populacao_total": stmt.excluded.populacao_total,
            "domicilios_total": stmt.excluded.domicilios_total,
            "domicilios_particulares_ocupados": stmt.excluded.domicilios_particulares_ocupados,
            "domicilios_particulares_vagos": stmt.excluded.domicilios_particulares_vagos,
            "ano_referencia": stmt.excluded.ano_referencia,
            "fonte_id": stmt.excluded.fonte_id,
            "snapshot_ref": stmt.excluded.snapshot_ref,
        },
    )
    session.execute(stmt)
    session.commit()
    return len(rows)
