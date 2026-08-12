from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from infrastructure.database.repositories.feature_repository import (
    consultar_metricas_comercio,
)

from dependencies import get_db
from schemas import MetricaComercioOut

router = APIRouter()


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
