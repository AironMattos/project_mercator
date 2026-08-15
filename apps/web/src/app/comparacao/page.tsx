"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ComparisonTable } from "@/components/comparison-table";
import { Headline } from "@/components/headline";
import { QuebraCategoriaBars } from "@/components/quebra-categoria";
import { SerieTemporalChart } from "@/components/serie-temporal-chart";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { TerritorioMultiSelect } from "@/components/territorio-multi-select";
import {
  getCategorias,
  getComparacao,
  getTerritorios,
  type BairroResumo,
  type Categoria,
  type GeoJsonFeatureCollection,
} from "@/lib/api";
import { PRESETS_PERIODO, intervaloUltimosMeses } from "@/lib/periodo";

const TODAS_CATEGORIAS = "todas";
const MAX_BAIRROS = 4;
const MIN_BAIRROS = 2;

type EstadoBase =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; territorios: GeoJsonFeatureCollection; categorias: Categoria[] };

type EstadoComparacao =
  | { status: "ocioso" }
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; itens: BairroResumo[] };

// Experiência "COMPARAÇÃO" do prompt de referência (checkpoint 11c) - sem
// lógica de negócio nova: cada item vem exatamente de GET /bairros/{id}/resumo
// (via GET /bairros/comparar, que só chama a mesma função N vezes no
// backend), lado a lado. Nunca uma nota agregada decidindo qual bairro é
// melhor.
export default function ComparacaoPage() {
  const [base, setBase] = useState<EstadoBase>({ status: "carregando" });
  const [selecionados, setSelecionados] = useState<string[]>([]);
  const [categoriaId, setCategoriaId] = useState<string>(TODAS_CATEGORIAS);
  const [presetPeriodo, setPresetPeriodo] = useState<string>("12");
  const [comparacao, setComparacao] = useState<EstadoComparacao>({ status: "ocioso" });

  const categoriaFiltro = categoriaId === TODAS_CATEGORIAS ? undefined : categoriaId;
  const { dataInicio, dataFim } = useMemo(
    () => intervaloUltimosMeses(Number(presetPeriodo) || 12),
    [presetPeriodo],
  );

  useEffect(() => {
    let cancelado = false;
    Promise.all([getTerritorios(), getCategorias()])
      .then(([territorios, categorias]) => {
        if (!cancelado) setBase({ status: "pronto", territorios, categorias });
      })
      .catch((erro: unknown) => {
        if (!cancelado) {
          setBase({
            status: "erro",
            mensagem: erro instanceof Error ? erro.message : "Erro desconhecido",
          });
        }
      });
    return () => {
      cancelado = true;
    };
  }, []);

  useEffect(() => {
    if (selecionados.length < MIN_BAIRROS) return;
    let cancelado = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- indicador de carregando pro refetch ao trocar seleção/filtro, não há como derivar isso do render.
    setComparacao({ status: "carregando" });
    getComparacao(selecionados, { categoriaId: categoriaFiltro, dataInicio, dataFim })
      .then((itens) => {
        if (!cancelado) setComparacao({ status: "pronto", itens });
      })
      .catch((erro: unknown) => {
        if (!cancelado) {
          setComparacao({
            status: "erro",
            mensagem: erro instanceof Error ? erro.message : "Erro desconhecido",
          });
        }
      });
    return () => {
      cancelado = true;
    };
  }, [selecionados, categoriaFiltro, dataInicio, dataFim]);

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-4">
        <div>
          <p className="text-xs font-semibold tracking-wider text-primary uppercase">Mercator</p>
          <h1 className="font-heading text-2xl leading-tight font-semibold">Comparação de territórios</h1>
          <p className="text-sm text-muted-foreground">
            Selecione de {MIN_BAIRROS} a {MAX_BAIRROS} bairros para comparar lado a lado
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/radar" className="text-sm text-muted-foreground underline underline-offset-2">
            Voltar ao Radar
          </Link>
          <Link href="/imoveis" className="text-sm text-muted-foreground underline underline-offset-2">
            Radar Imobiliário
          </Link>
          <Link href="/metodologia" className="text-sm text-muted-foreground underline underline-offset-2">
            Metodologia
          </Link>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-3 border-b px-6 py-3">
        <Select
          value={categoriaId}
          onValueChange={(valor) => {
            if (valor) setCategoriaId(valor);
          }}
          disabled={base.status !== "pronto"}
        >
          <SelectTrigger className="w-64">
            <SelectValue placeholder="Todas as categorias">
              {(valor: string | null) =>
                !valor || valor === TODAS_CATEGORIAS
                  ? "Todas as categorias"
                  : ((base.status === "pronto"
                      ? base.categorias.find((c) => c.categoria_id === valor)?.nome
                      : valor) ?? valor)
              }
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={TODAS_CATEGORIAS}>Todas as categorias</SelectItem>
            {base.status === "pronto" &&
              base.categorias.map((categoria) => (
                <SelectItem key={categoria.categoria_id} value={categoria.categoria_id}>
                  {categoria.nome}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>

        <Select
          value={presetPeriodo}
          onValueChange={(valor) => {
            if (valor) setPresetPeriodo(valor);
          }}
        >
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Período" />
          </SelectTrigger>
          <SelectContent>
            {PRESETS_PERIODO.map((preset) => (
              <SelectItem key={preset.value} value={preset.value}>
                {preset.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <main className="flex flex-1 flex-col gap-4 p-6">
        {base.status === "carregando" && (
          <div className="space-y-3" role="status" aria-label="Carregando">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-24 w-full" />
          </div>
        )}

        {base.status === "erro" && (
          <Alert variant="destructive">
            <AlertTitle>Não foi possível carregar os bairros</AlertTitle>
            <AlertDescription>{base.mensagem}</AlertDescription>
          </Alert>
        )}

        {base.status === "pronto" && (
          <>
            <TerritorioMultiSelect
              territorios={base.territorios}
              selecionados={selecionados}
              onChange={setSelecionados}
              max={MAX_BAIRROS}
            />

            {selecionados.length < MIN_BAIRROS && (
              <Alert>
                <AlertTitle>Selecione ao menos {MIN_BAIRROS} bairros</AlertTitle>
                <AlertDescription>
                  Escolha entre {MIN_BAIRROS} e {MAX_BAIRROS} bairros acima para ver a comparação.
                </AlertDescription>
              </Alert>
            )}

            {selecionados.length >= MIN_BAIRROS && comparacao.status === "carregando" && (
              <div className="space-y-3" role="status" aria-label="Carregando comparação">
                <Skeleton className="h-9 w-3/4" />
                <Skeleton className="h-40 w-full" />
              </div>
            )}

            {selecionados.length >= MIN_BAIRROS && comparacao.status === "erro" && (
              <Alert variant="destructive">
                <AlertTitle>Não foi possível carregar a comparação</AlertTitle>
                <AlertDescription>{comparacao.mensagem}</AlertDescription>
              </Alert>
            )}

            {selecionados.length >= MIN_BAIRROS && comparacao.status === "pronto" && (
              <div className="flex flex-col gap-6">
                <Headline size="md">
                  Comparando {comparacao.itens.map((i) => i.nome).join(", ")}
                  {categoriaFiltro
                    ? ` — categoria ${base.categorias.find((c) => c.categoria_id === categoriaFiltro)?.nome ?? categoriaFiltro}`
                    : ""}
                  .
                </Headline>

                <ComparisonTable itens={comparacao.itens} />

                <div>
                  <p className="mb-2 text-xs text-muted-foreground">
                    evolução mensal — aberturas e desaparecimentos
                  </p>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {comparacao.itens.map((item) => {
                      const pontos = item.serieTemporal
                        .filter((l) => l.mes !== null)
                        .map((l) => ({
                          mes: l.mes as string,
                          aberturas: l.aberturas,
                          desaparecimentos: l.desaparecimentos,
                        }))
                        .sort((a, b) => a.mes.localeCompare(b.mes));
                      return (
                        <div key={item.territorioId} className="rounded-md border p-3">
                          <p className="text-sm font-medium">{item.nome}</p>
                          {pontos.length === 0 ? (
                            <p className="mt-2 text-xs text-muted-foreground">
                              sem eventos no período filtrado
                            </p>
                          ) : (
                            <SerieTemporalChart pontos={pontos} compacto />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <p className="mb-2 text-xs text-muted-foreground">
                    composição por categoria — top categorias em aberturas
                  </p>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {comparacao.itens.map((item) => (
                      <div key={item.territorioId} className="rounded-md border p-3">
                        <p className="mb-1.5 text-sm font-medium">{item.nome}</p>
                        <QuebraCategoriaBars itens={item.quebraCategoria} />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
