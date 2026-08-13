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

export function formatarMes(mes: string): string {
  const [ano, m] = mes.split("-");
  const indice = Number(m) - 1;
  return `${NOMES_MES[indice] ?? m}/${ano.slice(2)}`;
}

export type PontoSerieTemporal = { mes: string; aberturas: number; desaparecimentos: number };

type Props = {
  pontos: PontoSerieTemporal[];
  /** Altura menor + legenda oculta para grades de small multiples
   * (checkpoint 11c, comparação de territórios). */
  compacto?: boolean;
};

// Extraído de detail-panel.tsx (checkpoint 7c) para ser reaproveitado pela
// comparação de territórios (checkpoint 11c) sem duplicar a configuração
// do gráfico - mesmas cores/formas (aberturas azul, desaparecimentos
// laranja, seção 4.2 do prompt de referência), só o tamanho muda.
export function SerieTemporalChart({ pontos, compacto = false }: Props) {
  return (
    <ResponsiveContainer width="100%" height={compacto ? 140 : 280}>
      <LineChart data={pontos} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e1e0d9" vertical={false} />
        <XAxis
          dataKey="mes"
          tickFormatter={formatarMes}
          stroke="#898781"
          tick={{ fontSize: compacto ? 10 : 12 }}
          minTickGap={compacto ? 20 : 5}
        />
        <YAxis
          stroke="#898781"
          tick={{ fontSize: compacto ? 10 : 12 }}
          allowDecimals={false}
          width={compacto ? 28 : 36}
        />
        <Tooltip
          labelFormatter={(mes) => formatarMes(String(mes))}
          cursor={{ stroke: "#898781", strokeDasharray: "3 3" }}
          contentStyle={{ fontSize: 12 }}
        />
        {!compacto && (
          <Legend formatter={(value) => (value === "aberturas" ? "Aberturas" : "Desaparecimentos")} />
        )}
        <Line
          type="monotone"
          dataKey="aberturas"
          name="aberturas"
          stroke="#2a78d6"
          strokeWidth={2}
          strokeLinecap="round"
          dot={{ r: compacto ? 2.5 : 4 }}
          activeDot={{ r: compacto ? 3.5 : 5 }}
        />
        <Line
          type="monotone"
          dataKey="desaparecimentos"
          name="desaparecimentos"
          stroke="#eb6834"
          strokeWidth={2}
          strokeLinecap="round"
          dot={{ r: compacto ? 2.5 : 4 }}
          activeDot={{ r: compacto ? 3.5 : 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
