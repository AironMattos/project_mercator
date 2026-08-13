"use client";

import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Headline } from "@/components/headline";
import { MethodologyTooltip } from "@/components/methodology-tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { getRankingCategorias, type RankingCategoriaItem } from "@/lib/api";
import { corDelta, formatarDeltaPct, formatarValorCompacto } from "@/lib/indicadores";
import { mancheteRankingCategorias } from "@/lib/manchete";

type Props = {
  /** "desc" (padrão) = categorias que mais crescem; "asc" = maiores
   * retrações (checkpoint 11b). */
  ordem?: "desc" | "asc";
  onSelecionarCategoria: (categoriaId: string) => void;
};

type Estado =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; itens: RankingCategoriaItem[]; abaixoDoPisoVolume: number };

const LIMITE_RANKING = 20;

// Mesmo padrão visual de RankingList, mas por categoria em vez de bairro -
// cidade inteira (checkpoint 11b: "categorias em alta/em queda" no Radar).
// Clicar numa categoria aplica ela como filtro no resto do Radar (mesmo
// combobox de categoria do cabeçalho), não abre um painel novo.
export function CategoryRankingList({ ordem = "desc", onSelecionarCategoria }: Props) {
  const [estado, setEstado] = useState<Estado>({ status: "carregando" });

  useEffect(() => {
    let cancelado = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- indicador de carregando pro refetch ao trocar ordem, não há como derivar isso do render.
    setEstado({ status: "carregando" });
    getRankingCategorias({ limite: LIMITE_RANKING, ordem })
      .then((ranking) => {
        if (!cancelado) {
          setEstado({
            status: "pronto",
            itens: ranking.itens,
            abaixoDoPisoVolume: ranking.abaixoDoPisoVolume,
          });
        }
      })
      .catch((erro: unknown) => {
        if (!cancelado) {
          setEstado({
            status: "erro",
            mensagem: erro instanceof Error ? erro.message : "Erro desconhecido",
          });
        }
      });
    return () => {
      cancelado = true;
    };
  }, [ordem]);

  if (estado.status === "carregando") {
    return (
      <div className="space-y-3" role="status" aria-label="Carregando">
        <Skeleton className="h-9 w-3/4" />
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (estado.status === "erro") {
    return (
      <Alert variant="destructive">
        <AlertTitle>Não foi possível carregar o ranking de categorias</AlertTitle>
        <AlertDescription>{estado.mensagem}</AlertDescription>
      </Alert>
    );
  }

  if (estado.itens.length === 0) {
    return (
      <Alert>
        <AlertTitle>Nenhuma categoria elegível</AlertTitle>
        <AlertDescription>
          {estado.abaixoDoPisoVolume > 0
            ? `${estado.abaixoDoPisoVolume} categoria${estado.abaixoDoPisoVolume > 1 ? "s tiveram" : " teve"} crescimento calculável nesse período, mas com volume baixo demais (abaixo do piso mínimo) pra competir no ranking principal.`
            : `Não há histórico suficiente pra calcular ${ordem === "asc" ? "retração" : "crescimento"} por categoria ainda.`}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-3">
      <Headline size="md">{mancheteRankingCategorias(estado.itens, ordem)}</Headline>
      <div className="overflow-y-auto rounded-md border">
        <p className="flex items-center gap-1 border-b bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
          categorias ordenadas por {ordem === "asc" ? "retração" : "crescimento"} de aberturas
          frente ao baseline dos últimos 24 meses — {estado.itens[0].total} elegíveis
          {estado.abaixoDoPisoVolume > 0 &&
            ` · ${estado.abaixoDoPisoVolume} abaixo do piso mínimo de volume, não exibidas`}
          <MethodologyTooltip
            titulo="variação %"
            formula="(valor atual - baseline) / baseline, onde baseline é a média móvel dos 24 meses anteriores."
            ancora="baseline"
          />
        </p>
        <ol className="divide-y">
          {estado.itens.map((item) => (
            <li key={item.categoriaId}>
              <button
                type="button"
                onClick={() => onSelecionarCategoria(item.categoriaId)}
                className="flex w-full items-center gap-4 px-4 py-2.5 text-left transition-colors hover:bg-muted/50"
              >
                <span
                  className="w-7 shrink-0 text-xs text-muted-foreground"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  #{item.posicao}
                </span>
                <span className="flex-1 truncate text-sm font-medium">{item.nome}</span>
                <span className="flex items-baseline gap-3">
                  <span className="text-base font-semibold">
                    {formatarValorCompacto(item.valorAtual)}
                  </span>
                  <span
                    className="w-14 shrink-0 text-right text-sm font-medium"
                    style={{ color: corDelta(item.variacaoPct, true) }}
                  >
                    {formatarDeltaPct(item.variacaoPct)}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
