from __future__ import annotations

from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon

SRID_ORIGEM = 31982
SRID_DESTINO = 4326

_transformer = Transformer.from_crs(
    f"EPSG:{SRID_ORIGEM}", f"EPSG:{SRID_DESTINO}", always_xy=True
)


def reprojetar_anel(ring: list[list[float]]) -> list[tuple[float, float]]:
    return [_transformer.transform(x, y) for x, y in ring]


def anel_e_horario(ring: list[list[float]]) -> bool:
    """Convenção Esri: anéis externos são horários; anéis de buraco são anti-horários."""
    total = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        total += (x2 - x1) * (y2 + y1)
    return total >= 0


def aneis_esri_para_multipolygon(rings: list[list[list[float]]]) -> MultiPolygon:
    """Converte os anéis brutos de uma geometria Esri (esriGeometryPolygon,
    em EPSG:31982) para um MultiPolygon shapely em EPSG:4326.

    Uma geometria Esri pode conter múltiplas partes (polígonos separados) e
    buracos; a convenção de orientação dos anéis é o único jeito de saber
    qual anel é exterior e qual é buraco.
    """
    poligonos: list[tuple[list[list[float]], list[list[list[float]]]]] = []
    for ring in rings:
        if len(ring) < 4:
            continue
        if anel_e_horario(ring) or not poligonos:
            poligonos.append((ring, []))
        else:
            poligonos[-1][1].append(ring)

    shapely_polys = [
        Polygon(
            shell=reprojetar_anel(exterior),
            holes=[reprojetar_anel(buraco) for buraco in buracos],
        )
        for exterior, buracos in poligonos
    ]
    return MultiPolygon(shapely_polys)
