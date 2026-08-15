from __future__ import annotations

from geoalchemy2.shape import from_shape
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.valuation import ValorReferenciaTerritorial
from infrastructure.database.orm.valor_referencia_territorial import (
    ValorReferenciaTerritorial as ValorReferenciaTerritorialOrm,
)


def inserir_valores_referencia(
    session: Session, valores: list[ValorReferenciaTerritorial]
) -> int:
    """Grava valores de referência de forma idempotente por
    (objectid_fonte, fonte_id, vigencia_inicio) - a identidade do
    registro na fonte, não território (um bairro comum tem várias
    geometrias/valores da mesma fonte). Reprocessar o mesmo snapshot não
    duplica a linha, mas uma linha já gravada nunca é atualizada (ON
    CONFLICT DO NOTHING, não DO UPDATE) - mesma disciplina de
    imutabilidade de observacao_entidade. Uma revisão de valor é uma
    linha nova, com vigencia_inicio diferente, não uma sobrescrita."""
    if not valores:
        return 0

    rows = [
        {
            "geometria": from_shape(v.geometria, srid=4326),
            "objectid_fonte": v.objectid_fonte,
            "territorio_id": v.territorio_id,
            "tipo_valor": v.tipo_valor,
            "componente": v.componente,
            "valor_m2": v.valor_m2,
            "moeda_data": v.moeda_data,
            "fonte_id": v.fonte_id,
            "metodologia": v.metodologia,
            "vigencia_inicio": v.vigencia_inicio,
            "vigencia_fim": v.vigencia_fim,
            "snapshot_ref": v.snapshot_ref,
        }
        for v in valores
    ]

    stmt = insert(ValorReferenciaTerritorialOrm).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["objectid_fonte", "fonte_id", "vigencia_inicio"]
    )
    result = session.execute(stmt)
    return result.rowcount or 0
