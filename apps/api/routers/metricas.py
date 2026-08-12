from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from infrastructure.database.repositories.feature_repository import (
    consultar_cobertura_temporal,
    consultar_metricas_comercio,
)

from dependencies import get_db
from schemas import CoberturaTemporalOut, MetricaComercioOut

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
    linhas = consultar_metricas_comercio(
        session,
        territorio_id=territorio_id,
        categoria_id=categoria_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
    return [
        MetricaComercioOut(
            territorio_id=linha["territorio_id"],
            categoria_id=linha["categoria_id"],
            mes=linha["mes"],
            aberturas=linha["aberturas"],
            desaparecimentos=linha["desaparecimentos"],
            saldo=linha["aberturas"] - linha["desaparecimentos"],
        )
        for linha in linhas
    ]
