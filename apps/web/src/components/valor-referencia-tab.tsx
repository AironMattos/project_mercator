"use client";

import { useMemo } from "react";

import { Headline } from "@/components/headline";
import { ImoveisChoroplethMap } from "@/components/imoveis-choropleth-map";
import { MethodologyTooltip } from "@/components/methodology-tooltip";
import { SequentialLegend } from "@/components/sequential-legend";
import type { GeoJsonFeatureCollection, ValorReferenciaBairro } from "@/lib/api";
import { expressaoCorSequencial } from "@/lib/palette";
import { formatarDataDMY } from "@/lib/periodo";

function formatarReais(valor: number): string {
  return `R$ ${new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(valor)}`;
}

function featureCollectionComValor(territorios: GeoJsonFeatureCollection, linhas: ValorReferenciaBairro[]) {
  const porTerritorio = new Map(linhas.map((l) => [l.territorioId, l]));
  return {
    type: "FeatureCollection" as const,
    features: territorios.features.map((feature) => {
      const linha = porTerritorio.get(feature.properties.territorio_id);
      return {
        ...feature,
        properties: {
          ...feature.properties,
          valor: linha?.valorM2Mediano ?? 0,
          quantidadeRegistros: linha?.quantidadeRegistros ?? 0,
          vigenciaInicio: linha?.vigenciaInicio ?? null,
          temDado: linha !== undefined,
        },
      };
    }),
  };
}

type ValorReferenciaTabProps = {
  territorios: GeoJsonFeatureCollection;
  linhas: ValorReferenciaBairro[];
  onSelecionarTerritorio: (territorioId: string) => void;
};

// Aba "Valor de referência" - coroplético sequencial do valor venal
// mediano de terreno (PGV/IPPUC). Sem filtro de período (PGV não é série
// temporal, ver /metodologia#imoveis-valor-referencia) e sem baseline/
// variação - só nível e vigência, mesma trava do checkpoint 11e.
export function ValorReferenciaTab({ territorios, linhas, onSelecionarTerritorio }: ValorReferenciaTabProps) {
  const featureCollection = useMemo(() => featureCollectionComValor(territorios, linhas), [territorios, linhas]);
  const max = useMemo(() => Math.max(1, ...linhas.map((l) => l.valorM2Mediano)), [linhas]);
  const corExpressao = useMemo(() => expressaoCorSequencial("valor", "temDado", max), [max]);

  const vigencia = linhas[0]?.vigenciaInicio;

  return (
    <div className="flex flex-1 flex-col gap-3">
      <div className="flex items-center gap-1.5">
        <Headline>
          Valor venal mediano de terreno em {linhas.length} bairros, segundo a Planta Genérica de
          Valores (IPPUC).
        </Headline>
        <MethodologyTooltip
          titulo="valor de referência"
          formula="Mediana do valor unitário de terreno (VUKT) das microrregiões da PGV dentro de cada bairro — referência oficial de tributação, não preço de mercado ou de anúncio."
          ancora="imoveis-valor-referencia"
        />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <SequentialLegend
          max={max}
          rotulo="R$/m² (valor venal mediano)"
          formatarMax={(v) => formatarReais(v)}
        />
        {vigencia && (
          <span className="text-xs text-muted-foreground">vigente desde {formatarDataDMY(vigencia)}</span>
        )}
      </div>

      <div className="min-h-[520px] flex-1 overflow-hidden rounded-md border">
        <ImoveisChoroplethMap
          territorios={territorios}
          featureCollection={featureCollection as unknown as GeoJSON.FeatureCollection}
          corExpressao={corExpressao}
          onSelecionarTerritorio={onSelecionarTerritorio}
          renderPopup={(props) => {
            const nome = String(props.nome ?? "");
            const temDado = Boolean(props.temDado);
            if (!temDado) return `<strong>${nome}</strong><br/>sem registro de PGV nesse bairro`;
            return `<strong>${nome}</strong><br/>${formatarReais(Number(props.valor))}/m² mediano<br/>${props.quantidadeRegistros} microrregião(ões)`;
          }}
        />
      </div>
    </div>
  );
}
