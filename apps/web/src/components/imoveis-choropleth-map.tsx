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
import { useEffect, useRef, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import type { GeoJsonFeatureCollection } from "@/lib/api";
import { calcularBoundsPoligonos } from "@/lib/geo";
import { COR_SUPERFICIE, LARGURA_ANEL_SUPERFICIE, MAP_STYLE_URL } from "@/lib/map-style";
import { NEUTRO_SALDO_ZERO } from "@/lib/palette";

// Mesma questão de worker do choropleth-map.tsx (Turbopack não resolve
// import.meta.url do worker do MapLibre) - ver comentário lá. Inofensivo
// chamar de novo aqui (mesmo valor).
setWorkerUrl("/maplibre-gl-worker.mjs");

const CENTRO_CURITIBA: [number, number] = [-49.2731, -25.4284];
const FONTE_ID = "imoveis-territorios";
const CAMADA_PREENCHIMENTO = "imoveis-territorios-fill";
const CAMADA_LINHA = "imoveis-territorios-linha";

/**
 * Coroplético genérico por bairro (Radar Imobiliário, checkpoint 11f) -
 * reaproveitado por construção e valor de referência, que são a mesma forma
 * (mapear um valor numérico por território, num bairro que pode ou não ter
 * dado) com fonte/expressão de cor diferentes. Diferente de ChoroplethMap
 * (comércio), que é fixo à semântica de saldo/aberturas/desaparecimentos -
 * aqui o chamador já entrega a FeatureCollection mesclada e a expressão de
 * cor prontas, então o componente não precisa conhecer o domínio do dado.
 */
type ImoveisChoroplethMapProps = {
  territorios: GeoJsonFeatureCollection;
  featureCollection: GeoJSON.FeatureCollection;
  corExpressao: ExpressionSpecification;
  renderPopup: (props: Record<string, unknown>) => string;
  onSelecionarTerritorio?: (territorioId: string) => void;
};

export function ImoveisChoroplethMap({
  territorios,
  featureCollection,
  corExpressao,
  renderPopup,
  onSelecionarTerritorio,
}: ImoveisChoroplethMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const popupRef = useRef<Popup | null>(null);
  const onSelecionarRef = useRef(onSelecionarTerritorio);
  const renderPopupRef = useRef(renderPopup);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    onSelecionarRef.current = onSelecionarTerritorio;
  }, [onSelecionarTerritorio]);
  useEffect(() => {
    renderPopupRef.current = renderPopup;
  }, [renderPopup]);

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
      map.addSource(FONTE_ID, { type: "geojson", data: featureCollection });

      map.addLayer({
        id: CAMADA_PREENCHIMENTO,
        type: "fill",
        source: FONTE_ID,
        paint: { "fill-color": NEUTRO_SALDO_ZERO, "fill-opacity": 0.85 },
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

      const bounds = calcularBoundsPoligonos(territorios as unknown as GeoJSON.FeatureCollection);
      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: 24, duration: 0 });
      }

      map.on("mousemove", CAMADA_PREENCHIMENTO, (e) => {
        map.getCanvas().style.cursor = "pointer";
        const feature = e.features?.[0];
        if (!feature || !popupRef.current) return;
        const props = feature.properties as Record<string, unknown>;
        popupRef.current.setLngLat(e.lngLat).setHTML(renderPopupRef.current(props)).addTo(map);
      });

      map.on("mouseleave", CAMADA_PREENCHIMENTO, () => {
        map.getCanvas().style.cursor = "";
        popupRef.current?.remove();
      });

      map.on("click", CAMADA_PREENCHIMENTO, (e) => {
        const feature = e.features?.[0];
        const territorioId = feature?.properties?.territorio_id as string | undefined;
        if (territorioId) onSelecionarRef.current?.(territorioId);
      });

      setCarregando(false);
    });

    // Mesma correção do choropleth-map (checkpoint 10d): força resize()
    // quando o container atinge sua dimensão final de layout.
    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      popupRef.current?.remove();
      map.remove();
      mapRef.current = null;
    };
    // Mapa é criado uma única vez; dado/cor são atualizados no efeito abaixo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const aplicar = () => {
      const source = map.getSource(FONTE_ID) as GeoJSONSource | undefined;
      if (!source) return;
      source.setData(featureCollection);
      map.setPaintProperty(CAMADA_PREENCHIMENTO, "fill-color", corExpressao);
    };

    if (map.isStyleLoaded() && map.getSource(FONTE_ID)) {
      aplicar();
    } else {
      map.once("load", aplicar);
    }
  }, [featureCollection, corExpressao]);

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
