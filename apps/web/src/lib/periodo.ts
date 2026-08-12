export type PresetPeriodo = "1" | "3" | "6" | "12";

export const PRESETS_PERIODO: Array<{ value: PresetPeriodo; label: string }> = [
  { value: "1", label: "Mês atual" },
  { value: "3", label: "Últimos 3 meses" },
  { value: "6", label: "Últimos 6 meses" },
  { value: "12", label: "Últimos 12 meses" },
];

export type IntervaloData = { dataInicio: string; dataFim: string };

function formatarData(d: Date): string {
  return d.toISOString().slice(0, 10);
}

const MESES_ABREVIADOS = [
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

/** "2026-08-01" -> "ago/2026". Usado para mostrar cobertura real de dado,
 * não o range do preset de período (que é sempre um filtro, existir ou não
 * dado real dentro dele). */
export function formatarMesAno(iso: string): string {
  const [ano, mes] = iso.split("-");
  return `${MESES_ABREVIADOS[Number(mes) - 1]}/${ano}`;
}

/** meses=1 -> só o mês atual; meses=3 -> mês atual + 2 anteriores; etc. */
export function intervaloUltimosMeses(meses: number): IntervaloData {
  const hoje = new Date();
  const inicio = new Date(hoje.getFullYear(), hoje.getMonth() - (meses - 1), 1);
  const fim = new Date(hoje.getFullYear(), hoje.getMonth() + 1, 0);
  return { dataInicio: formatarData(inicio), dataFim: formatarData(fim) };
}
