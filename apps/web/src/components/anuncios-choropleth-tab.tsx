"use client";

import { useMemo } from "react";

import { ImoveisChoroplethMap } from "@/components/imoveis-choropleth-map";
import { SequentialLegend } from "@/components/sequential-legend";
import type { GeoJsonFeatureCollection, TermometroBairro } from "@/lib/api";
import { expressaoCorSequencial } from "@/lib/palette";

function formatarReais(valor: number): string {
  return `R$ ${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(valor)}`;
}

function featureCollectionComPreco(
  territorios: GeoJsonFeatureCollection,
  linhas: TermometroBairro[],
) {
  const porTerritorio = new Map(linhas.map((l) => [l.territorioId, l]));
  return {
    type: "FeatureCollection" as const,
    features: territorios.features.map((feature) => {
      const linha = porTerritorio.get(feature.properties.territorio_id);
      return {
        ...feature,
        properties: {
          ...feature.properties,
          valor: linha?.precoMediano ?? 0,
          estoque: linha?.estoque ?? 0,
          temDado: Boolean(linha?.amostraPrecoSuficiente),
        },
      };
    }),
  };
}

type AnunciosChoroplethTabProps = {
  territorios: GeoJsonFeatureCollection;
  linhas: TermometroBairro[];
  operacaoLabel: string;
  onSelecionarTerritorio: (territorioId: string) => void;
};

// Mapa principal do Radar de Anúncios (checkpoint 12i, seção 10) - o
// prompt de referência pede coloração pelo quadrante de aquecimento
// (seção 2.1), mas o quadrante depende de baseline histórica que ainda
// não existe pra nenhum bairro (checkpoint 12f/12g) - colorir por preço
// pedido mediano é o melhor sinal real disponível hoje, com a mesma
// rampa sequencial já usada em Valor de referência (Radar Imobiliário).
// Terceira correção da seção 10 aplicada: a legenda declara quantos
// bairros ficaram de fora por amostra insuficiente, nunca uma área cinza
// sem explicação.
export function AnunciosChoroplethTab({
  territorios,
  linhas,
  operacaoLabel,
  onSelecionarTerritorio,
}: AnunciosChoroplethTabProps) {
  const featureCollection = useMemo(
    () => featureCollectionComPreco(territorios, linhas),
    [territorios, linhas],
  );
  const comAmostra = linhas.filter((l) => l.amostraPrecoSuficiente);
  const max = useMemo(
    () => Math.max(1, ...comAmostra.map((l) => l.precoMediano ?? 0)),
    [comAmostra],
  );
  const corExpressao = useMemo(() => expressaoCorSequencial("valor", "temDado", max), [max]);

  const semAmostra = linhas.length - comAmostra.length;

  return (
    <div className="flex flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <SequentialLegend
          max={max}
          rotulo={`R$ (preço pedido mediano — ${operacaoLabel})`}
          formatarMax={(v) => formatarReais(v)}
        />
        <span className="text-xs text-muted-foreground">
          {comAmostra.length} de {linhas.length} bairros com amostra suficiente (≥ 30 anúncios) para
          mediana de preço
          {semAmostra > 0 && ` — os outros ${semAmostra} aparecem em cinza`}
        </span>
        <span className="ml-auto text-xs text-muted-foreground">
          quadrante de aquecimento aparece aqui assim que houver histórico suficiente
        </span>
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
            const estoque = Number(props.estoque ?? 0);
            if (!temDado) {
              return `<strong>${nome}</strong><br/>${estoque} anúncio(s) — amostra insuficiente para mediana`;
            }
            return `<strong>${nome}</strong><br/>${formatarReais(Number(props.valor))} mediano<br/>${estoque} anúncios ativos`;
          }}
        />
      </div>
    </div>
  );
}
