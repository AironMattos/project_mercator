"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import circle from "@turf/circle";
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
import { Skeleton } from "@/components/ui/skeleton";
import type { BuscaRaio } from "@/lib/api";
import { COR_SUPERFICIE, LARGURA_ANEL_SUPERFICIE, MAP_STYLE_URL } from "@/lib/map-style";
import { AZUL_DESTAQUE } from "@/lib/palette";

// Mesma questão de worker do choropleth-map (Turbopack não resolve
// import.meta.url do worker do MapLibre) - ver comentário lá. Chamar de
// novo aqui é inofensivo (mesmo valor), e deixa este componente
// autossuficiente se um dia for usado fora do Dashboard.
setWorkerUrl("/maplibre-gl-worker.mjs");

type RadiusMapProps = {
  resultado: BuscaRaio | null;
  /** Sincronização com a lista de resultados (checkpoint 9g). */
  hoveredId?: string | null;
  onHoverMarker?: (id: string | null) => void;
  /** Clicar numa linha da lista centraliza o mapa nesse estabelecimento -
   * incrementar `selectedNonce` força o flyTo mesmo se `selectedId` não
   * mudou (clicar duas vezes seguidas na mesma linha). */
  selectedId?: string | null;
  selectedNonce?: number;
};

const CENTRO_CURITIBA: [number, number] = [-49.2731, -25.4284];
const FONTE_CIRCULO = "raio-circulo";
const FONTE_PONTOS = "raio-pontos";
const FONTE_CENTRO = "raio-centro";
const CAMADA_CIRCULO_PREENCHIMENTO = "raio-circulo-fill";
const CAMADA_CIRCULO_LINHA = "raio-circulo-linha";
const CAMADA_PONTOS = "raio-pontos-circulo";
const CAMADA_CENTRO = "raio-centro-circulo";

function circuloVazio() {
  return { type: "FeatureCollection" as const, features: [] as GeoJSON.Feature[] };
}

function pontosVazio() {
  return { type: "FeatureCollection" as const, features: [] as GeoJSON.Feature[] };
}

export function RadiusMap({
  resultado,
  hoveredId = null,
  onHoverMarker,
  selectedId = null,
  selectedNonce = 0,
}: RadiusMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const popupRef = useRef<Popup | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregado, setCarregado] = useState(false);
  const onHoverMarkerRef = useRef(onHoverMarker);

  useEffect(() => {
    onHoverMarkerRef.current = onHoverMarker;
  }, [onHoverMarker]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new MaplibreMap({
      container: containerRef.current,
      style: MAP_STYLE_URL,
      center: CENTRO_CURITIBA,
      zoom: 12,
    });
    mapRef.current = map;
    popupRef.current = new Popup({ closeButton: false, closeOnClick: false });

    map.addControl(new NavigationControl({ showCompass: false }), "top-right");

    map.on("error", (e) => {
      console.error("MapLibre error:", e.error);
      setErro(e.error?.message ?? "Erro desconhecido ao carregar o mapa");
    });

    map.on("load", () => {
      map.addSource(FONTE_CIRCULO, { type: "geojson", data: circuloVazio() });
      map.addSource(FONTE_PONTOS, { type: "geojson", data: pontosVazio() });
      map.addSource(FONTE_CENTRO, { type: "geojson", data: pontosVazio() });

      map.addLayer({
        id: CAMADA_CIRCULO_PREENCHIMENTO,
        type: "fill",
        source: FONTE_CIRCULO,
        paint: { "fill-color": AZUL_DESTAQUE, "fill-opacity": 0.08 },
      });
      map.addLayer({
        id: CAMADA_CIRCULO_LINHA,
        type: "line",
        source: FONTE_CIRCULO,
        paint: { "line-color": AZUL_DESTAQUE, "line-width": 1.5, "line-opacity": 0.6 },
      });
      map.addLayer({
        id: CAMADA_PONTOS,
        type: "circle",
        source: FONTE_PONTOS,
        paint: {
          "circle-radius": 6,
          "circle-color": AZUL_DESTAQUE,
          // Anel de 2px na cor de superfície (checkpoint 9f) - contra um
          // mapa-base real com ruas/rótulos, o espaçamento é o que separa
          // o marcador visualmente, não uma borda escura.
          "circle-stroke-width": LARGURA_ANEL_SUPERFICIE,
          "circle-stroke-color": COR_SUPERFICIE,
        },
      });
      map.addLayer({
        id: CAMADA_CENTRO,
        type: "circle",
        source: FONTE_CENTRO,
        paint: {
          "circle-radius": 5,
          "circle-color": "#0b0b0b",
          "circle-stroke-width": LARGURA_ANEL_SUPERFICIE,
          "circle-stroke-color": COR_SUPERFICIE,
        },
      });

      map.on("mousemove", CAMADA_PONTOS, (e) => {
        map.getCanvas().style.cursor = "pointer";
        const feature = e.features?.[0];
        if (!feature || !popupRef.current) return;
        const props = feature.properties as Record<string, unknown>;
        const nome = String(props.nome ?? "(sem nome)");
        const distancia = Math.round(Number(props.distanciaM ?? 0));
        popupRef.current
          .setLngLat(e.lngLat)
          .setHTML(`<strong>${nome}</strong><br/>${distancia}m`)
          .addTo(map);
        onHoverMarkerRef.current?.(String(props.entidadeId ?? ""));
      });
      map.on("mouseleave", CAMADA_PONTOS, () => {
        map.getCanvas().style.cursor = "";
        popupRef.current?.remove();
        onHoverMarkerRef.current?.(null);
      });

      setCarregado(true);
    });

    // Mesma correção do choropleth-map (checkpoint 10d): força resize()
    // quando o container atinge sua dimensão final de layout, em vez de só
    // repintar depois de uma interação manual do usuário.
    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      popupRef.current?.remove();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !carregado) return;

    const source_circulo = map.getSource(FONTE_CIRCULO) as GeoJSONSource | undefined;
    const source_pontos = map.getSource(FONTE_PONTOS) as GeoJSONSource | undefined;
    const source_centro = map.getSource(FONTE_CENTRO) as GeoJSONSource | undefined;
    if (!source_circulo || !source_pontos || !source_centro) return;

    if (!resultado) {
      source_circulo.setData(circuloVazio());
      source_pontos.setData(pontosVazio());
      source_centro.setData(pontosVazio());
      return;
    }

    const { lat, lon } = resultado.pontoBusca;
    const circuloGeojson = circle([lon, lat], resultado.raioM, { units: "meters", steps: 64 });
    source_circulo.setData(circuloGeojson as unknown as GeoJSON.FeatureCollection);

    source_centro.setData({
      type: "FeatureCollection",
      features: [{ type: "Feature", geometry: { type: "Point", coordinates: [lon, lat] }, properties: {} }],
    });

    source_pontos.setData({
      type: "FeatureCollection",
      features: resultado.estabelecimentos.map((e) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [e.ponto.lon, e.ponto.lat] },
        properties: { nome: e.nome ?? "(sem nome)", distanciaM: e.distanciaM, entidadeId: e.entidadeId },
      })),
    });

    const bounds = new LngLatBounds();
    for (const coord of (circuloGeojson.geometry.coordinates[0] as [number, number][])) {
      bounds.extend(coord);
    }
    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, { padding: 40, duration: 300 });
    }
  }, [resultado, carregado]);

  // Destaque do marcador correspondente à linha da lista sob o mouse
  // (checkpoint 9g) - expressão de estilo em vez de feature-state, mais
  // simples de manter sincronizada com um id vindo de fora do mapa.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !carregado || !map.getLayer(CAMADA_PONTOS)) return;

    const destacado = hoveredId ?? "";
    map.setPaintProperty(CAMADA_PONTOS, "circle-radius", [
      "case",
      ["==", ["get", "entidadeId"], destacado],
      10,
      6,
    ]);
    map.setPaintProperty(CAMADA_PONTOS, "circle-stroke-width", [
      "case",
      ["==", ["get", "entidadeId"], destacado],
      3,
      LARGURA_ANEL_SUPERFICIE,
    ]);
  }, [hoveredId, carregado]);

  // Clicar numa linha da lista centraliza o mapa nesse estabelecimento.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !carregado || !resultado || !selectedId || selectedNonce === 0) return;

    const alvo = resultado.estabelecimentos.find((e) => e.entidadeId === selectedId);
    if (!alvo) return;
    map.flyTo({ center: [alvo.ponto.lon, alvo.ponto.lat], zoom: Math.max(map.getZoom(), 16), duration: 500 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNonce, carregado]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      {!carregado && !erro && (
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
