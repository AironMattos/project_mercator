from __future__ import annotations

from fastapi import APIRouter, Depends
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from infrastructure.database.repositories.territorio_repository import (
    list_territorios,
)

from dependencies import get_db
from schemas import GeoJsonFeatureCollection

router = APIRouter()


@router.get("/territorios", response_model=GeoJsonFeatureCollection)
def listar_territorios(session: Session = Depends(get_db)) -> GeoJsonFeatureCollection:
    """Bairros de Curitiba como GeoJSON, direto de dim_territorio.

    Geometria de bairro não muda a cada request - resposta estática o
    suficiente para o frontend cachear no cliente.
    """
    territorios = list_territorios(session, nivel="bairro")
    features = [
        {
            "type": "Feature",
            "geometry": mapping(t.geometria) if t.geometria is not None else None,
            "properties": {
                "territorio_id": t.territorio_id,
                "nome": t.nome,
                "nivel": t.nivel,
                "territorio_pai_id": t.territorio_pai_id,
                "cidade_id": t.cidade_id,
            },
        }
        for t in territorios
    ]
    return GeoJsonFeatureCollection(type="FeatureCollection", features=features)
