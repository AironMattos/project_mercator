"use client";

import { useMemo, useState } from "react";

import { Headline } from "@/components/headline";
import { ImoveisChoroplethMap } from "@/components/imoveis-choropleth-map";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SequentialLegend } from "@/components/sequential-legend";
import type { GeoJsonFeatureCollection, MetricaConstrucao } from "@/lib/api";
import { formatarValorCompacto } from "@/lib/indicadores";
import { expressaoCorSequencial } from "@/lib/palette";

type Metrica = "alvarasAprovados" | "cvcosConcluidos";

const ROTULOS_METRICA: Record<Metrica, { curto: string; tile: string }> = {
  alvarasAprovados: { curto: "Alvarás aprovados", tile: "alvarás aprovados" },
  cvcosConcluidos: { curto: "CVCOs concluídos", tile: "CVCOs concluídos" },
};

function featureCollectionComValor(
  territorios: GeoJsonFeatureCollection,
  linhas: MetricaConstrucao[],
  metrica: Metrica,
) {
  const porTerritorio = new Map(linhas.filter((l) => l.territorioId).map((l) => [l.territorioId as string, l]));
  return {
    type: "FeatureCollection" as const,
    features: territorios.features.map((feature) => {
      const linha = porTerritorio.get(feature.properties.territorio_id);
      return {
        ...feature,
        properties: {
          ...feature.properties,
          valor: linha ? linha[metrica] : 0,
          alvarasAprovados: linha?.alvarasAprovados ?? 0,
          cvcosConcluidos: linha?.cvcosConcluidos ?? 0,
          areaLicenciadaM2: linha?.areaLicenciadaM2 ?? 0,
          areaConcluidaM2: linha?.areaConcluidaM2 ?? 0,
          temDado: linha !== undefined,
        },
      };
    }),
  };
}

function formatarM2(valor: number): string {
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(valor)} m²`;
}

type ConstrucaoTabProps = {
  territorios: GeoJsonFeatureCollection;
  linhas: MetricaConstrucao[];
  onSelecionarTerritorio: (territorioId: string) => void;
};

// Aba "Construção" do Radar Imobiliário (checkpoint 11f) - coroplético
// sequencial (nunca divergente: não há polo negativo em contagem de alvará/
// CVCO) com toggle entre as duas métricas, que nunca são somadas numa
// "atividade construtiva" única (trava metodológica do checkpoint 11b/11e:
// alvará = "vai mudar", CVCO = "já mudou", perguntas diferentes).
export function ConstrucaoTab({ territorios, linhas, onSelecionarTerritorio }: ConstrucaoTabProps) {
  const [metrica, setMetrica] = useState<Metrica>("alvarasAprovados");

  const featureCollection = useMemo(
    () => featureCollectionComValor(territorios, linhas, metrica),
    [territorios, linhas, metrica],
  );

  const max = useMemo(
    () => Math.max(1, ...featureCollection.features.map((f) => f.properties.valor)),
    [featureCollection],
  );

  const corExpressao = useMemo(() => expressaoCorSequencial("valor", "temDado", max), [max]);

  const totalAlvaras = linhas.reduce((soma, l) => soma + l.alvarasAprovados, 0);
  const totalCvcos = linhas.reduce((soma, l) => soma + l.cvcosConcluidos, 0);

  return (
    <div className="flex flex-1 flex-col gap-3">
      <Headline>
        {formatarValorCompacto(totalAlvaras)} alvarás aprovados e{" "}
        {formatarValorCompacto(totalCvcos)} CVCOs concluídos no período, entre os bairros de
        Curitiba.
      </Headline>

      <div className="flex flex-wrap items-center gap-3">
        <Select value={metrica} onValueChange={(v) => v && setMetrica(v as Metrica)}>
          <SelectTrigger className="w-56">
            <SelectValue>{ROTULOS_METRICA[metrica].curto}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="alvarasAprovados">Alvarás aprovados</SelectItem>
            <SelectItem value="cvcosConcluidos">CVCOs concluídos</SelectItem>
          </SelectContent>
        </Select>
        <SequentialLegend max={max} rotulo={ROTULOS_METRICA[metrica].tile} />
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
            if (!temDado) {
              return `<strong>${nome}</strong><br/>sem alvará/CVCO no período`;
            }
            return `<strong>${nome}</strong><br/>${formatarValorCompacto(Number(props.alvarasAprovados))} alvarás (${formatarM2(Number(props.areaLicenciadaM2))})<br/>${formatarValorCompacto(Number(props.cvcosConcluidos))} CVCOs (${formatarM2(Number(props.areaConcluidaM2))})`;
          }}
        />
      </div>
    </div>
  );
}
