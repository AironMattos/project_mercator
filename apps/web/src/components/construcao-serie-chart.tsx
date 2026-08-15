"use client";

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

import { formatarMes } from "@/components/serie-temporal-chart";

export type PontoSerieConstrucao = { mes: string; alvarasAprovados: number; cvcosConcluidos: number };

// Mesma anatomia de SerieTemporalChart (checkpoint 7c/11c: linha 2px,
// marcador >=8px, legenda sempre presente) - componente separado porque os
// rótulos e o significado das duas séries são outros: alvará aprovado
// ("vai mudar") x CVCO concluído ("já mudou"), nunca "aberturas/
// desaparecimentos". Mesmas cores (azul/laranja) por serem, aqui também, um
// par de eventos "início x conclusão" - não uma reinterpretação do saldo.
export function ConstrucaoSerieChart({ pontos }: { pontos: PontoSerieConstrucao[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={pontos} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e1e0d9" vertical={false} />
        <XAxis
          dataKey="mes"
          tickFormatter={formatarMes}
          stroke="#898781"
          tick={{ fontSize: 12 }}
          minTickGap={5}
        />
        <YAxis stroke="#898781" tick={{ fontSize: 12 }} allowDecimals={false} width={36} />
        <Tooltip
          labelFormatter={(mes) => formatarMes(String(mes))}
          cursor={{ stroke: "#898781", strokeDasharray: "3 3" }}
          contentStyle={{ fontSize: 12 }}
        />
        <Legend
          formatter={(value) => (value === "alvarasAprovados" ? "Alvarás aprovados" : "CVCOs concluídos")}
        />
        <Line
          type="monotone"
          dataKey="alvarasAprovados"
          name="alvarasAprovados"
          stroke="#2a78d6"
          strokeWidth={2}
          strokeLinecap="round"
          dot={{ r: 4 }}
          activeDot={{ r: 5 }}
        />
        <Line
          type="monotone"
          dataKey="cvcosConcluidos"
          name="cvcosConcluidos"
          stroke="#eb6834"
          strokeWidth={2}
          strokeLinecap="round"
          dot={{ r: 4 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
