"use client";

import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getCategorias,
  getMetricasComercio,
  getTerritorios,
  type Categoria,
  type GeoJsonFeatureCollection,
  type MetricaComercio,
} from "@/lib/api";

type Estado =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | {
      status: "pronto";
      territorios: GeoJsonFeatureCollection;
      categorias: Categoria[];
      metricas: MetricaComercio[];
    };

const PRESETS_PERIODO = [
  { value: "1", label: "Mês atual" },
  { value: "3", label: "Últimos 3 meses" },
  { value: "6", label: "Últimos 6 meses" },
  { value: "12", label: "Últimos 12 meses" },
];

export function Dashboard() {
  const [estado, setEstado] = useState<Estado>({ status: "carregando" });

  useEffect(() => {
    let cancelado = false;

    async function carregar() {
      setEstado({ status: "carregando" });
      try {
        const [territorios, categorias, metricas] = await Promise.all([
          getTerritorios(),
          getCategorias(),
          getMetricasComercio(),
        ]);
        if (!cancelado) {
          setEstado({ status: "pronto", territorios, categorias, metricas });
        }
      } catch (erro) {
        if (!cancelado) {
          setEstado({
            status: "erro",
            mensagem:
              erro instanceof Error
                ? erro.message
                : "Erro desconhecido ao conversar com a API",
          });
        }
      }
    }

    carregar();
    return () => {
      cancelado = true;
    };
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b px-6 py-4">
        <h1 className="text-lg font-semibold">Radar de Comércio — Curitiba</h1>
        <p className="text-sm text-muted-foreground">
          Abertura e fechamento de estabelecimentos por bairro e categoria
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3 border-b px-6 py-3">
        <Select disabled={estado.status !== "pronto"}>
          <SelectTrigger className="w-64">
            <SelectValue placeholder="Todas as categorias" />
          </SelectTrigger>
          <SelectContent>
            {estado.status === "pronto" &&
              estado.categorias.map((categoria) => (
                <SelectItem key={categoria.categoria_id} value={categoria.categoria_id}>
                  {categoria.nome}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>

        <Select defaultValue="12">
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

      <main className="flex-1 p-6">
        {estado.status === "carregando" && (
          <div className="space-y-3" role="status" aria-label="Carregando">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-96 w-full" />
          </div>
        )}

        {estado.status === "erro" && (
          <Alert variant="destructive">
            <AlertTitle>Não foi possível carregar os dados</AlertTitle>
            <AlertDescription>
              {estado.mensagem}. Confirme que a API está rodando (
              {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}) e tente
              novamente.
            </AlertDescription>
          </Alert>
        )}

        {estado.status === "pronto" && estado.territorios.features.length === 0 && (
          <Alert>
            <AlertTitle>Nenhum território encontrado</AlertTitle>
            <AlertDescription>
              A API respondeu, mas ainda não há bairros cadastrados.
            </AlertDescription>
          </Alert>
        )}

        {estado.status === "pronto" && estado.territorios.features.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Territórios</CardTitle>
              </CardHeader>
              <CardContent className="text-3xl font-semibold">
                {estado.territorios.features.length}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Categorias</CardTitle>
              </CardHeader>
              <CardContent className="text-3xl font-semibold">
                {estado.categorias.length}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Bairros com métrica agregada</CardTitle>
              </CardHeader>
              <CardContent className="text-3xl font-semibold">
                {estado.metricas.length}
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
