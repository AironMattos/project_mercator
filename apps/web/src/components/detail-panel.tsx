"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { getMetricasComercio } from "@/lib/api";

type TerritorioSelecionado = { id: string; nome: string };

type DetailPanelProps = {
  territorio: TerritorioSelecionado | null;
  categoriaId: string | undefined;
  dataInicio: string;
  dataFim: string;
  onOpenChange: (open: boolean) => void;
};

type PontoSerie = { mes: string; aberturas: number; desaparecimentos: number };

type Estado =
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "vazio" }
  | { status: "pronto"; pontos: PontoSerie[] };

const NOMES_MES = [
  "jan",
  "fev",
  "mar",
  "abr",
  "mai",
  "jun",
  "jul",
  "ago",
  "set",
  "out",
  "nov",
  "dez",
];

function formatarMes(mes: string): string {
  const [ano, m] = mes.split("-");
  const indice = Number(m) - 1;
  return `${NOMES_MES[indice] ?? m}/${ano.slice(2)}`;
}

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
    // eslint-disable-next-line react-hooks/set-state-in-effect -- indicador de carregamento pro fetch da série ao trocar de bairro/filtro, não há como derivar isso do render.
    setEstado({ status: "carregando" });

    getMetricasComercio({ territorioId: territorio.id, categoriaId, dataInicio, dataFim })
      .then((linhas) => {
        if (cancelado) return;
        const pontos = linhas
          .filter((l) => l.mes !== null)
          .map((l) => ({
            mes: l.mes as string,
            aberturas: l.aberturas,
            desaparecimentos: l.desaparecimentos,
          }))
          .sort((a, b) => a.mes.localeCompare(b.mes));
        setEstado(pontos.length === 0 ? { status: "vazio" } : { status: "pronto", pontos });
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

  return (
    <Sheet open={territorio !== null} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{territorio?.nome ?? ""}</SheetTitle>
          <SheetDescription>
            Aberturas e desaparecimentos por mês
            {categoriaId ? " · categoria filtrada" : " · todas as categorias"}
          </SheetDescription>
        </SheetHeader>

        <div className="px-4 pb-4">
          {estado.status === "carregando" && (
            <div role="status" aria-label="Carregando">
              <Skeleton className="h-72 w-full" />
            </div>
          )}

          {estado.status === "erro" && (
            <Alert variant="destructive">
              <AlertTitle>Não foi possível carregar a série</AlertTitle>
              <AlertDescription>{estado.mensagem}</AlertDescription>
            </Alert>
          )}

          {estado.status === "vazio" && (
            <Alert>
              <AlertTitle>Sem eventos no período</AlertTitle>
              <AlertDescription>
                Não há aberturas nem desaparecimentos registrados para este bairro com os
                filtros atuais.
              </AlertDescription>
            </Alert>
          )}

          {estado.status === "pronto" && (
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={estado.pontos} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e1e0d9" vertical={false} />
                <XAxis
                  dataKey="mes"
                  tickFormatter={formatarMes}
                  stroke="#898781"
                  tick={{ fontSize: 12 }}
                />
                <YAxis stroke="#898781" tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip
                  labelFormatter={(mes) => formatarMes(String(mes))}
                  cursor={{ stroke: "#898781", strokeDasharray: "3 3" }}
                  contentStyle={{ fontSize: 12 }}
                />
                <Legend
                  formatter={(value) =>
                    value === "aberturas" ? "Aberturas" : "Desaparecimentos"
                  }
                />
                <Line
                  type="monotone"
                  dataKey="aberturas"
                  name="aberturas"
                  stroke="#2a78d6"
                  strokeWidth={2}
                  strokeLinecap="round"
                  dot={{ r: 4 }}
                  activeDot={{ r: 5 }}
                />
                <Line
                  type="monotone"
                  dataKey="desaparecimentos"
                  name="desaparecimentos"
                  stroke="#eb6834"
                  strokeWidth={2}
                  strokeLinecap="round"
                  dot={{ r: 4 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
