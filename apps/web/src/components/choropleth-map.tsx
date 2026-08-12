"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { StyleSpecification } from "@maplibre/maplibre-gl-style-spec";
import {
  LngLatBounds,
  Map as MaplibreMap,
  NavigationControl,
  Popup,
  setWorkerUrl,
  type GeoJSONSource,
} from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { GeoJsonFeatureCollection, MetricaComercio } from "@/lib/api";
import { expressaoCorPorSaldo, NEUTRO_SALDO_ZERO } from "@/lib/palette";

// MapLibre localiza seu worker via `import.meta.url` do próprio chunk - sob o
// bundler do Next.js (Turbopack, dev e build) isso não resolve para uma URL
// http(s) real, então o worker nunca carrega e as camadas de dado (fill/linha)
// nunca renderizam (fica só o background, sem erro nenhum). Servindo uma cópia
// estática do worker (script `postinstall`, ver package.json) e apontando para
// ela explicitamente, contornamos essa detecção quebrada.
setWorkerUrl("/maplibre-gl-worker.mjs");

type ChoroplethMapProps = {
  territorios: GeoJsonFeatureCollection;
  metricas: MetricaComercio[];
  onSelecionarTerritorio?: (territorioId: string) => void;
};

// Estilo em branco, sem nenhuma fonte externa - o coroplético não depende
// de basemap com ruas/rótulos, e depender de um tile server de terceiros
// (ex.: demotiles.maplibre.org) provou ser frágil atrás de proxy/firewall:
// falha calada (sem "load", sem polígono nenhum) quando a rede bloqueia.
const ESTILO_BASE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "#f9f9f7" },
    },
  ],
};
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
  const [erro, setErro] = useState<string | null>(null);

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

    // Sem isso, uma falha (fonte de dado indisponível, WebGL indisponível
    // etc.) deixa o mapa em branco sem nenhum aviso - o mesmo princípio de
    // nunca deixar tela quebrada em silêncio aplicado no resto do produto.
    map.on("error", (e) => {
      console.error("MapLibre error:", e.error);
      setErro(e.error?.message ?? "Erro desconhecido ao carregar o mapa");
    });

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

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      {erro && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/90 p-6">
          <Alert variant="destructive" className="max-w-md">
            <AlertTitle>Não foi possível carregar o mapa</AlertTitle>
            <AlertDescription>{erro}</AlertDescription>
          </Alert>
        </div>
      )}
    </div>
  );
}
