"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { DateRange } from "react-day-picker";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { ChoroplethMap } from "@/components/choropleth-map";
import { DetailPanel } from "@/components/detail-panel";
import { Headline } from "@/components/headline";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { RadarRankingPanel } from "@/components/radar-ranking-panel";
import { RadiusSearchPanel } from "@/components/radius-search-panel";
import { SaldoLegend } from "@/components/saldo-legend";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  getCategorias,
  getCoberturaTemporal,
  getMetricasComercio,
  getTerritorios,
  type Categoria,
  type CoberturaTemporal,
  type GeoJsonFeatureCollection,
  type MetricaComercio,
} from "@/lib/api";
import { mancheteMapa } from "@/lib/manchete";
import { formatarMesAno, intervaloUltimosMeses, PRESETS_PERIODO } from "@/lib/periodo";

type Aba = "mapa" | "ranking" | "busca-raio";

const TODAS_CATEGORIAS = "todas";
const PERIODO_CUSTOM = "custom";

type EstadoBase =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | {
      status: "pronto";
      territorios: GeoJsonFeatureCollection;
      categorias: Categoria[];
      cobertura: CoberturaTemporal;
    };

type EstadoMetricas =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; metricas: MetricaComercio[] };

function formatarDataCurta(iso: string): string {
  const [ano, m, d] = iso.split("-");
  return `${d}/${m}/${ano.slice(2)}`;
}

// A cobertura real do dado é sempre um fato distinto do preset de período
// escolhido no filtro - "últimos 12 meses" é sempre um range válido de
// filtro, exista ou não 12 meses de evento real dentro dele. Ver achado da
// auditoria de 2026-08-12.
function textoCobertura(cobertura: CoberturaTemporal): string {
  if (!cobertura.mesInicio || !cobertura.mesFim) {
    return "nenhum evento processado ainda";
  }
  if (cobertura.mesInicio === cobertura.mesFim) {
    return formatarMesAno(cobertura.mesInicio);
  }
  return `${formatarMesAno(cobertura.mesInicio)} – ${formatarMesAno(cobertura.mesFim)}`;
}

export function Dashboard() {
  const [base, setBase] = useState<EstadoBase>({ status: "carregando" });
  const [metricas, setMetricas] = useState<EstadoMetricas>({ status: "carregando" });
  // Última resposta de /metricas/comercio que teve sucesso, separada do
  // status de carregando/erro acima - o mapa e a legenda lêem daqui, não de
  // `metricas`, para não zerar todo bairro pro cinza neutro a cada troca de
  // filtro só porque a resposta nova ainda não chegou (era exatamente isso
  // que dava a impressão de "mapa perde os indicadores" reportada pelo
  // dono - ContagemEventos real ficava momentaneamente substituída por um
  // array vazio até o fetch da nova categoria/período resolver).
  const [metricasAtuais, setMetricasAtuais] = useState<MetricaComercio[]>([]);
  const [categoriaId, setCategoriaId] = useState<string>(TODAS_CATEGORIAS);
  const [presetPeriodo, setPresetPeriodo] = useState<string>("12");
  const [intervaloCustom, setIntervaloCustom] = useState<DateRange | undefined>(undefined);
  const [popoverAberto, setPopoverAberto] = useState(false);
  const [selecionado, setSelecionado] = useState<{ id: string; nome: string } | null>(null);
  const [aba, setAba] = useState<Aba>("mapa");

  const { dataInicio, dataFim } = useMemo(() => {
    if (presetPeriodo === PERIODO_CUSTOM && intervaloCustom?.from && intervaloCustom.to) {
      return {
        dataInicio: intervaloCustom.from.toISOString().slice(0, 10),
        dataFim: intervaloCustom.to.toISOString().slice(0, 10),
      };
    }
    return intervaloUltimosMeses(Number(presetPeriodo) || 12);
  }, [presetPeriodo, intervaloCustom]);

  const categoriaFiltro = categoriaId === TODAS_CATEGORIAS ? undefined : categoriaId;

  // Carrega território + categoria uma única vez - geometria e taxonomia não
  // dependem dos filtros.
  useEffect(() => {
    let cancelado = false;
    Promise.all([getTerritorios(), getCategorias(), getCoberturaTemporal()])
      .then(([territorios, categorias, cobertura]) => {
        if (!cancelado) setBase({ status: "pronto", territorios, categorias, cobertura });
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

  // Métrica agregada por bairro (mapa) - refaz sempre que categoria ou
  // período mudam, sem tocar em território/categoria.
  useEffect(() => {
    let cancelado = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- indicador de "atualizando" pro refetch ao trocar filtro, não há como derivar isso do render.
    setMetricas({ status: "carregando" });
    getMetricasComercio({ categoriaId: categoriaFiltro, dataInicio, dataFim })
      .then((linhas) => {
        if (!cancelado) {
          setMetricas({ status: "pronto", metricas: linhas });
          setMetricasAtuais(linhas);
        }
      })
      .catch((erro: unknown) => {
        if (!cancelado) {
          setMetricas({
            status: "erro",
            mensagem: erro instanceof Error ? erro.message : "Erro desconhecido",
          });
        }
      });
    return () => {
      cancelado = true;
    };
  }, [categoriaFiltro, dataInicio, dataFim]);

  function selecionarTerritorio(territorioId: string) {
    if (base.status !== "pronto") return;
    const feature = base.territorios.features.find(
      (f) => f.properties.territorio_id === territorioId,
    );
    if (feature) {
      setSelecionado({ id: territorioId, nome: feature.properties.nome });
    }
  }

  const nomesPorTerritorio = useMemo(() => {
    if (base.status !== "pronto") return new Map<string, string>();
    return new Map(base.territorios.features.map((f) => [f.properties.territorio_id, f.properties.nome]));
  }, [base]);

  const nomesPorCategoria = useMemo(() => {
    const mapa = new Map<string, string>([[TODAS_CATEGORIAS, "Todas as categorias"]]);
    if (base.status === "pronto") {
      for (const categoria of base.categorias) mapa.set(categoria.categoria_id, categoria.nome);
    }
    return mapa;
  }, [base]);

  // Clique numa linha do ranking já vem com o nome (a API devolve) - não
  // precisa procurar no GeoJSON como o clique no mapa. Os dois caminhos
  // levam ao mesmo DetailPanel, só a origem do nome muda.
  function selecionarTerritorioComNome(territorioId: string, nome: string) {
    setSelecionado({ id: territorioId, nome });
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-4">
        <div>
          <p className="text-xs font-semibold tracking-wider text-primary uppercase">Mercator</p>
          <h1 className="font-heading text-2xl leading-tight font-semibold">Radar de Comércio</h1>
          <p className="text-sm text-muted-foreground">
            Curitiba — abertura e fechamento de estabelecimentos por bairro e categoria
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Tabs
            value={aba}
            onValueChange={(valor) => {
              if (valor) setAba(valor as Aba);
            }}
          >
            <TabsList>
              <TabsTrigger value="mapa">Mapa</TabsTrigger>
              <TabsTrigger value="ranking">Ranking de crescimento</TabsTrigger>
              <TabsTrigger value="busca-raio">Busca por raio</TabsTrigger>
            </TabsList>
          </Tabs>
          <Link
            href="/comparacao"
            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            Comparar bairros
          </Link>
          <Link
            href="/imoveis"
            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            Radar Imobiliário
          </Link>
          <Link
            href="/anuncios"
            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            Radar de Anúncios
          </Link>
          <Link
            href="/metodologia"
            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
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
            {/* Checkpoint 10d: o campo fechado mostrava o categoria_id cru
              (ex.: "imobiliario") em vez do nome formatado que a lista
              aberta já usa - Select.Value do Base UI exibe o value literal
              por padrão, a menos que receba a função de formatação. */}
            <SelectValue placeholder="Todas as categorias">
              {(valor: string | null) => (valor ? (nomesPorCategoria.get(valor) ?? valor) : "Todas as categorias")}
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

        {aba === "mapa" && (
          <>
            <Select
              value={presetPeriodo}
              onValueChange={(valor) => {
                if (!valor) return;
                setPresetPeriodo(valor);
                if (valor === PERIODO_CUSTOM) setPopoverAberto(true);
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
                <SelectItem value={PERIODO_CUSTOM}>Personalizado…</SelectItem>
              </SelectContent>
            </Select>

            {presetPeriodo === PERIODO_CUSTOM && (
              <Popover open={popoverAberto} onOpenChange={setPopoverAberto}>
                <PopoverTrigger className={buttonVariants({ variant: "outline", size: "sm" })}>
                  {intervaloCustom?.from && intervaloCustom.to
                    ? `${formatarDataCurta(dataInicio)} – ${formatarDataCurta(dataFim)}`
                    : "Escolher intervalo"}
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    mode="range"
                    selected={intervaloCustom}
                    onSelect={(range) => {
                      setIntervaloCustom(range);
                      if (range?.from && range?.to) setPopoverAberto(false);
                    }}
                    numberOfMonths={2}
                  />
                </PopoverContent>
              </Popover>
            )}

            <span className="ml-auto text-xs text-muted-foreground">
              {formatarDataCurta(dataInicio)} – {formatarDataCurta(dataFim)}
            </span>
          </>
        )}
      </div>

      {aba === "mapa" && base.status === "pronto" && (
        <div className="border-b px-6 py-1.5 text-xs text-muted-foreground">
          Dados reais processados: {textoCobertura(base.cobertura)} — o período acima é
          só o filtro, pode não ter evento em todo o intervalo.
        </div>
      )}

      <main className="flex flex-1 flex-col p-6">
        {base.status === "carregando" && (
          <div className="space-y-3" role="status" aria-label="Carregando">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-96 w-full" />
          </div>
        )}

        {base.status === "erro" && (
          <Alert variant="destructive">
            <AlertTitle>Não foi possível carregar os dados</AlertTitle>
            <AlertDescription>
              {base.mensagem}. Confirme que a API está rodando (
              {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}) e tente
              novamente.
            </AlertDescription>
          </Alert>
        )}

        {base.status === "pronto" && aba === "mapa" && base.territorios.features.length === 0 && (
          <Alert>
            <AlertTitle>Nenhum território encontrado</AlertTitle>
            <AlertDescription>
              A API respondeu, mas ainda não há bairros cadastrados.
            </AlertDescription>
          </Alert>
        )}

        {base.status === "pronto" && aba === "mapa" && base.territorios.features.length > 0 && (
          <div className="flex flex-1 flex-col gap-3">
            {metricas.status === "carregando" && metricasAtuais.length === 0 ? (
              <Skeleton className="h-9 w-3/4" />
            ) : (
              metricas.status !== "erro" && (
                <Headline>{mancheteMapa(metricasAtuais, nomesPorTerritorio)}</Headline>
              )
            )}

            {metricas.status === "erro" && (
              <Alert variant="destructive">
                <AlertTitle>Não foi possível carregar a métrica</AlertTitle>
                <AlertDescription>{metricas.mensagem}</AlertDescription>
              </Alert>
            )}

            {metricas.status !== "erro" && (
              <>
                <div className="flex items-center gap-3">
                  <SaldoLegend
                    minSaldo={Math.min(0, ...metricasAtuais.map((m) => m.saldo))}
                    maxSaldo={Math.max(0, ...metricasAtuais.map((m) => m.saldo))}
                  />
                  {metricas.status === "carregando" && (
                    <span className="text-xs text-muted-foreground">atualizando…</span>
                  )}
                </div>
                <div className="min-h-[520px] flex-1 overflow-hidden rounded-md border">
                  <ChoroplethMap
                    territorios={base.territorios}
                    metricas={metricasAtuais}
                    onSelecionarTerritorio={selecionarTerritorio}
                  />
                </div>
              </>
            )}
          </div>
        )}

        {base.status === "pronto" && aba === "ranking" && (
          <RadarRankingPanel
            categoriaId={categoriaFiltro}
            onSelecionarTerritorio={selecionarTerritorioComNome}
            onSelecionarCategoria={(catId) => setCategoriaId(catId)}
          />
        )}

        {base.status === "pronto" && aba === "busca-raio" && (
          <RadiusSearchPanel
            categoriaId={categoriaFiltro}
            nomeCategoria={base.categorias.find((c) => c.categoria_id === categoriaFiltro)?.nome}
            categorias={base.categorias}
          />
        )}
      </main>

      <DetailPanel
        territorio={selecionado}
        categoriaId={categoriaFiltro}
        dataInicio={dataInicio}
        dataFim={dataFim}
        onOpenChange={(open) => {
          if (!open) setSelecionado(null);
        }}
      />
    </div>
  );
}
