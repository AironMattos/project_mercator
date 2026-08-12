from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from analytics.features.servico_indicadores import (
    indicadores_aberturas_por_mes_bairro,
    motivo_indisponivel_combinado,
)
from infrastructure.database.repositories.feature_repository import (
    consultar_cobertura_temporal,
    consultar_metricas_comercio,
)

from dependencies import get_db
from schemas import CoberturaTemporalOut, MetricaComercioOut

MOTIVO_NAO_APLICAVEL_SEM_TERRITORIO = "nao_aplicavel_sem_territorio_id"

router = APIRouter()


@router.get("/metricas/cobertura", response_model=CoberturaTemporalOut)
def metricas_cobertura(session: Session = Depends(get_db)) -> CoberturaTemporalOut:
    """Primeiro/último mês com evento real processado - a cobertura de
    dado de fato, para o cliente não confundir com o range do preset de
    período selecionado no filtro (ver achado da auditoria de 2026-08-12:
    "últimos 12 meses" no filtro parecia sugerir 12 meses de atividade
    real, mas só havia 1 mês de comparação processado).
    """
    mes_inicio, mes_fim = consultar_cobertura_temporal(session)
    return CoberturaTemporalOut(mes_inicio=mes_inicio, mes_fim=mes_fim)


def montar_serie_metricas(
    session: Session,
    *,
    territorio_id: str | None,
    categoria_id: str | None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> list[MetricaComercioOut]:
    """Monta a lista de MetricaComercioOut (com baseline/variacao_pct/
    tendencia de aberturas quando aplicável) - função compartilhada entre
    GET /metricas/comercio e GET /bairros/{id}/resumo, que reaproveita a
    série temporal em vez de duplicar a lógica de agregação (o pedido
    explícito do checkpoint 8b).
    """
    linhas = consultar_metricas_comercio(
        session,
        territorio_id=territorio_id,
        categoria_id=categoria_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )

    # baseline/variacao_pct/tendencia só fazem sentido por mês - no modo
    # agregado por bairro (sem territorio_id, usado pra colorir o mapa),
    # cada linha já soma o período inteiro, não um mês específico.
    indicadores_por_mes: dict = {}
    if territorio_id is not None:
        meses = [linha["mes"] for linha in linhas if linha["mes"] is not None]
        indicadores_por_mes = indicadores_aberturas_por_mes_bairro(
            session, territorio_id=territorio_id, categoria_id=categoria_id, meses=meses
        )

    resultado = []
    for linha in linhas:
        baseline = variacao_pct = tendencia = None
        motivo_indisponivel = MOTIVO_NAO_APLICAVEL_SEM_TERRITORIO
        if linha["mes"] is not None and linha["mes"] in indicadores_por_mes:
            b, t = indicadores_por_mes[linha["mes"]]
            baseline, variacao_pct, tendencia = b.baseline, b.variacao_pct, t.classificacao
            motivo_indisponivel = motivo_indisponivel_combinado(b, t)

        resultado.append(
            MetricaComercioOut(
                territorio_id=linha["territorio_id"],
                categoria_id=linha["categoria_id"],
                mes=linha["mes"],
                aberturas=linha["aberturas"],
                desaparecimentos=linha["desaparecimentos"],
                saldo=linha["aberturas"] - linha["desaparecimentos"],
                baseline=baseline,
                variacao_pct=variacao_pct,
                tendencia=tendencia,
                motivo_indisponivel=motivo_indisponivel,
            )
        )
    return resultado


@router.get("/metricas/comercio", response_model=list[MetricaComercioOut])
def metricas_comercio(
    territorio_id: str | None = None,
    categoria_id: str | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    session: Session = Depends(get_db),
) -> list[MetricaComercioOut]:
    """Sem territorio_id: agregado por bairro, para o mapa. Com
    territorio_id: série temporal completa daquele bairro, para o painel
    de detalhe.
    """
    return montar_serie_metricas(
        session,
        territorio_id=territorio_id,
        categoria_id=categoria_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
