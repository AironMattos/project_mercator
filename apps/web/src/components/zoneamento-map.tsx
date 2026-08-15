"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { ExpressionSpecification } from "@maplibre/maplibre-gl-style-spec";
import {
  Map as MaplibreMap,
  NavigationControl,
  Popup,
  setWorkerUrl,
  type GeoJSONSource,
} from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import type { ZoneamentoFeatureCollection } from "@/lib/api";
import { calcularBoundsPoligonos } from "@/lib/geo";
import { COR_SUPERFICIE, LARGURA_ANEL_SUPERFICIE, MAP_STYLE_URL } from "@/lib/map-style";
import { CATEGORICO_ZONEAMENTO, ZONA_OUTROS_COR } from "@/lib/palette";

setWorkerUrl("/maplibre-gl-worker.mjs");

const CENTRO_CURITIBA: [number, number] = [-49.2731, -25.4284];
const FONTE_ID = "zoneamento";
const CAMADA_PREENCHIMENTO = "zoneamento-fill";
const CAMADA_LINHA = "zoneamento-linha";
const GRUPO_OUTROS = "outros";

// Só os 3 grupos de zoneamento mais frequentes ganham cor categórica própria
// (ver CATEGORICO_ZONEAMENTO em lib/palette.ts - limite do skill dataviz
// pra choropleth) - os demais (Curitiba tem 12 nm_grupo reais) caem em
// "outros", neutro.
export function top3Grupos(fc: ZoneamentoFeatureCollection): string[] {
  const contagem = new Map<string, number>();
  for (const f of fc.features) {
    const grupo = f.properties.nm_grupo ?? GRUPO_OUTROS;
    contagem.set(grupo, (contagem.get(grupo) ?? 0) + 1);
  }
  return [...contagem.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([grupo]) => grupo);
}

function featureCollectionComGrupo(fc: ZoneamentoFeatureCollection, top3: string[]) {
  return {
    type: "FeatureCollection" as const,
    features: fc.features.map((feature) => {
      const grupoReal = feature.properties.nm_grupo ?? GRUPO_OUTROS;
      return {
        ...feature,
        properties: {
          ...feature.properties,
          grupoCor: top3.includes(grupoReal) ? grupoReal : GRUPO_OUTROS,
        },
      };
    }),
  };
}

type ZoneamentoMapProps = {
  zoneamento: ZoneamentoFeatureCollection;
};

export function ZoneamentoMap({ zoneamento }: ZoneamentoMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const popupRef = useRef<Popup | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  const top3 = useMemo(() => top3Grupos(zoneamento), [zoneamento]);
  const data = useMemo(() => featureCollectionComGrupo(zoneamento, top3), [zoneamento, top3]);

  const corExpressao = useMemo<ExpressionSpecification>(() => {
    const expressao: unknown[] = ["match", ["get", "grupoCor"]];
    top3.forEach((grupo, indice) => {
      expressao.push(grupo, CATEGORICO_ZONEAMENTO[indice]);
    });
    expressao.push(ZONA_OUTROS_COR);
    return expressao as unknown as ExpressionSpecification;
  }, [top3]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new MaplibreMap({
      container: containerRef.current,
      style: MAP_STYLE_URL,
      center: CENTRO_CURITIBA,
      zoom: 10.5,
    });
    mapRef.current = map;
    popupRef.current = new Popup({ closeButton: false, closeOnClick: false });

    map.addControl(new NavigationControl({ showCompass: false }), "top-right");

    map.on("error", (e) => {
      console.error("MapLibre error:", e.error);
      setErro(e.error?.message ?? "Erro desconhecido ao carregar o mapa");
    });

    map.on("load", () => {
      map.addSource(FONTE_ID, { type: "geojson", data: data as unknown as GeoJSON.FeatureCollection });

      map.addLayer({
        id: CAMADA_PREENCHIMENTO,
        type: "fill",
        source: FONTE_ID,
        paint: {
          "fill-color": corExpressao,
          "fill-opacity": 0.55,
        },
      });

      map.addLayer({
        id: CAMADA_LINHA,
        type: "line",
        source: FONTE_ID,
        paint: {
          "line-color": COR_SUPERFICIE,
          "line-width": LARGURA_ANEL_SUPERFICIE,
          "line-opacity": 1,
        },
      });

      const bounds = calcularBoundsPoligonos(data as unknown as GeoJSON.FeatureCollection);
      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: 24, duration: 0 });
      }

      map.on("mousemove", CAMADA_PREENCHIMENTO, (e) => {
        map.getCanvas().style.cursor = "pointer";
        const feature = e.features?.[0];
        if (!feature || !popupRef.current) return;
        const props = feature.properties as Record<string, unknown>;
        const conteudo = `<strong>${props.nm_zona ?? props.sg_zona}</strong> (${props.sg_zona})<br/>${props.nm_grupo ?? "sem grupo"}${props.legislacao ? `<br/>${props.legislacao}` : ""}`;
        popupRef.current.setLngLat(e.lngLat).setHTML(conteudo).addTo(map);
      });
      map.on("mouseleave", CAMADA_PREENCHIMENTO, () => {
        map.getCanvas().style.cursor = "";
        popupRef.current?.remove();
      });

      setCarregando(false);
    });

    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      popupRef.current?.remove();
      map.remove();
      mapRef.current = null;
    };
    // Mapa criado uma única vez; dado inicial já é o `data`/`corExpressao`
    // calculados no primeiro render - reaplicados via o efeito abaixo se o
    // zoneamento mudar (não muda hoje, é uma fonte estática, mas mantém o
    // componente consistente com o padrão dos outros mapas do produto).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const aplicar = () => {
      const source = map.getSource(FONTE_ID) as GeoJSONSource | undefined;
      if (!source) return;
      source.setData(data as unknown as GeoJSON.FeatureCollection);
      map.setPaintProperty(CAMADA_PREENCHIMENTO, "fill-color", corExpressao);
    };

    if (map.isStyleLoaded() && map.getSource(FONTE_ID)) {
      aplicar();
    } else {
      map.once("load", aplicar);
    }
  }, [data, corExpressao]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      {carregando && !erro && (
        <div className="absolute inset-0" aria-hidden>
          <Skeleton className="h-full w-full rounded-none" />
        </div>
      )}
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
