import { LngLatBounds } from "maplibre-gl";

/**
 * Bounds de uma FeatureCollection de polígonos (Polygon ou MultiPolygon) -
 * extraído de choropleth-map.tsx (checkpoint 7b) para ser reaproveitado
 * pelos mapas do Radar Imobiliário (checkpoint 11f: construção, valor de
 * referência, zoneamento), que precisam do mesmo cálculo sobre geometrias
 * diferentes (bairro ou zona).
 */
export function calcularBoundsPoligonos(fc: GeoJSON.FeatureCollection): LngLatBounds {
  const bounds = new LngLatBounds();
  for (const feature of fc.features) {
    if (!feature.geometry) continue;
    const tipo = feature.geometry.type;
    if (tipo === "MultiPolygon") {
      const poligonos = feature.geometry.coordinates as number[][][][];
      for (const poligono of poligonos) {
        for (const anel of poligono) {
          for (const [lng, lat] of anel) bounds.extend([lng, lat]);
        }
      }
    } else if (tipo === "Polygon") {
      const poligono = feature.geometry.coordinates as number[][][];
      for (const anel of poligono) {
        for (const [lng, lat] of anel) bounds.extend([lng, lat]);
      }
    }
  }
  return bounds;
}
