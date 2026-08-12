"use client";

import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Sparkline } from "@/components/sparkline";
import { getRanking, type RankingItem } from "@/lib/api";
import { corDelta, formatarDeltaPct, formatarValorCompacto } from "@/lib/indicadores";

type Props = {
  categoriaId?: string;
  onSelecionarTerritorio: (territorioId: string, nome: string) => void;
};

type Estado =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; itens: RankingItem[] };

const LIMITE_RANKING = 20;

// A lista de ranking é, além de porta de entrada alternativa ao mapa, a
// "visão em tabela" acessível que todo painel de dado precisa - por isso
// vive como uma lista clicável simples (ol/li/button), não um canvas.
export function RankingList({ categoriaId, onSelecionarTerritorio }: Props) {
  const [estado, setEstado] = useState<Estado>({ status: "carregando" });

  useEffect(() => {
    let cancelado = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- indicador de carregando pro refetch ao trocar categoria, não há como derivar isso do render.
    setEstado({ status: "carregando" });
    getRanking({ categoriaId, limite: LIMITE_RANKING })
      .then((itens) => {
        if (!cancelado) setEstado({ status: "pronto", itens });
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
  }, [categoriaId]);

  if (estado.status === "carregando") {
    return (
      <div className="space-y-2" role="status" aria-label="Carregando">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    );
  }

  if (estado.status === "erro") {
    return (
      <Alert variant="destructive">
        <AlertTitle>Não foi possível carregar o ranking</AlertTitle>
        <AlertDescription>{estado.mensagem}</AlertDescription>
      </Alert>
    );
  }

  if (estado.itens.length === 0) {
    return (
      <Alert>
        <AlertTitle>Nenhum bairro elegível</AlertTitle>
        <AlertDescription>
          Não há histórico suficiente pra calcular crescimento nesse filtro ainda.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto rounded-md border">
      <p className="border-b bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
        bairros ordenados por crescimento de aberturas frente ao baseline dos últimos 24
        meses — {estado.itens[0].total} elegíveis
      </p>
      <ol className="divide-y">
        {estado.itens.map((item) => (
          <li key={item.territorioId}>
            <button
              type="button"
              onClick={() => onSelecionarTerritorio(item.territorioId, item.nome)}
              className="flex w-full items-center gap-4 px-4 py-3 text-left transition-colors hover:bg-muted/50"
            >
              <span
                className="w-7 shrink-0 text-xs text-muted-foreground"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                #{item.posicao}
              </span>
              <span className="w-40 shrink-0 truncate text-sm font-medium">{item.nome}</span>
              <Sparkline
                pontos={item.serie}
                corDestaque={corDelta(item.variacaoPct, true)}
                className="h-7 w-24 shrink-0"
              />
              <span className="ml-auto flex items-baseline gap-3">
                <span className="text-lg font-semibold">
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
  );
}
