"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AnunciosChoroplethTab } from "@/components/anuncios-choropleth-tab";
import { AnunciosDetailPanel } from "@/components/anuncios-detail-panel";
import { Headline } from "@/components/headline";
import { ProcedenciaAnunciosPanel } from "@/components/procedencia-anuncios-panel";
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
  getProcedenciaAnuncios,
  getTerritorios,
  getTermometroAnuncios,
  type GeoJsonFeatureCollection,
  type ProcedenciaFonte,
  type TermometroBairro,
} from "@/lib/api";
import { formatarValorCompacto } from "@/lib/indicadores";

const TODAS_TIPOLOGIAS = "todas";

// Mesmo catálogo fechado de domain.anuncio.models.TIPOLOGIAS_VALIDAS -
// sem endpoint dedicado pra isso ainda, lista pequena o suficiente pra
// não justificar um GET /anuncios/tipologias só pra isso.
const NOMES_TIPOLOGIA: Record<string, string> = {
  apartamento: "Apartamento",
  casa: "Casa",
  sobrado: "Sobrado",
  kitnet_studio: "Kitnet/Studio",
  cobertura: "Cobertura",
  terreno: "Terreno",
  sala_comercial: "Sala comercial",
  galpao: "Galpão",
  chacara_sitio: "Chácara/Sítio",
  nao_classificado: "Não classificado",
};

const OPERACOES = [
  { value: "aluguel", label: "Alugar" },
  { value: "venda", label: "Comprar" },
];

type Aba = "mapa" | "procedencia";

type EstadoTerritorios =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; territorios: GeoJsonFeatureCollection };

type EstadoTermometro =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; linhas: TermometroBairro[] };

type EstadoProcedencia =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "pronto"; fontes: ProcedenciaFonte[] };

// Painel principal do Radar de Anúncios (checkpoint 12i). Só três dos
// quatro controles da seção 10 (operação/tipo/bairro) - "período" fica de
// fora de propósito: o termômetro é um snapshot do estoque agora, não
// uma série filtrável por data ainda (mesma simplificação já adotada nas
// abas Valor de referência/Zoneamento do Radar Imobiliário, que também
// não têm filtro de período por não serem série temporal).
export function AnunciosDashboard() {
  const [territoriosEstado, setTerritoriosEstado] = useState<EstadoTerritorios>({
    status: "carregando",
  });
  const [operacao, setOperacao] = useState("aluguel");
  const [tipologia, setTipologia] = useState<string>(TODAS_TIPOLOGIAS);
  const [aba, setAba] = useState<Aba>("mapa");
  const [termometro, setTermometro] = useState<EstadoTermometro>({ status: "carregando" });
  const [procedencia, setProcedencia] = useState<EstadoProcedencia>({ status: "carregando" });
  const [selecionado, setSelecionado] = useState<{ id: string; nome: string } | null>(null);

  useEffect(() => {
    let cancelado = false;
    getTerritorios()
      .then((territorios) => {
        if (!cancelado) setTerritoriosEstado({ status: "pronto", territorios });
      })
      .catch((erro: unknown) => {
        if (!cancelado) {
          setTerritoriosEstado({
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
    let cancelado = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- indicador de carregamento pro refetch ao trocar operação/tipologia, não há como derivar isso do render.
    setTermometro({ status: "carregando" });
    getTermometroAnuncios(operacao, tipologia === TODAS_TIPOLOGIAS ? undefined : tipologia)
      .then((linhas) => {
        if (!cancelado) setTermometro({ status: "pronto", linhas });
      })
      .catch((erro: unknown) => {
        if (!cancelado) {
          setTermometro({
            status: "erro",
            mensagem: erro instanceof Error ? erro.message : "Erro desconhecido",
          });
        }
      });
    return () => {
      cancelado = true;
    };
  }, [operacao, tipologia]);

  useEffect(() => {
    let cancelado = false;
    getProcedenciaAnuncios()
      .then((fontes) => {
        if (!cancelado) setProcedencia({ status: "pronto", fontes });
      })
      .catch((erro: unknown) => {
        if (!cancelado) {
          setProcedencia({
            status: "erro",
            mensagem: erro instanceof Error ? erro.message : "Erro desconhecido",
          });
        }
      });
    return () => {
      cancelado = true;
    };
  }, []);

  const nomesPorTerritorio = useMemo(() => {
    if (territoriosEstado.status !== "pronto") return new Map<string, string>();
    return new Map(
      territoriosEstado.territorios.features.map((f) => [f.properties.territorio_id, f.properties.nome]),
    );
  }, [territoriosEstado]);

  function selecionarTerritorio(territorioId: string) {
    const nome = nomesPorTerritorio.get(territorioId);
    if (nome) setSelecionado({ id: territorioId, nome });
  }

  const operacaoLabel = OPERACOES.find((o) => o.value === operacao)?.label ?? operacao;

  const manchete = useMemo(() => {
    if (termometro.status !== "pronto") return null;
    const totalEstoque = termometro.linhas.reduce((soma, l) => soma + l.estoque, 0);
    const comAmostra = termometro.linhas.filter((l) => l.amostraPrecoSuficiente).length;
    if (totalEstoque === 0) {
      return `Nenhum anúncio ativo para ${operacaoLabel.toLowerCase()} com os filtros atuais.`;
    }
    return `${formatarValorCompacto(totalEstoque)} imóveis para ${operacaoLabel.toLowerCase()} anunciados agora em Curitiba, com preço mediano confiável em ${comAmostra} de ${termometro.linhas.length} bairros.`;
  }, [termometro, operacaoLabel]);

  return (
    <div className="flex h-screen flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-4">
        <div>
          <p className="text-xs font-semibold tracking-wider text-primary uppercase">Mercator</p>
          <h1 className="font-heading text-2xl leading-tight font-semibold">Radar de Anúncios</h1>
          <p className="text-sm text-muted-foreground">
            Curitiba — oferta e preço pedido de imóveis anunciados, por bairro (Apolar + Chaves na
            Mão)
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Tabs value={aba} onValueChange={(v) => v && setAba(v as Aba)}>
            <TabsList>
              <TabsTrigger value="mapa">Mapa</TabsTrigger>
              <TabsTrigger value="procedencia">Procedência</TabsTrigger>
            </TabsList>
          </Tabs>
          <Link
            href="/imoveis"
            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            Radar Imobiliário
          </Link>
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

      {aba === "mapa" && (
        <div className="flex flex-wrap items-center gap-3 border-b px-6 py-3">
          <Select value={operacao} onValueChange={(v) => v && setOperacao(v)}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Operação" />
            </SelectTrigger>
            <SelectContent>
              {OPERACOES.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={tipologia} onValueChange={(v) => v && setTipologia(v)}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Tipo de imóvel" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TODAS_TIPOLOGIAS}>Todos os tipos</SelectItem>
              {Object.entries(NOMES_TIPOLOGIA).map(([id, nome]) => (
                <SelectItem key={id} value={id}>
                  {nome}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value=""
            onValueChange={(v) => {
              if (v) selecionarTerritorio(v);
            }}
          >
            <SelectTrigger className="w-52">
              <SelectValue placeholder="Ir para um bairro…" />
            </SelectTrigger>
            <SelectContent>
              {Array.from(nomesPorTerritorio.entries())
                .sort((a, b) => a[1].localeCompare(b[1]))
                .map(([id, nome]) => (
                  <SelectItem key={id} value={id}>
                    {nome}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <main className="flex flex-1 flex-col gap-3 p-6">
        {manchete && <Headline>{manchete}</Headline>}

        {territoriosEstado.status === "carregando" && (
          <div className="space-y-3" role="status" aria-label="Carregando">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-96 w-full" />
          </div>
        )}

        {territoriosEstado.status === "erro" && (
          <Alert variant="destructive">
            <AlertTitle>Não foi possível carregar os dados</AlertTitle>
            <AlertDescription>
              {territoriosEstado.mensagem}. Confirme que a API está rodando (
              {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}) e tente novamente.
            </AlertDescription>
          </Alert>
        )}

        {territoriosEstado.status === "pronto" && aba === "mapa" && (
          <>
            {termometro.status === "erro" && (
              <Alert variant="destructive">
                <AlertTitle>Não foi possível carregar o termômetro</AlertTitle>
                <AlertDescription>{termometro.mensagem}</AlertDescription>
              </Alert>
            )}
            {termometro.status === "carregando" && <Skeleton className="h-96 w-full flex-1" />}
            {termometro.status === "pronto" && (
              <AnunciosChoroplethTab
                territorios={territoriosEstado.territorios}
                linhas={termometro.linhas}
                operacaoLabel={operacaoLabel}
                onSelecionarTerritorio={selecionarTerritorio}
              />
            )}
          </>
        )}

        {territoriosEstado.status === "pronto" && aba === "procedencia" && (
          <>
            {procedencia.status === "erro" && (
              <Alert variant="destructive">
                <AlertTitle>Não foi possível carregar a procedência</AlertTitle>
                <AlertDescription>{procedencia.mensagem}</AlertDescription>
              </Alert>
            )}
            {procedencia.status === "carregando" && <Skeleton className="h-64 w-full" />}
            {procedencia.status === "pronto" && (
              <ProcedenciaAnunciosPanel fontes={procedencia.fontes} />
            )}
          </>
        )}
      </main>

      <AnunciosDetailPanel
        territorio={selecionado}
        operacao={operacao}
        operacaoLabel={operacaoLabel}
        tipologia={tipologia === TODAS_TIPOLOGIAS ? undefined : tipologia}
        onOpenChange={(open) => {
          if (!open) setSelecionado(null);
        }}
      />
    </div>
  );
}
