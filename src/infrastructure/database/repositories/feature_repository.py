from __future__ import annotations

from datetime import date

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from analytics.features import ContagemEventos as ContagemEventosDominio
from infrastructure.database.orm.contagem_eventos import (
    ContagemEventos as ContagemEventosORM,
)


def substituir_contagem_eventos(
    session: Session, contagens: list[ContagemEventosDominio]
) -> int:
    """Recalcula a feature do zero: apaga tudo e grava de novo. É seguro
    porque a tabela é 100% derivada de fato_evento_territorial - nada aqui
    é fonte de verdade.
    """
    session.execute(delete(ContagemEventosORM))
    if not contagens:
        return 0

    rows = [
        {
            "territorio_id": c.territorio_id,
            "categoria_id": c.categoria_id,
            "mes": c.mes,
            "event_type": c.event_type,
            "contagem": c.contagem,
        }
        for c in contagens
    ]
    session.execute(ContagemEventosORM.__table__.insert(), rows)
    return len(rows)


def consultar_metricas_comercio(
    session: Session,
    *,
    territorio_id: str | None = None,
    categoria_id: str | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> list[dict]:
    """Lê analytics.contagem_eventos já pivotado em aberturas/desaparecimentos,
    no formato que a API expõe.

    Sem territorio_id: agrega por bairro (soma o período inteiro) - para
    popular o mapa. Com territorio_id: agrupa por mês - a série temporal
    completa daquele bairro, para o painel de detalhe.
    """
    tabela = ContagemEventosORM
    aberturas = func.sum(
        case((tabela.event_type == "PRIMEIRA_OBSERVACAO", tabela.contagem), else_=0)
    ).label("aberturas")
    desaparecimentos = func.sum(
        case((tabela.event_type == "DESAPARECIMENTO", tabela.contagem), else_=0)
    ).label("desaparecimentos")

    if territorio_id is not None:
        colunas = (tabela.territorio_id, tabela.mes, aberturas, desaparecimentos)
        agrupar_por = (tabela.territorio_id, tabela.mes)
    else:
        colunas = (tabela.territorio_id, aberturas, desaparecimentos)
        agrupar_por = (tabela.territorio_id,)

    stmt = select(*colunas).where(
        tabela.event_type.in_(("PRIMEIRA_OBSERVACAO", "DESAPARECIMENTO"))
    )
    if territorio_id is not None:
        stmt = stmt.where(tabela.territorio_id == territorio_id)
    if categoria_id is not None:
        stmt = stmt.where(tabela.categoria_id == categoria_id)
    if data_inicio is not None:
        stmt = stmt.where(tabela.mes >= data_inicio)
    if data_fim is not None:
        stmt = stmt.where(tabela.mes <= data_fim)

    stmt = stmt.group_by(*agrupar_por).order_by(*agrupar_por)

    resultado = []
    for row in session.execute(stmt):
        resultado.append(
            {
                "territorio_id": row.territorio_id,
                "categoria_id": categoria_id,
                "mes": row.mes if territorio_id is not None else None,
                "aberturas": int(row.aberturas or 0),
                "desaparecimentos": int(row.desaparecimentos or 0),
            }
        )
    return resultado
