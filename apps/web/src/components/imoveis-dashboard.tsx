"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { DateRange } from "react-day-picker";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { ConstrucaoTab } from "@/components/construcao-tab";
import { ContextoTab } from "@/components/contexto-tab";
import { ImoveisDetailPanel } from "@/components/imoveis-detail-panel";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ValorReferenciaTab } from "@/components/valor-referencia-tab";
import { ZoneamentoTab } from "@/components/zoneamento-tab";
import {
  getConstrucao,
  getContextoImoveis,
  getTerritorios,
  getValorReferencia,
  getZoneamento,
  type ContextoImoveis,
  type GeoJsonFeatureCollection,
  type MetricaConstrucao,
  type ValorReferenciaBairro,
  type ZoneamentoFeatureCollection,
} from "@/lib/api";
import { intervaloUltimosMeses, PRESETS_PERIODO } from "@/lib/periodo";

type Aba = "construcao" | "valor" | "zoneamento" | "contexto";

const PERIODO_CUSTOM = "custom";

type EstadoBase =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | {
      status: "pronto";
      territorios: GeoJsonFeatureCollection;
      valorReferencia: ValorReferenciaBairro[];
      zoneamento: ZoneamentoFeatureCollection;
      contexto: ContextoImoveis;
    };

type EstadoConstrucao =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; linhas: MetricaConstrucao[] };

function formatarDataCurta(iso: string): string {
  const [ano, m, d] = iso.split("-");
  return `${d}/${m}/${ano.slice(2)}`;
}

// Painel principal do Radar Imobiliário (checkpoint 11f) - mesma forma do
// Dashboard de comércio (header + Tabs + filtros + mapa/painel + Sheet de
// detalhe), com quatro abas em vez de três: as quatro fontes reais do
// checkpoint 11c-11e (construção, valor de referência, zoneamento,
// contexto), nunca combinadas numa métrica composta.
export function ImoveisDashboard() {
  const [base, setBase] = useState<EstadoBase>({ status: "carregando" });
  const [construcao, setConstrucao] = useState<EstadoConstrucao>({ status: "carregando" });
  const [construcaoAtual, setConstrucaoAtual] = useState<MetricaConstrucao[]>([]);
  const [presetPeriodo, setPresetPeriodo] = useState<string>("12");
  const [intervaloCustom, setIntervaloCustom] = useState<DateRange | undefined>(undefined);
  const [popoverAberto, setPopoverAberto] = useState(false);
  const [selecionado, setSelecionado] = useState<{ id: string; nome: string } | null>(null);
  const [aba, setAba] = useState<Aba>("construcao");

  const { dataInicio, dataFim } = useMemo(() => {
    if (presetPeriodo === PERIODO_CUSTOM && intervaloCustom?.from && intervaloCustom.to) {
      return {
        dataInicio: intervaloCustom.from.toISOString().slice(0, 10),
        dataFim: intervaloCustom.to.toISOString().slice(0, 10),
      };
    }
    return intervaloUltimosMeses(Number(presetPeriodo) || 12);
  }, [presetPeriodo, intervaloCustom]);

  // Território, valor de referência (estático), zoneamento (estático) e
  // contexto (mês mais recente) não dependem do filtro de período - uma
  // única busca.
  useEffect(() => {
    let cancelado = false;
    Promise.all([getTerritorios(), getValorReferencia(), getZoneamento(), getContextoImoveis()])
      .then(([territorios, valorReferencia, zoneamento, contexto]) => {
        if (!cancelado) setBase({ status: "pronto", territorios, valorReferencia, zoneamento, contexto });
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

  // Construção (mapa agregado por bairro) refaz sempre que o período muda.
  useEffect(() => {
    let cancelado = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- indicador de "atualizando" pro refetch ao trocar período, não há como derivar isso do render.
    setConstrucao({ status: "carregando" });
    getConstrucao({ dataInicio, dataFim })
      .then((linhas) => {
        if (!cancelado) {
          setConstrucao({ status: "pronto", linhas });
          setConstrucaoAtual(linhas);
        }
      })
      .catch((erro: unknown) => {
        if (!cancelado) {
          setConstrucao({
            status: "erro",
            mensagem: erro instanceof Error ? erro.message : "Erro desconhecido",
          });
        }
      });
    return () => {
      cancelado = true;
    };
  }, [dataInicio, dataFim]);

  const nomesPorTerritorio = useMemo(() => {
    if (base.status !== "pronto") return new Map<string, string>();
    return new Map(base.territorios.features.map((f) => [f.properties.territorio_id, f.properties.nome]));
  }, [base]);

  function selecionarTerritorio(territorioId: string) {
    const nome = nomesPorTerritorio.get(territorioId);
    if (nome) setSelecionado({ id: territorioId, nome });
  }

  const construcaoDoSelecionado = selecionado
    ? construcaoAtual.find((l) => l.territorioId === selecionado.id)
    : undefined;
  const valorReferenciaDoSelecionado =
    selecionado && base.status === "pronto"
      ? base.valorReferencia.find((v) => v.territorioId === selecionado.id)
      : undefined;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-4">
        <div>
          <p className="text-xs font-semibold tracking-wider text-primary uppercase">Mercator</p>
          <h1 className="font-heading text-2xl leading-tight font-semibold">Radar Imobiliário</h1>
          <p className="text-sm text-muted-foreground">
            Curitiba — construção, valor de referência, zoneamento e contexto de mercado por
            bairro
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Tabs value={aba} onValueChange={(v) => v && setAba(v as Aba)}>
            <TabsList>
              <TabsTrigger value="construcao">Construção</TabsTrigger>
              <TabsTrigger value="valor">Valor de referência</TabsTrigger>
              <TabsTrigger value="zoneamento">Zoneamento</TabsTrigger>
              <TabsTrigger value="contexto">Contexto de mercado</TabsTrigger>
            </TabsList>
          </Tabs>
          <Link
            href="/radar"
            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            Radar de Comércio
          </Link>
          <Link
            href="/metodologia"
            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            Metodologia
          </Link>
        </div>
      </header>

      {aba === "construcao" && (
        <div className="flex flex-wrap items-center gap-3 border-b px-6 py-3">
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
              {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}) e tente novamente.
            </AlertDescription>
          </Alert>
        )}

        {base.status === "pronto" && aba === "construcao" && (
          <>
            {construcao.status === "erro" && (
              <Alert variant="destructive">
                <AlertTitle>Não foi possível carregar a construção</AlertTitle>
                <AlertDescription>{construcao.mensagem}</AlertDescription>
              </Alert>
            )}
            {construcao.status === "carregando" && construcaoAtual.length === 0 && (
              <Skeleton className="h-96 w-full" />
            )}
            {construcao.status === "pronto" && construcaoAtual.length === 0 && (
              <Alert>
                <AlertTitle>Nenhum alvará ou CVCO no período</AlertTitle>
                <AlertDescription>
                  Ajuste o período acima para ver bairros com construção registrada.
                </AlertDescription>
              </Alert>
            )}
            {construcao.status !== "erro" && construcaoAtual.length > 0 && (
              <ConstrucaoTab
                territorios={base.territorios}
                linhas={construcaoAtual}
                onSelecionarTerritorio={selecionarTerritorio}
              />
            )}
          </>
        )}

        {base.status === "pronto" && aba === "valor" && (
          <ValorReferenciaTab
            territorios={base.territorios}
            linhas={base.valorReferencia}
            onSelecionarTerritorio={selecionarTerritorio}
          />
        )}

        {base.status === "pronto" && aba === "zoneamento" && (
          <ZoneamentoTab zoneamento={base.zoneamento} />
        )}

        {base.status === "pronto" && aba === "contexto" && (
          <ContextoTab contexto={base.contexto} nomesPorTerritorio={nomesPorTerritorio} />
        )}
      </main>

      <ImoveisDetailPanel
        territorio={selecionado}
        construcaoAgregada={construcaoDoSelecionado}
        valorReferencia={valorReferenciaDoSelecionado}
        dataInicio={dataInicio}
        dataFim={dataFim}
        onOpenChange={(open) => {
          if (!open) setSelecionado(null);
        }}
      />
    </div>
  );
}
