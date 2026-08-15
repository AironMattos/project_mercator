"use client";

import { useMemo } from "react";

import { CategoricalLegend } from "@/components/categorical-legend";
import { Headline } from "@/components/headline";
import { MethodologyTooltip } from "@/components/methodology-tooltip";
import { top3Grupos, ZoneamentoMap } from "@/components/zoneamento-map";
import type { ZoneamentoFeatureCollection } from "@/lib/api";
import { CATEGORICO_ZONEAMENTO, ZONA_OUTROS_COR } from "@/lib/palette";

type ZoneamentoTabProps = {
  zoneamento: ZoneamentoFeatureCollection;
};

// Aba "Zoneamento" - camada estática de parâmetros construtivos por
// polígono (Lei 15.511/2019). Só os 3 grupos mais frequentes ganham cor
// categórica própria (checkpoint 11f: limite all-pairs do skill dataviz
// pra choropleth) - os demais 9 grupos reais de Curitiba entram em
// "outros", visível na legenda, nunca escondidos.
export function ZoneamentoTab({ zoneamento }: ZoneamentoTabProps) {
  const top3 = useMemo(() => top3Grupos(zoneamento), [zoneamento]);
  const totalGrupos = useMemo(
    () => new Set(zoneamento.features.map((f) => f.properties.nm_grupo ?? "outros")).size,
    [zoneamento],
  );

  const itensLegenda = [
    ...top3.map((grupo, i) => ({ rotulo: grupo, cor: CATEGORICO_ZONEAMENTO[i] })),
    { rotulo: `outros (${Math.max(0, totalGrupos - top3.length)} grupos)`, cor: ZONA_OUTROS_COR },
  ];

  return (
    <div className="flex flex-1 flex-col gap-3">
      <div className="flex items-center gap-1.5">
        <Headline>
          {zoneamento.features.length} zonas de uso e ocupação do solo, segundo a Lei
          15.511/2019.
        </Headline>
        <MethodologyTooltip
          titulo="zoneamento"
          formula="Camada estática de parâmetros construtivos por polígono (GeoCuritiba) — sem vigência histórica: reflete a versão mais recente publicada."
          ancora="imoveis-zoneamento"
        />
      </div>

      <CategoricalLegend itens={itensLegenda} />

      <div className="min-h-[520px] flex-1 overflow-hidden rounded-md border">
        <ZoneamentoMap zoneamento={zoneamento} />
      </div>
    </div>
  );
}
