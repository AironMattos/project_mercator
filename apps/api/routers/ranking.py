from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from analytics.features.servico_indicadores import (
    montar_ranking_aberturas,
    montar_ranking_categorias,
    periodo_padrao_aberturas,
)
from infrastructure.database.repositories.categoria_repository import listar_categorias
from infrastructure.database.repositories.territorio_repository import (
    nomes_por_territorio_id,
)

from dependencies import get_db
from schemas import (
    PontoSerieOut,
    RankingCategoriaItemOut,
    RankingCategoriasOut,
    RankingItemOut,
    RankingOut,
)

router = APIRouter()


@router.get("/ranking/comercio", response_model=RankingOut)
def ranking_comercio(
    categoria_id: str | None = None,
    periodo: date | None = None,
    limite: int = 10,
    ordem: Literal["desc", "asc"] = "desc",
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
    `ordem="desc"` (padrão): maiores crescimentos primeiro. `ordem="asc"`:
    maiores retrações primeiro (checkpoint 11b) - lista distinta, nunca
    misturada com a de crescimento.
    """
    mes_referencia = periodo or periodo_padrao_aberturas(session)
    itens, sparklines, abaixo_do_piso = montar_ranking_aberturas(
        session, categoria_id=categoria_id, mes_referencia=mes_referencia, limite=limite, ordem=ordem
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


@router.get("/ranking/categorias", response_model=RankingCategoriasOut)
def ranking_categorias(
    territorio_id: str | None = None,
    periodo: date | None = None,
    limite: int = 10,
    ordem: Literal["desc", "asc"] = "desc",
    session: Session = Depends(get_db),
) -> RankingCategoriasOut:
    """Categorias ordenadas por crescimento relativo de aberturas - cidade
    inteira por padrão, ou um bairro específico via `territorio_id`
    (checkpoint 11b: "categorias em alta/em queda" no Radar). Mesma
    mecânica de /ranking/comercio (baseline de 24 meses, piso mínimo de
    volume, `ordem` para crescimento vs. retração), só agrupado por
    categoria em vez de território.
    """
    mes_referencia = periodo or periodo_padrao_aberturas(session)
    itens, abaixo_do_piso = montar_ranking_categorias(
        session, territorio_id=territorio_id, mes_referencia=mes_referencia, limite=limite, ordem=ordem
    )
    nomes = {c.categoria_id: c.nome for c in listar_categorias(session)}

    return RankingCategoriasOut(
        itens=[
            RankingCategoriaItemOut(
                categoria_id=item.territorio_id or "?",
                nome=nomes.get(item.territorio_id or "", item.territorio_id or "?"),
                valor_atual=item.valor_atual,
                baseline=item.baseline,
                variacao_pct=item.variacao_pct,
                tendencia=item.tendencia,
                posicao=item.posicao,
                total=item.total,
            )
            for item in itens
        ],
        abaixo_do_piso_volume=abaixo_do_piso,
    )
