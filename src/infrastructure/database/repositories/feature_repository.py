from __future__ import annotations

from datetime import date

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from analytics.features import ContagemEventos as ContagemEventosDominio
from analytics.features import PontoMensal
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
    # "aberturas" soma PRIMEIRA_OBSERVACAO (confiança baixa) e
    # ABERTURA_CONFIRMADA (confiança alta) - antes da correção de
    # 2026-08-12, ABERTURA_CONFIRMADA ficava de fora (nunca chegava a
    # analytics.contagem_eventos, ver TIPOS_CONSIDERADOS em
    # analytics/features/contagem_eventos.py), então "aberturas" media só
    # entidades sem prova de quando abriram.
    aberturas = func.sum(
        case(
            (
                tabela.event_type.in_(("PRIMEIRA_OBSERVACAO", "ABERTURA_CONFIRMADA")),
                tabela.contagem,
            ),
            else_=0,
        )
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
        tabela.event_type.in_(
            ("PRIMEIRA_OBSERVACAO", "ABERTURA_CONFIRMADA", "DESAPARECIMENTO")
        )
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


def consultar_saldo_mensal_todos_bairros(session: Session) -> dict[str, list[PontoMensal]]:
    """Saldo (aberturas - desaparecimentos) por bairro e mês, direto de
    analytics.contagem_eventos - mesma fonte/mesmo cálculo de
    indicador_saldo_bairro (servico_indicadores.py), mas para todos os
    bairros de uma vez numa única query (checkpoint 11b: sinais de saldo
    negativo consecutivo precisam varrer todo mundo, não um bairro por
    vez). Não é zero-preenchida - ausência de mês aqui significa "não
    processamos essa comparação de snapshot", nunca "saldo zero" (mesma
    convenção de indicador_saldo_bairro).
    """
    tabela = ContagemEventosORM
    aberturas = func.sum(
        case(
            (tabela.event_type.in_(("PRIMEIRA_OBSERVACAO", "ABERTURA_CONFIRMADA")), tabela.contagem),
            else_=0,
        )
    )
    desaparecimentos = func.sum(
        case((tabela.event_type == "DESAPARECIMENTO", tabela.contagem), else_=0)
    )
    stmt = (
        select(tabela.territorio_id, tabela.mes, aberturas, desaparecimentos)
        .where(tabela.territorio_id.isnot(None))
        .group_by(tabela.territorio_id, tabela.mes)
    )

    resultado: dict[str, list[PontoMensal]] = {}
    for territorio_id, mes, ab, des in session.execute(stmt):
        resultado.setdefault(territorio_id, []).append(
            PontoMensal(mes=mes, valor=float((ab or 0) - (des or 0)))
        )
    return resultado


def consultar_cobertura_temporal(session: Session) -> tuple[date | None, date | None]:
    """Primeiro e último mês com evento em analytics.contagem_eventos -
    a cobertura real do dado, independente do preset de período escolhido
    no filtro (ex.: "últimos 12 meses" no filtro não significa que existam
    12 meses de dado real; essa função é o que informa isso ao cliente).
    """
    tabela = ContagemEventosORM
    linha = session.execute(
        select(func.min(tabela.mes), func.max(tabela.mes))
    ).one()
    return linha[0], linha[1]
