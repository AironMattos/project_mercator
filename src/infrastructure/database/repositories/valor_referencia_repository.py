from __future__ import annotations

from geoalchemy2.shape import from_shape
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.valuation import ValorMonetario, ValorReferenciaTerritorial, mediana_valor_m2
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


def consultar_valor_venal_mediano_por_bairro(session: Session) -> list[dict]:
    """Valor venal mediano de terreno (R$/m²) por bairro, a partir da PGV
    (checkpoint 11c/11e) - reaproveita domain.valuation.mediana_valor_m2,
    a mesma regra pura que recusa misturar tipo_valor/componente
    diferentes na mesma mediana (trava metodológica: fórmula pública e
    reproduzível, "mediana simples de valor_m2", nunca um score
    ponderado). PGV não é série temporal (checkpoint 11a) - a saída é um
    nível único com vigência explícita, nunca uma variação percentual.
    """
    tabela = ValorReferenciaTerritorialOrm
    stmt = select(
        tabela.territorio_id,
        tabela.valor_m2,
        tabela.tipo_valor,
        tabela.componente,
        tabela.fonte_id,
        tabela.metodologia,
        tabela.vigencia_inicio,
    ).where(
        tabela.tipo_valor == "venal",
        tabela.componente == "terreno",
        tabela.territorio_id.isnot(None),
    )

    valores_por_bairro: dict[str, list[ValorMonetario]] = {}
    metodologia_por_bairro: dict[str, str | None] = {}
    vigencia_por_bairro: dict[str, object] = {}
    fonte_por_bairro: dict[str, str] = {}
    for row in session.execute(stmt):
        valores_por_bairro.setdefault(row.territorio_id, []).append(
            ValorMonetario(
                valor_m2=float(row.valor_m2),
                tipo_valor=row.tipo_valor,
                componente=row.componente,
                fonte_id=row.fonte_id,
            )
        )
        metodologia_por_bairro[row.territorio_id] = row.metodologia
        vigencia_por_bairro[row.territorio_id] = row.vigencia_inicio
        fonte_por_bairro[row.territorio_id] = row.fonte_id

    resultado = []
    for territorio_id, valores in valores_por_bairro.items():
        resultado.append(
            {
                "territorio_id": territorio_id,
                "valor_m2_mediano": mediana_valor_m2(valores),
                "tipo_valor": "venal",
                "componente": "terreno",
                "quantidade_registros": len(valores),
                "fonte_id": fonte_por_bairro[territorio_id],
                "metodologia": metodologia_por_bairro[territorio_id],
                "vigencia_inicio": vigencia_por_bairro[territorio_id],
            }
        )
    return resultado
