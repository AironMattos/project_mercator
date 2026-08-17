"use client";

import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { getResumoBairroAnuncio, type ResumoBairroAnuncio } from "@/lib/api";
import { formatarValorCompacto, motivoIndisponivelLegivel } from "@/lib/indicadores";

type TerritorioSelecionado = { id: string; nome: string };

type AnunciosDetailPanelProps = {
  territorio: TerritorioSelecionado | null;
  operacao: string;
  operacaoLabel: string;
  tipologia?: string;
  onOpenChange: (open: boolean) => void;
};

type Estado =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; resumo: ResumoBairroAnuncio };

function formatarReais(valor: number): string {
  return `R$ ${new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(valor)}`;
}

// Uma métrica indisponível vira uma linha discreta com o motivo, nunca um
// FatoTile de peso visual cheio (correção #1 da seção 10 do prompt de
// referência: "o tile... exibindo 'dado em construção' com peso visual de
// tile preenchido precisa sumir enquanto não houver dado" - aplicado aqui
// desde o início, não como correção depois).
function LinhaIndisponivel({ rotulo, motivo }: { rotulo: string; motivo: string }) {
  return (
    <p className="text-xs text-muted-foreground">
      {rotulo}: <span className="italic">{motivoIndisponivelLegivel(motivo)}</span>
    </p>
  );
}

// Painel de bairro do Radar de Anúncios (checkpoint 12i) - ordem exigida
// pela seção 10: preço mediano (P25-P75) → variação 12m → estoque e
// variação → permanência mediana → quadrante → leitura cruzada → e só
// então, embaixo, contexto de construção/valor venal (Radar Imobiliário).
export function AnunciosDetailPanel({
  territorio,
  operacao,
  operacaoLabel,
  tipologia,
  onOpenChange,
}: AnunciosDetailPanelProps) {
  const [estado, setEstado] = useState<Estado>({ status: "carregando" });

  useEffect(() => {
    if (!territorio) return;
    let cancelado = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- indicador de carregamento pro fetch do resumo ao trocar bairro/filtro, não há como derivar isso do render.
    setEstado({ status: "carregando" });

    getResumoBairroAnuncio(territorio.id, operacao, tipologia)
      .then((resumo) => {
        if (!cancelado) setEstado({ status: "pronto", resumo });
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
  }, [territorio, operacao, tipologia]);

  return (
    <Sheet open={territorio !== null} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{territorio?.nome ?? ""}</SheetTitle>
          <Headline size="md" className="pt-1">
            Oferta de imóveis para {operacaoLabel}
          </Headline>
          <SheetDescription>estoque anunciado hoje, deduplicado entre fontes</SheetDescription>
        </SheetHeader>

        <div className="space-y-4 px-4 pb-4">
          {estado.status === "carregando" && <Skeleton className="h-64 w-full" />}
          {estado.status === "erro" && (
            <Alert variant="destructive">
              <AlertTitle>Não foi possível carregar o resumo</AlertTitle>
              <AlertDescription>{estado.mensagem}</AlertDescription>
            </Alert>
          )}

          {estado.status === "pronto" && (
            <>
              <div className="flex flex-wrap gap-3">
                <FatoTile
                  rotulo="preço mediano"
                  valor={
                    estado.resumo.precoMediano !== null
                      ? formatarReais(estado.resumo.precoMediano)
                      : `${estado.resumo.estoque} anúncio(s) — amostra insuficiente`
                  }
                  metodologia={{
                    formula:
                      "Mediana do preço pedido dos anúncios ativos do bairro, deduplicados entre fontes (imóvel resolvido). Exige ao menos 30 anúncios.",
                    ancora: "anuncios-preco-pedido",
                  }}
                />
                <FatoTile
                  rotulo="estoque anunciado"
                  valor={formatarValorCompacto(estado.resumo.estoque)}
                  metodologia={{
                    formula: "Anúncios ativos (sem ANUNCIO_ENCERRADO) no bairro, agora.",
                    ancora: "anuncios-estoque",
                  }}
                />
              </div>
              {estado.resumo.precoMediano !== null && (
                <p className="text-xs text-muted-foreground">
                  faixa P25–P75: {formatarReais(estado.resumo.precoP25 ?? 0)} –{" "}
                  {formatarReais(estado.resumo.precoP75 ?? 0)}
                </p>
              )}

              <div className="space-y-1">
                <LinhaIndisponivel
                  rotulo="variação contra 12 meses"
                  motivo={estado.resumo.motivoIndisponivelVariacao}
                />
                <LinhaIndisponivel
                  rotulo="variação do estoque"
                  motivo={estado.resumo.motivoIndisponivelEstoqueVariacao}
                />
                <LinhaIndisponivel
                  rotulo="permanência mediana"
                  motivo={estado.resumo.motivoIndisponivelPermanencia}
                />
                <LinhaIndisponivel
                  rotulo="quadrante de aquecimento"
                  motivo={estado.resumo.motivoIndisponivelQuadrante}
                />
                <LinhaIndisponivel
                  rotulo="leitura cruzada com comércio"
                  motivo={estado.resumo.motivoIndisponivelLeituraCruzada}
                />
              </div>

              <div className="border-t pt-3">
                <p className="mb-2 text-xs font-medium text-muted-foreground uppercase">
                  contexto (Radar Imobiliário)
                </p>
                <div className="flex flex-wrap gap-3">
                  <FatoTile
                    rotulo="alvarás aprovados (12m)"
                    valor={
                      estado.resumo.construcaoAlvarasAprovados !== null
                        ? formatarValorCompacto(estado.resumo.construcaoAlvarasAprovados)
                        : "sem registro"
                    }
                  />
                  <FatoTile
                    rotulo="CVCOs concluídos (12m)"
                    valor={
                      estado.resumo.construcaoCvcosConcluidos !== null
                        ? formatarValorCompacto(estado.resumo.construcaoCvcosConcluidos)
                        : "sem registro"
                    }
                  />
                  <FatoTile
                    rotulo="valor venal mediano (PGV)"
                    valor={
                      estado.resumo.valorVenalM2Mediano !== null
                        ? `${formatarReais(estado.resumo.valorVenalM2Mediano)}/m² — referência para IPTU, não é preço de mercado`
                        : "sem registro de PGV nesse bairro"
                    }
                  />
                </div>
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
