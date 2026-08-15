"use client";

import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ConstrucaoSerieChart } from "@/components/construcao-serie-chart";
import { FatoTile } from "@/components/fato-tile";
import { Headline } from "@/components/headline";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { getConstrucao, type MetricaConstrucao, type ValorReferenciaBairro } from "@/lib/api";
import { formatarValorCompacto, motivoIndisponivelLegivel } from "@/lib/indicadores";

type TerritorioSelecionado = { id: string; nome: string };

type ImoveisDetailPanelProps = {
  territorio: TerritorioSelecionado | null;
  /** Linha agregada do período já carregada pelo mapa (checkpoint 11f) -
   * reaproveitada aqui, não refeita, mesmo princípio de DetailPanel
   * (comércio) reaproveitando /bairros/{id}/resumo em vez de duplicar
   * fetches. undefined = bairro sem nenhum alvará/CVCO no período. */
  construcaoAgregada: MetricaConstrucao | undefined;
  valorReferencia: ValorReferenciaBairro | undefined;
  dataInicio: string;
  dataFim: string;
  onOpenChange: (open: boolean) => void;
};

type EstadoSerie =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; pontos: MetricaConstrucao[] };

function formatarM2(valor: number): string {
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(valor)} m²`;
}

function formatarReais(valor: number): string {
  return `R$ ${new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(valor)}`;
}

// Painel de detalhe do Radar Imobiliário (checkpoint 11f) - mesma forma do
// DetailPanel de comércio (Sheet lateral, StatTile-like + série mensal),
// mas com FatoTile (sem baseline/tendência: a API de construção não expõe
// isso, ver GET /imoveis/construcao) e as duas séries próprias (alvará x
// CVCO, nunca somadas).
export function ImoveisDetailPanel({
  territorio,
  construcaoAgregada,
  valorReferencia,
  dataInicio,
  dataFim,
  onOpenChange,
}: ImoveisDetailPanelProps) {
  const [serie, setSerie] = useState<EstadoSerie>({ status: "carregando" });

  useEffect(() => {
    if (!territorio) return;
    let cancelado = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- indicador de carregamento pro fetch da série ao trocar de bairro/período, não há como derivar isso do render.
    setSerie({ status: "carregando" });

    getConstrucao({ territorioId: territorio.id, dataInicio, dataFim })
      .then((pontos) => {
        if (!cancelado) setSerie({ status: "pronto", pontos });
      })
      .catch((erro: unknown) => {
        if (!cancelado) {
          setSerie({
            status: "erro",
            mensagem: erro instanceof Error ? erro.message : "Erro desconhecido",
          });
        }
      });
    return () => {
      cancelado = true;
    };
  }, [territorio, dataInicio, dataFim]);

  const pontosChart =
    serie.status === "pronto"
      ? serie.pontos
          .filter((p) => p.mes !== null)
          .map((p) => ({
            mes: p.mes as string,
            alvarasAprovados: p.alvarasAprovados,
            cvcosConcluidos: p.cvcosConcluidos,
          }))
          .sort((a, b) => a.mes.localeCompare(b.mes))
      : [];

  return (
    <Sheet open={territorio !== null} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{territorio?.nome ?? ""}</SheetTitle>
          <Headline size="md" className="pt-1">
            Construção e valor de referência
          </Headline>
          <SheetDescription>período filtrado no mapa</SheetDescription>
        </SheetHeader>

        <div className="space-y-4 px-4 pb-4">
          <div className="flex flex-wrap gap-3">
            <FatoTile
              rotulo="alvarás aprovados"
              valor={formatarValorCompacto(construcaoAgregada?.alvarasAprovados ?? 0)}
              metodologia={{
                formula: "Alvarás de construção com data de criação dentro do período filtrado.",
                ancora: "imoveis-alvara-cvco",
              }}
            />
            <FatoTile
              rotulo="área licenciada"
              valor={formatarM2(construcaoAgregada?.areaLicenciadaM2 ?? 0)}
            />
            <FatoTile
              rotulo="CVCOs concluídos"
              valor={formatarValorCompacto(construcaoAgregada?.cvcosConcluidos ?? 0)}
              metodologia={{
                formula: "Certificados de Vistoria de Conclusão de Obra emitidos dentro do período filtrado.",
                ancora: "imoveis-alvara-cvco",
              }}
            />
            <FatoTile
              rotulo="área concluída"
              valor={formatarM2(construcaoAgregada?.areaConcluidaM2 ?? 0)}
            />
          </div>

          <div className="flex flex-wrap gap-3">
            <FatoTile
              rotulo="defasagem mediana alvará → CVCO"
              valor={
                construcaoAgregada?.defasagemMedianaDias != null
                  ? `${Math.round(construcaoAgregada.defasagemMedianaDias)} dias`
                  : motivoIndisponivelLegivel(construcaoAgregada?.motivoIndisponivelDefasagem ?? "historico_insuficiente")
              }
              metodologia={{
                formula:
                  "Mediana, em dias, entre a aprovação do alvará e a conclusão do CVCO do mesmo empreendimento — exige ao menos 3 pares observados.",
                ancora: "imoveis-defasagem",
              }}
            />
            <FatoTile
              rotulo="valor venal mediano (PGV)"
              valor={valorReferencia ? `${formatarReais(valorReferencia.valorM2Mediano)}/m²` : "sem registro de PGV nesse bairro"}
              metodologia={{
                formula:
                  "Mediana do valor unitário de terreno (VUKT) das microrregiões da Planta Genérica de Valores no bairro — referência de tributação, não preço de mercado.",
                ancora: "imoveis-valor-referencia",
              }}
            />
          </div>

          <div>
            <p className="mb-1.5 text-xs text-muted-foreground">
              alvarás aprovados e CVCOs concluídos por mês
            </p>
            {serie.status === "carregando" && <Skeleton className="h-72 w-full" />}
            {serie.status === "erro" && (
              <Alert variant="destructive">
                <AlertTitle>Não foi possível carregar a série</AlertTitle>
                <AlertDescription>{serie.mensagem}</AlertDescription>
              </Alert>
            )}
            {serie.status === "pronto" && pontosChart.length === 0 && (
              <Alert>
                <AlertTitle>Sem eventos no período</AlertTitle>
                <AlertDescription>
                  Não há alvará aprovado nem CVCO concluído registrado para este bairro com os
                  filtros atuais.
                </AlertDescription>
              </Alert>
            )}
            {serie.status === "pronto" && pontosChart.length > 0 && (
              <ConstrucaoSerieChart pontos={pontosChart} />
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
