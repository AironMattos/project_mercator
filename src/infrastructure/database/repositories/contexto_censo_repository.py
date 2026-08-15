from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
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


def consultar_agregado_por_bairro(session: Session) -> list[dict]:
    """Domicílios/população somados por bairro (soma dos setores que
    resolveram território) e densidade domiciliar (domicílios/km²).

    Rotulado deliberadamente como "densidade domiciliar", não "densidade
    construtiva/footprint" - o prompt de referência original (seção 5,
    métrica 6) pedia densidade cruzando footprint construído com
    domicílios do Censo, mas o checkpoint 11a já havia confirmado que não
    existe nenhuma camada de footprint/estoque construído publicada pelo
    GeoCuritiba. Usar só o que o Censo de fato tem (domicílios por área)
    é a métrica real disponível, não um substituto inventado - a mesma
    disciplina de "não invente proxy" já aplicada a TRANSACAO/LANCAMENTO.
    """
    tabela = ContextoCensoSetor
    stmt = (
        select(
            tabela.territorio_id,
            func.sum(tabela.populacao_total).label("populacao_total"),
            func.sum(tabela.domicilios_total).label("domicilios_total"),
            func.sum(tabela.domicilios_particulares_ocupados).label(
                "domicilios_particulares_ocupados"
            ),
            func.sum(tabela.area_km2).label("area_km2"),
            func.count().label("setores_agregados"),
        )
        .where(tabela.territorio_id.isnot(None))
        .group_by(tabela.territorio_id)
    )

    resultado = []
    for row in session.execute(stmt):
        area_km2 = float(row.area_km2) if row.area_km2 is not None else None
        domicilios_total = int(row.domicilios_total or 0)
        densidade = (domicilios_total / area_km2) if area_km2 else None
        resultado.append(
            {
                "territorio_id": row.territorio_id,
                "populacao_total": int(row.populacao_total or 0),
                "domicilios_total": domicilios_total,
                "domicilios_particulares_ocupados": int(
                    row.domicilios_particulares_ocupados or 0
                ),
                "area_km2": area_km2,
                "densidade_domicilios_km2": densidade,
                "setores_agregados": int(row.setores_agregados),
            }
        )
    return resultado
