from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from analytics.features.servico_indicadores import (
    indicador_aberturas_bairro,
    indicador_saldo_bairro,
    montar_ranking_aberturas,
    motivo_indisponivel_combinado,
    periodo_padrao_aberturas,
    quebra_categoria_bairro,
)
from infrastructure.database.repositories.categoria_repository import listar_categorias
from infrastructure.database.repositories.territorio_repository import (
    nomes_por_territorio_id,
)

from dependencies import get_db
from routers.metricas import montar_serie_metricas
from schemas import BairroResumoOut, ComparacaoOut, IndicadorOut, QuebraCategoriaOut

router = APIRouter()

MIN_BAIRROS_COMPARACAO = 2
MAX_BAIRROS_COMPARACAO = 4


def _montar_resumo_bairro(
    session: Session,
    territorio_id: str,
    *,
    categoria_id: str | None,
    periodo: date | None,
    data_inicio: date | None,
    data_fim: date | None,
    nomes: dict[str, str],
) -> BairroResumoOut | None:
    """Perfil completo de um bairro: os indicadores de aberturas/saldo (com
    baseline e tendência quando confiáveis), a posição no ranking de
    crescimento, a quebra por categoria do período, e a série temporal já
    exposta por /metricas/comercio (reaproveitada, não recalculada aqui).

    Fatorada de `bairro_resumo` (checkpoint 11c) para ser reaproveitada por
    GET /bairros/comparar sem duplicar a lógica - `nomes` é passado de fora
    porque quem compara vários bairros já carregou o mapa completo uma
    única vez, evitar recarregar por bairro.
    """
    nome = nomes.get(territorio_id)
    if nome is None:
        return None

    mes_referencia = periodo or periodo_padrao_aberturas(session)

    baseline_aberturas, tendencia_aberturas = indicador_aberturas_bairro(
        session, territorio_id=territorio_id, categoria_id=categoria_id, mes_referencia=mes_referencia
    )
    baseline_saldo, tendencia_saldo, _mes_saldo = indicador_saldo_bairro(
        session, territorio_id=territorio_id, categoria_id=categoria_id
    )

    # Posição no ranking - mesmo filtro de categoria, sem limite (precisa
    # da lista inteira pra achar a posição deste bairro específico nela).
    ranking_completo, _sparklines, _abaixo_do_piso = montar_ranking_aberturas(
        session, categoria_id=categoria_id, mes_referencia=mes_referencia
    )
    item_ranking = next((r for r in ranking_completo if r.territorio_id == territorio_id), None)
    posicao_ranking = item_ranking.posicao if item_ranking else None
    total_ranking = item_ranking.total if item_ranking else (len(ranking_completo) or None)

    categorias_por_id = {c.categoria_id: c.nome for c in listar_categorias(session)}
    quebra = quebra_categoria_bairro(session, territorio_id=territorio_id, mes_referencia=mes_referencia)

    # data_inicio/data_fim opcionais - o filtro de período do mapa (um
    # range) continua controlando a série temporal quando o painel é
    # aberto a partir dele; sem eles, mostra o histórico inteiro
    # disponível (o caso de abrir a partir do ranking, que não tem esse
    # conceito de range).
    serie_temporal = montar_serie_metricas(
        session,
        territorio_id=territorio_id,
        categoria_id=categoria_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )

    return BairroResumoOut(
        territorio_id=territorio_id,
        nome=nome,
        periodo=mes_referencia,
        aberturas=IndicadorOut(
            valor_atual=baseline_aberturas.valor_atual,
            baseline=baseline_aberturas.baseline,
            variacao_pct=baseline_aberturas.variacao_pct,
            tendencia=tendencia_aberturas.classificacao,
            motivo_indisponivel=motivo_indisponivel_combinado(baseline_aberturas, tendencia_aberturas),
        ),
        saldo=IndicadorOut(
            valor_atual=baseline_saldo.valor_atual,
            baseline=baseline_saldo.baseline,
            variacao_pct=baseline_saldo.variacao_pct,
            tendencia=tendencia_saldo.classificacao,
            motivo_indisponivel=motivo_indisponivel_combinado(baseline_saldo, tendencia_saldo),
        ),
        posicao_ranking=posicao_ranking,
        total_ranking=total_ranking,
        quebra_categoria=[
            QuebraCategoriaOut(
                categoria_id=cat_id,
                nome=categorias_por_id.get(cat_id, "(sem categoria)") if cat_id else "(sem categoria)",
                contagem=contagem,
            )
            for cat_id, contagem in quebra
        ],
        serie_temporal=serie_temporal,
    )


@router.get("/bairros/{territorio_id}/resumo", response_model=BairroResumoOut)
def bairro_resumo(
    territorio_id: str,
    categoria_id: str | None = None,
    periodo: date | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    session: Session = Depends(get_db),
) -> BairroResumoOut:
    nomes = nomes_por_territorio_id(session)
    resumo = _montar_resumo_bairro(
        session,
        territorio_id,
        categoria_id=categoria_id,
        periodo=periodo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        nomes=nomes,
    )
    if resumo is None:
        raise HTTPException(status_code=404, detail="território não encontrado")
    return resumo


@router.get("/bairros/comparar", response_model=ComparacaoOut)
def bairros_comparar(
    ids: str = Query(..., description="territorio_id separados por vírgula, 2 a 4 bairros"),
    categoria_id: str | None = None,
    periodo: date | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    session: Session = Depends(get_db),
) -> ComparacaoOut:
    """Perfil completo (mesmo formato de /bairros/{id}/resumo) de 2 a 4
    bairros de uma vez - checkpoint 11c, "COMPARAÇÃO" no prompt de
    referência. Um único endpoint em vez de N chamadas sequenciais do
    frontend (evita N waterfalls); nenhuma lógica de comparação nova aqui -
    cada item é exatamente o que /bairros/{id}/resumo já calcula, lado a
    lado, sem nota nem ranking agregado entre eles (o prompt é explícito:
    "não criar uma nota geral para determinar qual bairro é melhor").
    """
    territorio_ids = [t.strip() for t in ids.split(",") if t.strip()]
    if not (MIN_BAIRROS_COMPARACAO <= len(territorio_ids) <= MAX_BAIRROS_COMPARACAO):
        raise HTTPException(
            status_code=422,
            detail=f"informe entre {MIN_BAIRROS_COMPARACAO} e {MAX_BAIRROS_COMPARACAO} bairros",
        )

    nomes = nomes_por_territorio_id(session)
    invalidos = [t for t in territorio_ids if t not in nomes]
    if invalidos:
        raise HTTPException(status_code=404, detail=f"território(s) não encontrado(s): {', '.join(invalidos)}")

    itens = [
        _montar_resumo_bairro(
            session,
            territorio_id,
            categoria_id=categoria_id,
            periodo=periodo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            nomes=nomes,
        )
        for territorio_id in territorio_ids
    ]
    return ComparacaoOut(itens=[i for i in itens if i is not None])
