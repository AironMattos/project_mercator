"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import {
  LngLatBounds,
  Map as MaplibreMap,
  NavigationControl,
  Popup,
  type GeoJSONSource,
} from "maplibre-gl";
import { useEffect, useRef } from "react";

import type { GeoJsonFeatureCollection, MetricaComercio } from "@/lib/api";
import { expressaoCorPorSaldo, NEUTRO_SALDO_ZERO } from "@/lib/palette";

type ChoroplethMapProps = {
  territorios: GeoJsonFeatureCollection;
  metricas: MetricaComercio[];
  onSelecionarTerritorio?: (territorioId: string) => void;
};

const ESTILO_BASE = "https://demotiles.maplibre.org/style.json";
const CENTRO_CURITIBA: [number, number] = [-49.2731, -25.4284];
const FONTE_ID = "territorios";
const CAMADA_PREENCHIMENTO = "territorios-fill";
const CAMADA_LINHA = "territorios-linha";

function calcularBounds(fc: GeoJsonFeatureCollection): LngLatBounds {
  const bounds = new LngLatBounds();
  for (const feature of fc.features) {
    if (!feature.geometry) continue;
    // MultiPolygon: [ [ [ [lng, lat], ... ] ] ]
    const poligonos = feature.geometry.coordinates as unknown as number[][][][];
    for (const poligono of poligonos) {
      for (const anel of poligono) {
        for (const [lng, lat] of anel) {
          bounds.extend([lng, lat]);
        }
      }
    }
  }
  return bounds;
}

function featureCollectionComMetricas(
  territorios: GeoJsonFeatureCollection,
  metricas: MetricaComercio[],
) {
  const porTerritorio = new Map(metricas.map((m) => [m.territorio_id, m]));
  return {
    type: "FeatureCollection" as const,
    features: territorios.features.map((feature) => {
      const metrica = porTerritorio.get(feature.properties.territorio_id);
      return {
        ...feature,
        properties: {
          ...feature.properties,
          // saldo sem dado vira 0 (neutro) de propósito - a expressão de cor
          // já mapeia 0 para o cinza neutro, sem precisar de um caso especial.
          saldo: metrica?.saldo ?? 0,
          aberturas: metrica?.aberturas ?? null,
          desaparecimentos: metrica?.desaparecimentos ?? null,
          temDado: metrica !== undefined,
        },
      };
    }),
  };
}

export function ChoroplethMap({
  territorios,
  metricas,
  onSelecionarTerritorio,
}: ChoroplethMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const popupRef = useRef<Popup | null>(null);
  const onSelecionarRef = useRef(onSelecionarTerritorio);

  useEffect(() => {
    onSelecionarRef.current = onSelecionarTerritorio;
  }, [onSelecionarTerritorio]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new MaplibreMap({
      container: containerRef.current,
      style: ESTILO_BASE,
      center: CENTRO_CURITIBA,
      zoom: 10.5,
    });
    mapRef.current = map;
    popupRef.current = new Popup({ closeButton: false, closeOnClick: false });

    map.addControl(new NavigationControl({ showCompass: false }), "top-right");

    map.on("load", () => {
      const data = featureCollectionComMetricas(territorios, metricas);

      map.addSource(FONTE_ID, {
        type: "geojson",
        data: data as GeoJSON.FeatureCollection,
      });

      map.addLayer({
        id: CAMADA_PREENCHIMENTO,
        type: "fill",
        source: FONTE_ID,
        paint: {
          "fill-color": NEUTRO_SALDO_ZERO,
          "fill-opacity": 0.85,
        },
      });

      map.addLayer({
        id: CAMADA_LINHA,
        type: "line",
        source: FONTE_ID,
        paint: {
          "line-color": "#ffffff",
          "line-width": 0.6,
          "line-opacity": 0.6,
        },
      });

      const bounds = calcularBounds(territorios);
      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: 24, duration: 0 });
      }

      map.on("mousemove", CAMADA_PREENCHIMENTO, (e) => {
        map.getCanvas().style.cursor = "pointer";
        const feature = e.features?.[0];
        if (!feature || !popupRef.current) return;
        const props = feature.properties as Record<string, unknown>;
        const nome = String(props.nome ?? "");
        const temDado = Boolean(props.temDado);
        const saldo = Number(props.saldo ?? 0);
        const conteudo = temDado
          ? `<strong>${nome}</strong><br/>saldo ${saldo > 0 ? "+" : ""}${saldo} (aberturas ${props.aberturas}, fechamentos ${props.desaparecimentos})`
          : `<strong>${nome}</strong><br/>sem evento no período`;
        popupRef.current.setLngLat(e.lngLat).setHTML(conteudo).addTo(map);
      });

      map.on("mouseleave", CAMADA_PREENCHIMENTO, () => {
        map.getCanvas().style.cursor = "";
        popupRef.current?.remove();
      });

      map.on("click", CAMADA_PREENCHIMENTO, (e) => {
        const feature = e.features?.[0];
        const territorioId = feature?.properties?.territorio_id as string | undefined;
        if (territorioId) {
          onSelecionarRef.current?.(territorioId);
        }
      });
    });

    return () => {
      popupRef.current?.remove();
      map.remove();
      mapRef.current = null;
    };
    // Mapa é criado uma única vez; dado é atualizado no efeito abaixo via setData.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const data = featureCollectionComMetricas(territorios, metricas);
    const valores = data.features
      .filter((f) => f.properties.temDado)
      .map((f) => f.properties.saldo);
    const minSaldo = valores.length ? Math.min(...valores) : -1;
    const maxSaldo = valores.length ? Math.max(...valores) : 1;

    const aplicar = () => {
      const source = map.getSource(FONTE_ID) as GeoJSONSource | undefined;
      if (!source) return;
      source.setData(data as GeoJSON.FeatureCollection);
      map.setPaintProperty(
        CAMADA_PREENCHIMENTO,
        "fill-color",
        expressaoCorPorSaldo(minSaldo, maxSaldo),
      );
    };

    if (map.isStyleLoaded() && map.getSource(FONTE_ID)) {
      aplicar();
    } else {
      map.once("load", aplicar);
    }
  }, [territorios, metricas]);

  return <div ref={containerRef} className="h-full w-full" />;
}
