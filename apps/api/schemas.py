from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel


class CategoriaOut(BaseModel):
    categoria_id: str
    nome: str


class MetricaComercioOut(BaseModel):
    territorio_id: str | None
    categoria_id: str | None
    mes: date | None
    aberturas: int
    desaparecimentos: int
    saldo: int


class CoberturaTemporalOut(BaseModel):
    mes_inicio: date | None
    mes_fim: date | None


class GeoJsonFeature(BaseModel):
    type: str = "Feature"
    geometry: dict[str, Any] | None
    properties: dict[str, Any]


class GeoJsonFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[GeoJsonFeature]
