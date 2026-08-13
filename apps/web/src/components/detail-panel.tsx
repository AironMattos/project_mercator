"use client";

import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Headline } from "@/components/headline";
import { QuebraCategoriaBars } from "@/components/quebra-categoria";
import { SerieTemporalChart } from "@/components/serie-temporal-chart";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/stat-tile";
import { getBairroResumo, type BairroResumo } from "@/lib/api";
import { mancheteDetalheBairro } from "@/lib/manchete";

type TerritorioSelecionado = { id: string; nome: string };

type DetailPanelProps = {
  territorio: TerritorioSelecionado | null;
  categoriaId: string | undefined;
  dataInicio: string;
  dataFim: string;
  onOpenChange: (open: boolean) => void;
};

type Estado =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; resumo: BairroResumo };

// Checkpoint 8d: expande o painel do checkpoint 7c (que só tinha a série
// temporal) com cabeçalho + posição no ranking, stat tiles de
// aberturas/saldo, e quebra por categoria - tudo vindo de uma única
// chamada a GET /bairros/{id}/resumo, que já reaproveita a série temporal
// de /metricas/comercio (não duplicamos essa busca aqui).
export function DetailPanel({
  territorio,
  categoriaId,
  dataInicio,
  dataFim,
  onOpenChange,
}: DetailPanelProps) {
  const [estado, setEstado] = useState<Estado>({ status: "carregando" });

  useEffect(() => {
    if (!territorio) return;
    let cancelado = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- indicador de carregamento pro fetch do resumo ao trocar de bairro/filtro, não há como derivar isso do render.
    setEstado({ status: "carregando" });

    getBairroResumo(territorio.id, { categoriaId, dataInicio, dataFim })
      .then((resumo) => {
        if (!cancelado) setEstado({ status: "pronto", resumo });
      })
      .catch((erro: unknown) => {
        if (cancelado) return;
        setEstado({
          status: "erro",
          mensagem: erro instanceof Error ? erro.message : "Erro desconhecido",
        });
      });

    return () => {
      cancelado = true;
    };
  }, [territorio, categoriaId, dataInicio, dataFim]);

  const pontosChart =
    estado.status === "pronto"
      ? estado.resumo.serieTemporal
          .filter((l) => l.mes !== null)
          .map((l) => ({
            mes: l.mes as string,
            aberturas: l.aberturas,
            desaparecimentos: l.desaparecimentos,
          }))
          .sort((a, b) => a.mes.localeCompare(b.mes))
      : [];

  return (
    <Sheet open={territorio !== null} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{territorio?.nome ?? ""}</SheetTitle>
          {estado.status === "pronto" ? (
            <Headline size="md" className="pt-1">
              {mancheteDetalheBairro(estado.resumo)}
            </Headline>
          ) : estado.status === "carregando" ? (
            <Skeleton className="mt-1 h-7 w-full" />
          ) : null}
          <SheetDescription>
            {categoriaId ? "categoria filtrada" : "todas as categorias"}
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-4 px-4 pb-4">
          {estado.status === "carregando" && (
            <div className="space-y-3" role="status" aria-label="Carregando">
              <div className="flex gap-3">
                <Skeleton className="h-24 flex-1" />
                <Skeleton className="h-24 flex-1" />
              </div>
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-72 w-full" />
            </div>
          )}

          {estado.status === "erro" && (
            <Alert variant="destructive">
              <AlertTitle>Não foi possível carregar o resumo</AlertTitle>
              <AlertDescription>{estado.mensagem}</AlertDescription>
            </Alert>
          )}

          {estado.status === "pronto" && (
            <>
              <div className="flex gap-3">
                <StatTile
                  rotulo="aberturas"
                  valorAtual={estado.resumo.aberturas.valorAtual}
                  baseline={estado.resumo.aberturas.baseline}
                  variacaoPct={estado.resumo.aberturas.variacaoPct}
                  tendencia={estado.resumo.aberturas.tendencia}
                  motivoIndisponivel={estado.resumo.aberturas.motivoIndisponivel}
                  cimaEBom
                  metodologia={{
                    formula:
                      "Novos estabelecimentos identificados no mês, comparados à média móvel dos 24 meses anteriores.",
                    ancora: "baseline",
                  }}
                />
                <StatTile
                  rotulo="saldo"
                  valorAtual={estado.resumo.saldo.valorAtual}
                  baseline={estado.resumo.saldo.baseline}
                  variacaoPct={estado.resumo.saldo.variacaoPct}
                  tendencia={estado.resumo.saldo.tendencia}
                  motivoIndisponivel={estado.resumo.saldo.motivoIndisponivel}
                  cimaEBom
                  mensagemConstrucao={
                    estado.resumo.saldo.motivoIndisponivel === "historico_insuficiente"
                      ? "dado de fechamento em construção — acompanhando mês a mês"
                      : undefined
                  }
                  metodologia={{ formula: "Aberturas menos fechamentos (desaparecimentos) no período.", ancora: "saldo" }}
                />
              </div>

              <div>
                <p className="mb-1.5 text-xs text-muted-foreground">
                  categorias que mais abriram no período
                </p>
                <QuebraCategoriaBars itens={estado.resumo.quebraCategoria} />
              </div>

              <div>
                <p className="mb-1.5 text-xs text-muted-foreground">
                  aberturas e desaparecimentos por mês
                </p>
                {pontosChart.length === 0 ? (
                  <Alert>
                    <AlertTitle>Sem eventos no período</AlertTitle>
                    <AlertDescription>
                      Não há aberturas nem desaparecimentos registrados para este bairro com os
                      filtros atuais.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <SerieTemporalChart pontos={pontosChart} />
                )}
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
