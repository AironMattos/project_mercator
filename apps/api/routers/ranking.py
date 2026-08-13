from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from analytics.features.servico_indicadores import (
    montar_ranking_aberturas,
    periodo_padrao_aberturas,
)
from infrastructure.database.repositories.territorio_repository import (
    nomes_por_territorio_id,
)

from dependencies import get_db
from schemas import PontoSerieOut, RankingItemOut, RankingOut

router = APIRouter()


@router.get("/ranking/comercio", response_model=RankingOut)
def ranking_comercio(
    categoria_id: str | None = None,
    periodo: date | None = None,
    limite: int = 10,
    session: Session = Depends(get_db),
) -> RankingOut:
    """Bairros ordenados por crescimento relativo de aberturas
    (variacao_pct vs. baseline de 24 meses) - não por volume absoluto, de
    propósito: revela bairros pequenos em ascensão que a lista por volume
    nunca mostraria. Bairros com baseline abaixo do piso mínimo de volume
    (checkpoint 10d) não entram em `itens`, mas são contados em
    `abaixo_do_piso_volume` - visível, não escondido. `periodo`: mês de
    referência (default o último mês com cobertura real de
    INICIO_ATIVIDADE - ver servico_indicadores.periodo_padrao_aberturas).
    """
    mes_referencia = periodo or periodo_padrao_aberturas(session)
    itens, sparklines, abaixo_do_piso = montar_ranking_aberturas(
        session, categoria_id=categoria_id, mes_referencia=mes_referencia, limite=limite
    )
    nomes = nomes_por_territorio_id(session)

    return RankingOut(
        itens=[
            RankingItemOut(
                territorio_id=item.territorio_id,
                nome=nomes.get(item.territorio_id, item.territorio_id or "?"),
                valor_atual=item.valor_atual,
                baseline=item.baseline,
                variacao_pct=item.variacao_pct,
                tendencia=item.tendencia,
                posicao=item.posicao,
                total=item.total,
                serie=[
                    PontoSerieOut(mes=p.mes, valor=p.valor)
                    for p in sparklines.get(item.territorio_id, [])
                ],
            )
            for item in itens
        ],
        abaixo_do_piso_volume=abaixo_do_piso,
    )
