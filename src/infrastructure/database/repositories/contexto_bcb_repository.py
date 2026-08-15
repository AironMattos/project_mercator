from __future__ import annotations

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
